"""Live network tests — hit the real public endpoints to confirm forecasts pull correctly.

Run with:  pytest -m live      (skipped by default via -m "not live")
These can be flaky if an upstream service is briefly down; in CI they run as a non-blocking job.
"""
import aiohttp
import pytest

import gi
import swpc

pytestmark = pytest.mark.live


async def test_live_kp_forecast_has_predicted_rows():
    async with aiohttp.ClientSession() as s:
        rows = await swpc.fetch_kp_forecast(s)
    assert len(rows) > 10
    assert any(r["kind"] == "predicted" for r in rows)
    assert any(r["kind"] == "observed" for r in rows)
    assert all(0 <= r["kp"] <= 9 for r in rows)


async def test_live_ovation_grid():
    async with aiohttp.ClientSession() as s:
        grid, obs_t, fc_t = await swpc.fetch_ovation(s)
    assert len(grid) > 50000           # ~360 x 181 global 1-degree grid
    assert obs_t and fc_t
    # a value at a real cell is an int 0..100
    v = next(iter(grid.values()))
    assert 0 <= v <= 100


async def test_live_gi_daily_forecast():
    async with aiohttp.ClientSession() as s:
        daily = await gi.fetch_daily(s)
    assert len(daily) >= 3
    assert all(0 <= k <= 9 for k in daily.values())


async def test_live_viewline_images_resolve():
    urls = list(swpc.NOAA_VIEWLINE.values()) + [gi.viewline_url(4)]
    async with aiohttp.ClientSession() as s:
        for u in urls:
            async with s.get(u) as r:
                assert r.status == 200
                assert r.headers["content-type"].startswith("image/")
