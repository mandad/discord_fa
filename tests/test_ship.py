import asyncio
import json

import pytest

import ship

SAMPLE = {"lat": 60.34, "lon": -172.69, "utc": "2026-06-23T07:42:16Z",
          "_age_hours": 0.3, "_stale": False}


class FakeProc:
    def __init__(self, out=b"", err=b"", rc=0, delay=0.0):
        self._out, self._err, self.rc, self.delay = out, err, rc, delay
        self.returncode = None
        self.killed = False

    async def communicate(self):
        if not self.killed and self.delay:
            await asyncio.sleep(self.delay)
        self.returncode = self.rc
        return self._out, self._err

    def kill(self):
        self.killed = True


def _patch(monkeypatch, proc):
    async def fake_create(*a, **k):
        return proc
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create)


async def test_get_position_parses_json(monkeypatch):
    _patch(monkeypatch, FakeProc(out=json.dumps(SAMPLE).encode(), rc=0))
    data = await ship.get_position("dummy.py")
    assert data["lat"] == 60.34 and data["_stale"] is False


async def test_get_position_nonzero_exit_raises(monkeypatch):
    _patch(monkeypatch, FakeProc(err=b"boom", rc=2))
    with pytest.raises(RuntimeError, match="ship-position.py failed"):
        await ship.get_position("dummy.py")


async def test_get_position_bad_json_raises(monkeypatch):
    _patch(monkeypatch, FakeProc(out=b"not json", rc=0))
    with pytest.raises(RuntimeError, match="could not parse"):
        await ship.get_position("dummy.py")


async def test_get_position_timeout_raises(monkeypatch):
    _patch(monkeypatch, FakeProc(out=json.dumps(SAMPLE).encode(), rc=0, delay=0.3))
    with pytest.raises(RuntimeError, match="timed out"):
        await ship.get_position("dummy.py", timeout=0.05)
