"""NOAA SWPC data: planetary Kp forecast + OVATION aurora nowcast.

Endpoints are public, no auth. Verified live:
  Kp forecast: https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json
    -> [[time_tag, kp, "observed"|"predicted", noaa_scale], ...], first row is a header.
  OVATION:     https://services.swpc.noaa.gov/json/ovation_aurora_latest.json
    -> {"Observation Time", "Forecast Time", "coordinates": [[lon, lat, value], ...]}
       lon 0..359, lat -90..90, value = % probability of visible aurora at that cell.
"""
from __future__ import annotations

import aiohttp

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
OVATION_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
HEADERS = {"User-Agent": "aurora-fairweather-bot/1.0"}

# NOAA SWPC experimental static viewline forecast (OVATION driven by the 3-day Kp forecast).
NOAA_VIEWLINE_PAGE = "https://www.spaceweather.gov/products/aurora-viewline-tonight-and-tomorrow-night-experimental"
NOAA_VIEWLINE = {
    "tonight": "https://services.swpc.noaa.gov/experimental/images/aurora_dashboard/tonights_static_viewline_forecast.png",
    "tomorrow night": "https://services.swpc.noaa.gov/experimental/images/aurora_dashboard/tomorrow_nights_static_viewline_forecast.png",
}

# Current OVATION aurora forecast map (Northern Hemisphere, ~30-min nowcast). Static URL that
# always serves the latest frame; we attach the bytes so Discord shows the current map, not a
# cached copy of the URL.
NOAA_OVATION_PAGE = "https://www.swpc.noaa.gov/products/aurora-30-minute-forecast"
NOAA_OVATION_IMAGE = "https://services.swpc.noaa.gov/images/aurora-forecast-northern-hemisphere.jpg"


async def _fetch_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as r:
        r.raise_for_status()
        return await r.json(content_type=None)


async def fetch_kp_forecast(session: aiohttp.ClientSession) -> list[dict]:
    """Return rows as dicts: {time_tag, kp: float, kind: 'observed'|'predicted'}.

    The endpoint yields a list of objects {time_tag, kp, observed, noaa_scale}; `observed`
    is the literal string 'observed' or 'predicted'.
    """
    raw = await _fetch_json(session, KP_URL)
    rows = []
    for r in raw:
        try:
            rows.append({"time_tag": r["time_tag"], "kp": float(r["kp"]), "kind": r["observed"]})
        except (KeyError, ValueError, TypeError):
            continue
    return rows


async def fetch_ovation_image(session: aiohttp.ClientSession) -> bytes | None:
    """Current SWPC OVATION aurora forecast image (N. hemisphere) as bytes; None on failure."""
    try:
        async with session.get(NOAA_OVATION_IMAGE, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=30)) as r:
            r.raise_for_status()
            return await r.read()
    except Exception:
        return None


async def fetch_ovation(session: aiohttp.ClientSession):
    """Return (grid, obs_time, forecast_time). grid: {(lon, lat): value} with lon in 0..359."""
    raw = await _fetch_json(session, OVATION_URL)
    grid = {(int(lon), int(lat)): int(val) for lon, lat, val in raw.get("coordinates", [])}
    return grid, raw.get("Observation Time"), raw.get("Forecast Time")


def latest_observed_kp(rows: list[dict]):
    """Most recent observed Kp as {time_tag, kp}, or None."""
    obs = [r for r in rows if r["kind"] == "observed"]
    return obs[-1] if obs else None


def predicted_ge(rows: list[dict], threshold: float) -> list[dict]:
    """Predicted (future) rows with kp >= threshold, in time order."""
    return [r for r in rows if r["kind"] == "predicted" and r["kp"] >= threshold]


def predicted_peaks(rows: list[dict], top: int = 3) -> list[dict]:
    """Highest predicted Kp windows (for the daily summary), sorted by kp desc."""
    pred = [r for r in rows if r["kind"] == "predicted"]
    return sorted(pred, key=lambda r: r["kp"], reverse=True)[:top]


def aurora_prob_at(grid: dict, lat: float, lon: float):
    """% visible-aurora probability at the nearest 1-degree cell to (lat, lon), or None."""
    if lat is None or lon is None:
        return None
    lon_key = round(lon) % 360
    lat_key = max(-90, min(90, round(lat)))
    return grid.get((lon_key, lat_key))


if __name__ == "__main__":  # smoke test against live endpoints
    import asyncio

    async def _main():
        test_lat, test_lon = 57.0, -152.0  # Gulf of Alaska, near typical Fairweather ops
        async with aiohttp.ClientSession() as s:
            rows = await fetch_kp_forecast(s)
            grid, obs_t, fc_t = await fetch_ovation(s)
        obs = latest_observed_kp(rows)
        print(f"rows: {len(rows)}  (observed+predicted)")
        print(f"latest observed Kp: {obs}")
        ge = predicted_ge(rows, 4)
        print(f"predicted Kp>=4 windows: {[(r['time_tag'], r['kp']) for r in ge] or 'none'}")
        print(f"top predicted peaks: {[(r['time_tag'], r['kp']) for r in predicted_peaks(rows)]}")
        print(f"OVATION obs={obs_t} forecast={fc_t} cells={len(grid)}")
        print(f"aurora % at ({test_lat},{test_lon}): {aurora_prob_at(grid, test_lat, test_lon)}")

    asyncio.run(_main())
