"""Discord embed builders for the prediction (daily) and observed (hourly) posts."""
from __future__ import annotations

import io
from datetime import datetime, timezone

import discord

import gi
import solar
import swpc


def next_window_line(kp_rows: list[dict], ship: dict, threshold: float) -> str:
    """One-line summary of the next upcoming predicted Kp >= threshold window (for /aurora)."""
    ge = swpc.predicted_ge(kp_rows, threshold)
    if not ge:
        return f"None ≥ Kp {threshold:g} in the SWPC 3-day forecast."
    lat, lon = ship.get("lat"), ship.get("lon")
    nxt = ge[0]
    dt = solar.parse_swpc(nxt["time_tag"])
    hrs = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
    rel = f"in {hrs / 24:.1f} d" if hrs >= 24 else f"in {max(0, hrs):.0f} h"
    line = f"Kp {nxt['kp']:g} — {solar.window_label(nxt['time_tag'], lat, lon)} ({rel})"
    if lat is not None and lon is not None:
        line += " · 🌑 dark at ship" if solar.is_dark_nautical(lat, lon, dt) else " · ☀️ daylight at ship"
    return line


def _crossref_value(kp_rows: list[dict], gi_daily: dict | None, dates) -> str:
    """Per-date 'ours vs UAF GI' Kp comparison plus a link to the GI forecast/viewline page."""
    lines = []
    for d in sorted(set(dates)):
        ours = max((r["kp"] for r in kp_rows if r["time_tag"][:10] == d), default=None)
        g = (gi_daily or {}).get(d)
        g_txt = f"Kp {g}" if g is not None else "Kp —"
        lines.append(f"{d}: ours Kp {ours:g} · GI {g_txt}" if ours is not None
                     else f"{d}: GI {g_txt}")
    lines.append(f"[GI forecast & viewline]({gi.GI_URL})")
    return "\n".join(lines)


def _pos_line(ship: dict, include_motion: bool = True) -> str:
    lat, lon = ship.get("lat"), ship.get("lon")
    line = f"**{lat:.3f}, {lon:.3f}**" if lat is not None and lon is not None else "position unknown"
    age = ship.get("_age_hours")
    if age is not None:
        line += f" · fix {age:.1f}h old"
    if ship.get("_stale"):
        line += " ⚠️ STALE (pusher may be down / ship off-network)"
    if include_motion:
        # SOG/COG are unreliable while stationary, so callers can omit them.
        bits = [f"{label} {ship[k]}{unit}"
                for k, label, unit in (("sog_kt", "SOG", " kt"), ("cog", "COG", "°"))
                if ship.get(k) is not None]
        if bits:
            line += " · " + " · ".join(bits)
    return line


def viewing_assessment(prob, kp) -> str:
    """One-line plain-language read from aurora % at position + planetary Kp."""
    if prob is None:
        return "No aurora grid value for this position."
    if prob >= 50:
        head = "🟢 Strong odds overhead"
    elif prob >= 25:
        head = "🟡 Moderate odds overhead"
    elif prob >= 10:
        head = "🟠 Low odds overhead"
    else:
        head = "🔴 Aurora unlikely overhead"
    kp_txt = f" · planetary Kp {kp:g}" if kp is not None else ""
    return f"{head} ({prob}% visible){kp_txt}"


def _color(prob, kp) -> int:
    score = max(prob or 0, (kp or 0) * 10)
    if score >= 50:
        return 0x2ECC71  # green
    if score >= 25:
        return 0xF1C40F  # yellow
    if score >= 10:
        return 0xE67E22  # orange
    return 0x95A5A6      # grey


def build_observed_embed(ship: dict, observed_kp, grid: dict, obs_time) -> discord.Embed:
    lat, lon = ship.get("lat"), ship.get("lon")
    prob = swpc.aurora_prob_at(grid, lat, lon)
    kp = observed_kp["kp"] if observed_kp else None
    e = discord.Embed(
        title="🛰️ Aurora — observed conditions",
        description=_pos_line(ship, include_motion=False),
        color=_color(prob, kp),
    )
    e.add_field(name="Aurora at ship", value=f"{prob}% visible" if prob is not None else "n/a", inline=True)
    if observed_kp:
        e.add_field(name="Kp (observed)",
                    value=f"{kp:g} @ {solar.local_str(observed_kp['time_tag'], lat, lon)}", inline=True)
    e.add_field(name="Outlook", value=viewing_assessment(prob, kp), inline=False)
    if obs_time:
        e.set_footer(text=f"OVATION obs {solar.local_str(obs_time, lat, lon)} · source: NOAA SWPC + mfphub AIS")
    return e


