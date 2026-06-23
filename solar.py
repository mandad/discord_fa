"""Sun altitude + ship-local time — dependency-free.

Used to (a) gate Kp alerts on darkness (aurora needs the sky darker than nautical twilight,
i.e. sun altitude < -12 deg) and (b) show a forecast window's time in ship-local terms.

Local time at sea is taken from longitude (nautical zone time, offset = round(lon/15)),
which is the right notion for a ship in open water and needs no timezone database.

The solar position is the standard low-precision NOAA algorithm (~0.01 deg), far more than
enough for twilight gating.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

NAUTICAL_TWILIGHT_ALT = -12.0  # deg; sky is "darker than nautical twilight" below this


def parse_swpc(time_tag: str) -> datetime:
    """SWPC time_tag like '2026-06-20T03:00:00' (UTC) -> aware UTC datetime."""
    return datetime.fromisoformat(time_tag).replace(tzinfo=timezone.utc)


def _julian(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    day = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def sun_altitude(lat: float, lon: float, dt: datetime) -> float:
    """Sun altitude in degrees at (lat, lon) for aware datetime `dt`."""
    n = _julian(dt) - 2451545.0
    mean_long = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = mean_long + math.radians(1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    lmst = (gmst + lon) % 360
    ha = math.radians((lmst - math.degrees(ra)) % 360)
    latr = math.radians(lat)
    alt = math.asin(math.sin(latr) * math.sin(dec) + math.cos(latr) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt)


def is_dark_nautical(lat: float, lon: float, dt: datetime) -> bool:
    """True if the sky at (lat, lon, dt) is darker than nautical twilight (aurora-visible)."""
    return sun_altitude(lat, lon, dt) < NAUTICAL_TWILIGHT_ALT


def to_local(dt_utc: datetime, lon: float):
    """Return (local_datetime, integer_offset_hours) using nautical zone time from longitude."""
    off = round(lon / 15)
    return dt_utc + timedelta(hours=off), off


def window_label(time_tag: str, lon) -> str:
    """'2026-06-20T03:00:00Z · Sat 16:00 ship-local (UTC-11)'. UTC-only if lon is None."""
    if lon is None:
        return f"{time_tag}Z"
    loc, off = to_local(parse_swpc(time_tag), lon)
    return f"{time_tag}Z · {loc:%a %H:%M} ship-local (UTC{off:+d})"


if __name__ == "__main__":  # smoke test
    # Fairweather-ish Bering Sea position in June: high-latitude summer -> little/no darkness.
    lat, lon = 60.56, -172.91
    for h in (3, 9, 12, 15, 21):
        dt = datetime(2026, 6, 22, h, 0, tzinfo=timezone.utc)
        alt = sun_altitude(lat, lon, dt)
        loc, off = to_local(dt, lon)
        print(f"{dt:%Y-%m-%d %H:%M}Z  alt={alt:6.1f}deg  dark={alt < NAUTICAL_TWILIGHT_ALT!s:5}  "
              f"local={loc:%a %H:%M} (UTC{off:+d})")
    # Sanity: London local noon should be high; midnight negative.
    for h in (0, 12):
        dt = datetime(2026, 3, 20, h, tzinfo=timezone.utc)
        print(f"London {h:02d}Z alt={sun_altitude(51.5, 0.0, dt):.1f}")
