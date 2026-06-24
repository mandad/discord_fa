"""Discord-facing logic, exercised offline (no gateway, no token).

Uses a fake channel to capture what the bot would send, and patches the network/darkness so the
alert path is deterministic.
"""
import discord

import bot
import config


class FakeChannel:
    def __init__(self):
        self.sends = []

    async def send(self, **kwargs):
        self.sends.append(kwargs)


def test_aurora_slash_command_registered():
    names = {c.name for c in bot.bot.tree.get_commands()}
    assert "aurora" in names


def test_setup_hook_is_custom():
    # one-time setup lives in setup_hook (not on_ready), so reconnects don't re-sync
    assert bot.bot.setup_hook.__module__ == "bot"


async def _run_alert(monkeypatch, tmp_path, kp_rows, ship):
    ch = FakeChannel()
    monkeypatch.setattr(bot, "_channel", lambda: ch)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("solar.is_dark_nautical", lambda *a, **k: True)  # force "dark" windows

    async def fake_gi(_session):
        return {"2026-06-25": 4, "2026-06-26": 5}
    monkeypatch.setattr(bot.gi, "fetch_daily", fake_gi)
    return ch


async def test_maybe_alert_sends_everyone_with_viewlines(monkeypatch, tmp_path, kp_rows, ship):
    ch = await _run_alert(monkeypatch, tmp_path, kp_rows, ship)
    await bot.maybe_alert(kp_rows, ship)

    assert len(ch.sends) == 1
    sent = ch.sends[0]
    assert sent["content"] == "@everyone"
    assert sent["allowed_mentions"].everyone is True
    # main alert embed + NOAA tonight + NOAA tomorrow = 3 embeds, all with images.
    embeds = sent["embeds"]
    assert len(embeds) == 3
    assert all(e.image.url for e in embeds)
    assert "Alaska_" in embeds[0].image.url


async def test_maybe_alert_dedupes_second_call(monkeypatch, tmp_path, kp_rows, ship):
    ch = await _run_alert(monkeypatch, tmp_path, kp_rows, ship)
    await bot.maybe_alert(kp_rows, ship)
    await bot.maybe_alert(kp_rows, ship)   # same windows -> no second post
    assert len(ch.sends) == 1


async def test_maybe_alert_suppressed_when_daylight(monkeypatch, tmp_path, kp_rows, ship):
    ch = await _run_alert(monkeypatch, tmp_path, kp_rows, ship)
    monkeypatch.setattr("solar.is_dark_nautical", lambda *a, **k: False)  # all windows in daylight
    await bot.maybe_alert(kp_rows, ship)
    assert ch.sends == []
