import gi
from conftest import FakeResp, FakeSession


def test_viewline_url_round_and_clamp():
    assert gi.viewline_url(4.0).endswith("/ak/Alaska_4.png")
    assert gi.viewline_url(3.67).endswith("Alaska_4.png")   # rounds
    assert gi.viewline_url(12).endswith("Alaska_9.png")     # clamps high
    assert gi.viewline_url(-3).endswith("Alaska_0.png")     # clamps low


async def test_fetch_daily_prefers_3day_max(gi_html):
    daily = await gi.fetch_daily(FakeSession(FakeResp(text_data=gi_html)))
    # 3-day array: day max overrides the 27-day value (4.0 > 2) and rounds to int.
    assert daily["2026-06-24"] == 4
    assert daily["2026-06-25"] == 3       # round(3.33)
    # date only in the 27-day outlook is still present.
    assert daily["2026-07-10"] == 3


async def test_fetch_daily_best_effort_on_error():
    # HTTP failure -> empty dict, never raises.
    assert await gi.fetch_daily(FakeSession(FakeResp(text_data="", status=500))) == {}
    # missing arrays -> empty dict.
    assert await gi.fetch_daily(FakeSession(FakeResp(text_data="<html>no data</html>"))) == {}
