"""Discord embed builders for the prediction (daily) and observed (hourly) posts."""
from __future__ import annotations

import discord

import solar
import swpc


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
        e.add_field(name="Kp (observed)", value=f"{kp:g} @ {observed_kp['time_tag']}Z", inline=True)
    e.add_field(name="Outlook", value=viewing_assessment(prob, kp), inline=False)
    if obs_time:
        e.set_footer(text=f"OVATION obs {obs_time} · source: NOAA SWPC + mfphub AIS")
    return e


def build_prediction_embed(ship: dict, kp_rows: list[dict], grid: dict, obs_time,
                           threshold: float) -> discord.Embed:
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
        peak_txt = "\n".join(f"Kp {p['kp']:g} — {solar.window_label(p['time_tag'], lon)}" for p in peaks)
        e.add_field(name="Predicted Kp peaks (3-day)", value=peak_txt, inline=False)
    ge = swpc.predicted_ge(kp_rows, threshold)
    if ge:
        ge_txt = "\n".join(f"Kp {r['kp']:g} — {solar.window_label(r['time_tag'], lon)}" for r in ge)
        e.add_field(name=f"⚡ Forecast Kp ≥ {threshold:g}", value=ge_txt, inline=False)
    e.add_field(name="Outlook", value=viewing_assessment(prob, top_kp), inline=False)
    if obs_time:
        e.set_footer(text=f"OVATION obs {obs_time} · source: NOAA SWPC + mfphub AIS")
    return e