def build_prediction_embed(ship: dict, kp_rows: list[dict], grid: dict, obs_time,
                           threshold: float, gi_daily: dict | None = None) -> discord.Embed:
    lat, lon = ship.get("lat"), ship.get("lon")
    prob = swpc.aurora_prob_at(grid, lat, lon)
    peaks = swpc.predicted_peaks(kp_rows, top=3)
    top_kp = peaks[0]["kp"] if peaks else None
    e = discord.Embed(
        title="🌌 Aurora forecast — NOAA Ship Fairweather",
        description=_pos_line(ship),
        color=_color(prob, top_kp),
    )
    e.add_field(name="Aurora at ship now", value=f"{prob}% visible" if prob is not None else "n/a", inline=True)
    if peaks:
        peak_txt = "\n".join(f"Kp {p['kp']:g} — {solar.window_label(p['time_tag'], lat, lon)}" for p in peaks)
        e.add_field(name="Predicted Kp peaks (3-day)", value=peak_txt, inline=False)
    ge = swpc.predicted_ge(kp_rows, threshold)
    if ge:
        ge_txt = "\n".join(f"Kp {r['kp']:g} — {solar.window_label(r['time_tag'], lat, lon)}" for r in ge)
        e.add_field(name=f"⚡ Forecast Kp ≥ {threshold:g}", value=ge_txt, inline=False)
    e.add_field(name="Outlook", value=viewing_assessment(prob, top_kp), inline=False)
    xref_dates = [r["time_tag"][:10] for r in ge] or [p["time_tag"][:10] for p in peaks[:1]]
    e.add_field(name="🔭 UAF GI cross-reference",
                value=_crossref_value(kp_rows, gi_daily, xref_dates), inline=False)
    if obs_time:
        e.set_footer(text=f"OVATION obs {solar.local_str(obs_time, lat, lon)} · source: NOAA SWPC + mfphub AIS")
    return e


def build_alert_embed(new_windows: list[dict], ship: dict, kp_rows: list[dict],
                      gi_daily: dict | None, threshold: float) -> discord.Embed:
    """Kp alert embed: window list, UAF GI cross-reference, and the GI Alaska viewline map."""
    lat, lon = ship.get("lat"), ship.get("lon")
    lines = "\n".join(f"Kp {r['kp']:g} — {solar.window_label(r['time_tag'], lat, lon)}"
                      for r in new_windows)
    e = discord.Embed(
        title=f"⚡ Aurora alert — forecast Kp ≥ {threshold:g} (dark at ship)",
        description=lines,
        color=0x9B59B6,
    )
    e.add_field(name="🔭 UAF GI cross-reference",
                value=_crossref_value(kp_rows, gi_daily, [r["time_tag"][:10] for r in new_windows]),
                inline=False)
    peak_kp = max(int(round(r["kp"])) for r in new_windows)
    e.set_image(url=gi.viewline_url(peak_kp))
    e.set_footer(text=f"Viewline: UAF Geophysical Institute (Alaska, Kp {peak_kp})")
    return e


def swpc_forecast_embed(img_bytes: bytes | None = None):
    """SWPC current OVATION aurora forecast map (N. hemisphere) as an image embed.

    Returns (embed, file). With img_bytes, the image is attached so Discord shows the current
    frame rather than a cached copy of the static URL; otherwise it falls back to the URL and
    file is None.
    """
    e = discord.Embed(title="🛰️ SWPC aurora forecast — current (OVATION, N. hemisphere)",
                      url=swpc.NOAA_OVATION_PAGE, color=0x1ABC9C)
    if img_bytes:
        f = discord.File(io.BytesIO(img_bytes), filename="swpc_aurora_forecast.jpg")
        e.set_image(url="attachment://swpc_aurora_forecast.jpg")
        return e, f
    e.set_image(url=swpc.NOAA_OVATION_IMAGE)
    return e, None


def noaa_viewline_embeds() -> list[discord.Embed]:
    """NOAA SWPC static predicted-viewline images (tonight + tomorrow night) as image embeds."""
    out = []
    for label, url in swpc.NOAA_VIEWLINE.items():
        e = discord.Embed(title=f"NOAA predicted viewline — {label}",
                          url=swpc.NOAA_VIEWLINE_PAGE, color=0x3498DB)
        e.set_image(url=url)
        out.append(e)
    return out
