"""Shared fixtures + offline fakes (no network, no Discord token, no ship-position.py needed)."""
import sys
from pathlib import Path

import pytest

# Make the project modules importable when tests run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---- fake aiohttp session/response ------------------------------------------------------------
class FakeResp:
    def __init__(self, *, json_data=None, text_data=None, status=200):
        self._json = json_data
        self._text = text_data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self, content_type=None):
        return self._json

    async def text(self):
        return self._text


class FakeSession:
    """Returns the same FakeResp for any .get(); usable as `async with FakeSession() as s`."""
    def __init__(self, resp: FakeResp):
        self._resp = resp
        self.requested = []

    def get(self, url, **kw):
        self.requested.append(url)
        return self._resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


# ---- sample payloads --------------------------------------------------------------------------
@pytest.fixture
def kp_raw():
    """Shape of services.swpc.noaa.gov planetary-k-index-forecast.json (list of dicts)."""
    return [
        {"time_tag": "2026-06-23T00:00:00", "kp": 3.0, "observed": "observed", "noaa_scale": None},
        {"time_tag": "2026-06-23T03:00:00", "kp": 2.33, "observed": "observed", "noaa_scale": None},
        {"time_tag": "2026-06-24T18:00:00", "kp": 3.67, "observed": "predicted", "noaa_scale": None},
        {"time_tag": "2026-06-25T03:00:00", "kp": 4.0, "observed": "predicted", "noaa_scale": None},
        {"time_tag": "2026-06-26T00:00:00", "kp": 5.0, "observed": "predicted", "noaa_scale": None},
        {"time_tag": "bad", "kp": "x", "observed": "predicted"},  # must be skipped
    ]


@pytest.fixture
def kp_rows():
    """Already-parsed rows as swpc.fetch_kp_forecast would return."""
    return [
        {"time_tag": "2026-06-23T00:00:00", "kp": 3.0, "kind": "observed"},
        {"time_tag": "2026-06-23T03:00:00", "kp": 2.33, "kind": "observed"},
        {"time_tag": "2026-06-24T18:00:00", "kp": 3.67, "kind": "predicted"},
        {"time_tag": "2026-06-25T03:00:00", "kp": 4.0, "kind": "predicted"},
        {"time_tag": "2026-06-26T00:00:00", "kp": 5.0, "kind": "predicted"},
    ]


@pytest.fixture
def ovation_raw():
    return {
        "Observation Time": "2026-06-23T05:57:00Z",
        "Forecast Time": "2026-06-23T07:10:00Z",
        "coordinates": [[188, 60, 55], [188, 61, 40], [0, -90, 2], [359, 0, 1]],
    }


@pytest.fixture
def grid():
    # lon (0..359) keyed; ship at lon -172 -> 188
    return {(188, 60): 55, (188, 61): 40, (0, -90): 2}


@pytest.fixture
def ship():
    return {
        "lat": 60.34, "lon": -172.69, "utc": "2026-06-23T07:42:16Z",
        "sog_kt": 10, "cog": 185, "heading": 215,
        "_age_hours": 0.3, "_stale": False, "_source": "mfphub (public AIS)",
    }


@pytest.fixture
def gi_html():
    return (
        '<p hidden id="db-data">[{"predicted_time":"2026-06-24","kp":"2"}]</p>'
        '<p hidden id="db-data-27-day">[{"predicted_time":"2026-06-24","kp":"2"},'
        '{"predicted_time":"2026-07-10","kp":"3"}]</p>'
        '<p hidden id="db-data-3-day">[{"id":"1","kp":"1.67","predicted_time":"2026-06-24 00:00:00"},'
        '{"id":"2","kp":"4.0","predicted_time":"2026-06-24 21:00:00"},'
        '{"id":"3","kp":"3.33","predicted_time":"2026-06-25 03:00:00"}]</p>'
    )
