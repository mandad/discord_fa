from datetime import datetime, timezone

import solar


def test_parse_swpc_with_and_without_z():
    a = solar.parse_swpc("2026-06-25T03:00:00")
    b = solar.parse_swpc("2026-06-25T03:00:00Z")
    assert a == b
    assert a.tzinfo is timezone.utc


def test_sun_altitude_known_signs():
    # London at equinox: high near noon, well below horizon at midnight.
    noon = solar.sun_altitude(51.5, 0.0, datetime(2026, 3, 20, 12, tzinfo=timezone.utc))
    midnight = solar.sun_altitude(51.5, 0.0, datetime(2026, 3, 20, 0, tzinfo=timezone.utc))
    assert noon > 30
    assert midnight < -30


def test_is_dark_nautical():
    # Fairbanks deep winter night -> darker than nautical twilight.
    assert solar.is_dark_nautical(64.8, -147.7, datetime(2026, 1, 1, 11, tzinfo=timezone.utc))
    # Bering Sea summer local midnight -> NOT dark (sun stays high-ish at this latitude).
    assert not solar.is_dark_nautical(60.5, -172.9, datetime(2026, 6, 22, 12, tzinfo=timezone.utc))


def test_to_local_uses_alaska_zone():
    dt = datetime(2026, 6, 25, 3, tzinfo=timezone.utc)
    loc, tzabbr = solar.to_local(dt, 60.34, -172.69)
    assert tzabbr.startswith("AK")          # AKDT in summer
    assert loc.utcoffset().total_seconds() == -8 * 3600


def test_window_label_and_local_str_format():
    label = solar.window_label("2026-06-25T03:00:00", 60.34, -172.69)
    assert label.startswith("2026-06-25T03:00:00Z")
    assert "AK" in label
    assert "AK" in solar.local_str("2026-06-25T03:00:00Z", 60.34, -172.69)


def test_no_position_defaults_to_alaska():
    # When lat/lon are unknown, still resolve to Alaska time (not a crash, not UTC).
    assert "AK" in solar.window_label("2026-06-25T03:00:00", None, None)


def test_default_local_date_same_ak_day_across_utc_dates():
    # The reported double: 18:00 UTC Jun 25 and 01:00 UTC Jun 26 are different UTC dates but
    # both fall on Jun 25 in Alaska (AKDT = UTC-8) -> dedupe must treat them as one day.
    early = datetime(2026, 6, 25, 18, tzinfo=timezone.utc)   # 10:00 AKDT Jun 25
    late = datetime(2026, 6, 26, 1, tzinfo=timezone.utc)     # 17:00 AKDT Jun 25
    assert solar.default_local_date(early) == "2026-06-25"
    assert solar.default_local_date(late) == "2026-06-25"
