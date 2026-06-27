import alerts


def test_check_kp_alert_threshold_and_dedupe(kp_rows):
    state = {}
    first = alerts.check_kp_alert(kp_rows, state, 4)
    assert [r["kp"] for r in first] == [4.0, 5.0]
    # state now records both windows; a second pass yields nothing (deduped).
    assert alerts.check_kp_alert(kp_rows, state, 4) == []


def test_check_kp_alert_repings_only_on_increase(kp_rows):
    state = {}
    alerts.check_kp_alert(kp_rows, state, 4)
    # same windows, but one window's predicted Kp rose -> re-fires only that one.
    bumped = [dict(r) for r in kp_rows]
    for r in bumped:
        if r["time_tag"] == "2026-06-25T03:00:00":
            r["kp"] = 6.0
    again = alerts.check_kp_alert(bumped, state, 4)
    assert [r["time_tag"] for r in again] == ["2026-06-25T03:00:00"]


def test_check_kp_alert_keep_filter(kp_rows):
    state = {}
    keep = lambda r: r["time_tag"].startswith("2026-06-26")  # only the 06-26 window survives
    out = alerts.check_kp_alert(kp_rows, state, 4, keep=keep)
    assert [r["time_tag"] for r in out] == ["2026-06-26T00:00:00"]
    # filtered-out windows were not recorded, so they remain eligible later.
    assert "2026-06-25T03:00:00" not in state


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    assert alerts.load_state(p) == {}          # missing file -> empty
    alerts.save_state(p, {"2026-06-25T03:00:00": 4.0})
    assert alerts.load_state(p) == {"2026-06-25T03:00:00": 4.0}


def test_daily_dedupe_roundtrip_preserves_alert_state(tmp_path):
    p = tmp_path / "state.json"
    assert alerts.daily_already_posted(p, "2026-06-25") is False
    alerts.save_state(p, {"2026-06-25T03:00:00": 4.0})   # pre-existing Kp-alert state
    alerts.mark_daily_posted(p, "2026-06-25")
    assert alerts.daily_already_posted(p, "2026-06-25") is True
    assert alerts.daily_already_posted(p, "2026-06-26") is False   # different day not suppressed
    # marking the daily date must not clobber the Kp-alert windows
    assert alerts.load_state(p)["2026-06-25T03:00:00"] == 4.0
