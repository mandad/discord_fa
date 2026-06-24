"""Live network tests — hit the real public endpoints to confirm forecasts pull correctly.

Run with:  pytest -m live      (skipped by default via -m "not live")

Philosophy: a host being unreachable from the runner is an environment problem, not a
regression, so those cases SKIP. When a host IS reachable, the data shape is asserted strictly
(that's the real check). In CI the whole job is also non-blocking. (gi.alaska.edu is frequently
unreachable from GitHub's IP ranges, hence the skip guard.)
"""
import asyncio

import aiohttp
import pytest

import gi
import swpc

pytestmark = pytest.mark.live

_TIMEOUT = aiohttp.ClientTimeout(total=25)


async def _probe(session, url):
    """Return (status, content_type) or skip the test if the host is unreachable."""
    try:
        async with session.get(url, timeout=_TIMEOUT) as r:
            return r.status, r.headers.get("content-type", "")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        pytest.skip(f"unreachable from this network: {url} ({type(e).__name__})")


async def test_live_kp_forecast_has_predicted_rows():
    async with aiohttp.ClientSession() as s:
        await _probe(s, swpc.KP_URL)
        rows = await swpc.fetch_kp_forecast(s)
    assert len(rows) > 10
    assert any(r["kind"] == "predicted" for r in rows)
    assert any(r["kind"] == "observed" for r in rows)
    assert all(0 <= r["kp"] <= 9 for r in rows)


async def test_live_ovation_grid():
    async with aiohttp.ClientSession() as s:
        await _probe(s, swpc.OVATION_URL)
        grid, obs_t, fc_t = await swpc.fetch_ovation(s)
    assert len(grid) > 50000           # ~360 x 181 global 1-degree grid
    assert obs_t and fc_t
    assert 0 <= next(iter(grid.values())) <= 100


async def test_live_gi_daily_forecast():
    async with aiohttp.ClientSession() as s:
        await _probe(s, gi.GI_URL)     # skips if GI is blocked/unreachable
        daily = await gi.fetch_daily(s)
    assert len(daily) >= 3, "GI reachable but no forecast parsed — selector may have changed"
    assert all(0 <= k <= 9 for k in daily.values())


async def test_live_noaa_viewline_images_resolve():
    async with aiohttp.ClientSession() as s:
        for u in swpc.NOAA_VIEWLINE.values():
            st, ct = await _probe(s, u)
            assert st == 200 and ct.startswith("image/")


async def test_live_gi_viewline_image_resolves():
    async with aiohttp.ClientSession() as s:
        st, ct = await _probe(s, gi.viewline_url(4))   # skips if GI unreachable
    assert st == 200 and ct.startswith("image/")
