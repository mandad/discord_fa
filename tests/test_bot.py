"""Discord-facing logic, exercised offline (no gateway, no token).

Uses a fake channel to capture what the bot would send, and patches the network/darkness so the
alert path is deterministic.
"""
import discord

import bot
import config
import solar


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

    async def fake_img(_session):
        return b"\xff\xd8\xff_fake_jpeg"
    monkeypatch.setattr(bot.swpc, "fetch_ovation_image", fake_img)
    return ch


async def test_maybe_alert_sends_everyone_with_viewlines(monkeypatch, tmp_path, kp_rows, ship):
    ch = await _run_alert(monkeypatch, tmp_path, kp_rows, ship)
    await bot.maybe_alert(kp_rows, ship)

    assert len(ch.sends) == 1
    sent = ch.sends[0]
    assert sent["content"] == "@everyone"
    assert sent["allowed_mentions"].everyone is True
    # alert embed + SWPC OVATION map + NOAA tonight + NOAA tomorrow = 4 embeds, all with images.
    embeds = sent["embeds"]
    assert len(embeds) == 4
    assert all(e.image.url for e in embeds)
    assert "Alaska_" in embeds[0].image.url                       # GI viewline on the alert embed
    assert embeds[1].image.url == "attachment://swpc_aurora_forecast.jpg"  # SWPC map attached
    assert len(sent["files"]) == 1                                # the attached SWPC image


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


async def _run_hourly(monkeypatch, kp_rows, grid, ship, *, dark, prob):
    ch = FakeChannel()
    monkeypatch.setattr(bot, "_channel", lambda: ch)

    async def fake_gather():
        return ship, kp_rows, grid, "2026-06-23T16:07:00Z"
    monkeypatch.setattr(bot, "gather_data", fake_gather)
    monkeypatch.setattr(bot.swpc, "aurora_prob_at", lambda *a, **k: prob)
    monkeypatch.setattr("solar.is_dark_nautical", lambda *a, **k: dark)

    async def noop_alert(*a, **k):  # alert path tested separately
        return None
    monkeypatch.setattr(bot, "maybe_alert", noop_alert)
    await bot.hourly_observed()
    return ch


async def test_hourly_posts_when_dark_and_above_threshold(monkeypatch, kp_rows, grid, ship):
    ch = await _run_hourly(monkeypatch, kp_rows, grid, ship, dark=True, prob=80)
    assert len(ch.sends) == 1


async def test_hourly_suppressed_in_daylight_even_if_high_prob(monkeypatch, kp_rows, grid, ship):
    # The reported bug: high Kp/aurora % but still light at the ship -> must NOT post.
    ch = await _run_hourly(monkeypatch, kp_rows, grid, ship, dark=False, prob=80)
    assert ch.sends == []


async def test_daily_posts_once_per_local_day(monkeypatch, tmp_path, kp_rows, grid, ship):
    # Two fires on the same Alaska date (e.g. after a DAILY_POST_UTC change + restart) must
    # produce a single daily post.
    ch = FakeChannel()
    monkeypatch.setattr(bot, "_channel", lambda: ch)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(solar, "default_local_date", lambda *a, **k: "2026-06-25")

    async def fake_gather():
        return ship, kp_rows, grid, "2026-06-25T16:07:00Z"
    monkeypatch.setattr(bot, "gather_data", fake_gather)

    async def fake_gi(_s):
        return {}
    monkeypatch.setattr(bot.gi, "fetch_daily", fake_gi)

    async def noop_alert(*a, **k):
        return None
    monkeypatch.setattr(bot, "maybe_alert", noop_alert)

    await bot.daily_prediction()
    await bot.daily_prediction()   # same AK date -> deduped
    assert len(ch.sends) == 1
