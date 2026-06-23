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

# first embedded array of daily {"predicted_time":"YYYY-MM-DD","kp":"N"} objects
_DAILY_RE = re.compile(r'\[\{"predicted_time":"\d{4}-\d{2}-\d{2}".*?\}\]')


def viewline_url(kp, region_dir: str = "ak", region_name: str = "Alaska") -> str:
    """GI viewline map URL for the given Kp (clamped to the available 0-9 integer maps)."""
    n = max(0, min(9, int(round(float(kp)))))
    return f"{_IMG_BASE}/{region_dir}/{region_name}_{n}.png"


async def fetch_daily(session: aiohttp.ClientSession) -> dict[str, int]:
    """Return GI's daily Kp forecast as {'YYYY-MM-DD': kp_int}. Best-effort: {} on any failure."""
    try:
        async with session.get(GI_URL, headers=HEADERS,
                               timeout=aiohttp.ClientTimeout(total=30)) as r:
            r.raise_for_status()
            html = await r.text()
        m = _DAILY_RE.search(html)
        if not m:
            return {}
        return {row["predicted_time"]: int(row["kp"]) for row in json.loads(m.group(0))}
    except Exception:
        return {}


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
