"""University of Alaska Fairbanks — Geophysical Institute (GI) aurora forecast.

Two things from https://www.gi.alaska.edu/monitors/aurora-forecast :

1. A daily Kp forecast (NOAA-derived, embedded as JSON in the page) used to cross-reference
   our SWPC 3-hourly forecast.
2. The Alaska "viewline" diagrams: per-Kp maps of the auroral oval + equatorward visibility
   line over Alaska, at a deterministic URL keyed by integer Kp (0-9). We attach the matching
   one to a Kp alert.
"""
from __future__ import annotations

import json
import re

import aiohttp

GI_URL = "https://www.gi.alaska.edu/monitors/aurora-forecast"
_IMG_BASE = "https://www.gi.alaska.edu/modules/custom/aurora-forecast/images/idl_graphics"
HEADERS = {"User-Agent": "aurora-fairweather-bot/1.0 (+discord)"}

# The page hides several forecast arrays in <p id="db-data-*"> tags. We want the 3-day NOAA
# geomagnetic forecast (3-hourly, id=db-data-3-day) and the longer 27-day outlook as fallback.
_BLOCK_RE = re.compile(r'id="(db-data-3-day|db-data-27-day)"[^>]*>(\[.*?\])', re.S)


def viewline_url(kp, region_dir: str = "ak", region_name: str = "Alaska") -> str:
    """GI viewline map URL for the given Kp (clamped to the available 0-9 integer maps)."""
    n = max(0, min(9, int(round(float(kp)))))
    return f"{_IMG_BASE}/{region_dir}/{region_name}_{n}.png"


def _loads(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


async def fetch_daily(session: aiohttp.ClientSession) -> dict[str, int]:
    """Return GI's forecast Kp as {'YYYY-MM-DD': kp_int}. Best-effort: {} on any failure.

    The 3-day forecast is 3-hourly; we take each day's max Kp, which is what GI shows as that
    day's value (and what selects its viewline map). The 27-day outlook fills later dates.
    """
    try:
        async with session.get(GI_URL, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=30)) as r:
            r.raise_for_status()
            html = await r.text()
    except Exception:
        return {}
    blocks = dict(_BLOCK_RE.findall(html))
    daily: dict[str, int] = {}
    for row in _loads(blocks.get("db-data-27-day")):       # longer range, lower priority
        daily[row["predicted_time"][:10]] = int(round(float(row["kp"])))
    threeday: dict[str, float] = {}
    for row in _loads(blocks.get("db-data-3-day")):        # near term, day's max Kp
        d = row["predicted_time"][:10]
        threeday[d] = max(threeday.get(d, 0.0), float(row["kp"]))
    for d, k in threeday.items():
        daily[d] = int(round(k))
    return daily


if __name__ == "__main__":  # smoke test
    import asyncio

    async def _main():
        async with aiohttp.ClientSession() as s:
            daily = await fetch_daily(s)
        print(f"GI daily forecast entries: {len(daily)}")
        for d in list(daily)[:6]:
            print(f"  {d}: Kp {daily[d]}")
        print("viewline for Kp 4.3 ->", viewline_url(4.3))

    asyncio.run(_main())
