import swpc
from conftest import FakeResp, FakeSession


async def test_fetch_kp_forecast_parses_and_skips_bad(kp_raw):
    rows = await swpc.fetch_kp_forecast(FakeSession(FakeResp(json_data=kp_raw)))
    assert len(rows) == 5  # the malformed row is dropped
    assert rows[0] == {"time_tag": "2026-06-23T00:00:00", "kp": 3.0, "kind": "observed"}
    assert all(isinstance(r["kp"], float) for r in rows)
    assert {r["kind"] for r in rows} == {"observed", "predicted"}


async def test_fetch_ovation_builds_grid(ovation_raw):
    grid, obs_t, fc_t = await swpc.fetch_ovation(FakeSession(FakeResp(json_data=ovation_raw)))
    assert obs_t == "2026-06-23T05:57:00Z"
    assert fc_t == "2026-06-23T07:10:00Z"
    assert grid[(188, 60)] == 55
    assert len(grid) == 4


def test_latest_observed_kp(kp_rows):
    obs = swpc.latest_observed_kp(kp_rows)
    assert obs["kind"] == "observed"
    assert obs["time_tag"] == "2026-06-23T03:00:00"  # most recent observed


def test_predicted_ge_threshold(kp_rows):
    ge = swpc.predicted_ge(kp_rows, 4)
    assert [r["kp"] for r in ge] == [4.0, 5.0]
    assert swpc.predicted_ge(kp_rows, 9) == []


def test_predicted_peaks_sorted(kp_rows):
    peaks = swpc.predicted_peaks(kp_rows, top=2)
    assert [r["kp"] for r in peaks] == [5.0, 4.0]


def test_aurora_prob_at_lookup_wrap_clamp(grid):
    assert swpc.aurora_prob_at(grid, 60.3, -172.1) == 55      # round -172.1 -> -172 -> 188
    assert swpc.aurora_prob_at(grid, 60.4, 187.6) == 55       # 188 directly
    assert swpc.aurora_prob_at(grid, -95, 0) == 2             # lat clamps to -90
    assert swpc.aurora_prob_at(grid, None, None) is None
    assert swpc.aurora_prob_at(grid, 12.3, 45.6) is None      # missing cell
