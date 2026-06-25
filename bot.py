"""Aurora forecast Discord bot for NOAA Ship Fairweather.

- Daily loop  : posts the Kp / aurora *prediction* for the ship's position.
- Hourly loop : posts *observed* conditions and checks the Kp >= threshold alert.
- /aurora     : on-demand current conditions for the ship's position.
- Alert       : @everyone when a new forecast window reaches Kp >= KP_THRESHOLD (deduped).

Persistent process; launched + kept alive by Windows Task Scheduler (see README).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

import alerts
import config
import forecast
import gi
import ship
import solar
import swpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aurora-bot")

intents = discord.Intents.default()  # guilds only; no privileged intents needed
bot = commands.Bot(command_prefix="!", intents=intents,
                   allowed_mentions=discord.AllowedMentions.none())


async def gather_data():
    """Fetch ship position + Kp forecast + OVATION concurrently."""
    async with aiohttp.ClientSession() as s:
        kp_rows, ov, ship_data = await asyncio.gather(
            swpc.fetch_kp_forecast(s),
            swpc.fetch_ovation(s),
            ship.get_position(),
        )
    grid, obs_time, _fc_time = ov
    return ship_data, kp_rows, grid, obs_time


def _channel():
    ch = bot.get_channel(config.CHANNEL_ID)
    if ch is None:
        log.error("channel %s not found / not cached", config.CHANNEL_ID)
    return ch


async def maybe_alert(kp_rows: list[dict], ship_data: dict):
    lat, lon = ship_data.get("lat"), ship_data.get("lon")

    def dark_enough(r: dict) -> bool:
        # Only alert windows when the sky at the ship is darker than nautical twilight;
        # if position is unknown, don't suppress.
        if lat is None or lon is None:
            return True
        return solar.is_dark_nautical(lat, lon, solar.parse_swpc(r["time_tag"]))

    state = alerts.load_state(config.STATE_PATH)
    new = alerts.check_kp_alert(kp_rows, state, config.KP_THRESHOLD, keep=dark_enough)
    if not new:
        return
    alerts.save_state(config.STATE_PATH, state)
    ch = _channel()
    if ch is None:
        return
    async with aiohttp.ClientSession() as s:
        gi_daily = await gi.fetch_daily(s)  # best-effort; {} on failure
    embed = forecast.build_alert_embed(new, ship_data, kp_rows, gi_daily, config.KP_THRESHOLD)
    embeds = [embed, *forecast.noaa_viewline_embeds()]  # GI Alaska viewline + NOAA tonight/tomorrow
    await ch.send(content="@everyone", embeds=embeds,
                  allowed_mentions=discord.AllowedMentions(everyone=True))
    log.info("posted Kp alert for %d window(s)", len(new))


@tasks.loop(time=time(hour=config.DAILY_POST_UTC, tzinfo=timezone.utc))
async def daily_prediction():
    try:
        ship_data, kp_rows, grid, obs_time = await gather_data()
        ch = _channel()
        if ch:
            async with aiohttp.ClientSession() as s:
                gi_daily = await gi.fetch_daily(s)  # best-effort; {} on failure
            embed = forecast.build_prediction_embed(ship_data, kp_rows, grid, obs_time,
                                                    config.KP_THRESHOLD, gi_daily=gi_daily)
            await ch.send(embed=embed)
            log.info("posted daily prediction")
        await maybe_alert(kp_rows, ship_data)
    except Exception:
        log.exception("daily_prediction failed")


@tasks.loop(hours=1)
async def hourly_observed():
    try:
        ship_data, kp_rows, grid, obs_time = await gather_data()
        lat, lon = ship_data.get("lat"), ship_data.get("lon")
        prob = swpc.aurora_prob_at(grid, lat, lon)
        # Aurora is only visible after nautical twilight, so don't post observed conditions while
        # it's still light at the ship (sun above -12 deg). Unknown position -> don't suppress.
        dark = lat is None or lon is None or solar.is_dark_nautical(lat, lon, datetime.now(timezone.utc))
        # Post the hourly update only when it's dark at the ship AND aurora chance clears the threshold.
        if dark and prob is not None and prob >= config.MIN_AURORA_PCT:
            ch = _channel()
            if ch:
                observed = swpc.latest_observed_kp(kp_rows)
                embed = forecast.build_observed_embed(ship_data, observed, grid, obs_time)
                await ch.send(embed=embed)
                log.info("posted hourly observed conditions (aurora %s%% >= %s%% at ship, dark)",
                         prob, config.MIN_AURORA_PCT)
        elif not dark:
            log.info("skipped hourly post (still light at ship; aurora %s%%)", prob)
        else:
            log.info("skipped hourly post (aurora %s%% < %s%% at ship)", prob, config.MIN_AURORA_PCT)
        # Alert check runs every hour regardless of local aurora probability.
        await maybe_alert(kp_rows, ship_data)
    except Exception:
        log.exception("hourly_observed failed")


@bot.tree.command(name="aurora", description="Current aurora odds at NOAA Ship Fairweather's position")
async def aurora_cmd(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        ship_data, kp_rows, grid, obs_time = await gather_data()
        observed = swpc.latest_observed_kp(kp_rows)
        embed = forecast.build_observed_embed(ship_data, observed, grid, obs_time)
        embed.add_field(name=f"Next Kp ≥ {config.KP_THRESHOLD:g} window",
                        value=forecast.next_window_line(kp_rows, ship_data, config.KP_THRESHOLD),
                        inline=False)
        await interaction.followup.send(embed=embed)
    except Exception:
        log.exception("/aurora failed")
        await interaction.followup.send("Could not fetch aurora data right now — try again shortly.")


async def _wait_until_ready():
    # Loops start in setup_hook (before the gateway is up); hold each first iteration until the
    # connection + cache are ready so channel lookups succeed.
    await bot.wait_until_ready()


hourly_observed.before_loop(_wait_until_ready)
daily_prediction.before_loop(_wait_until_ready)


@bot.event
async def setup_hook():
    # Runs ONCE at startup (not on every gateway reconnect), so command sync + loop start are
    # not repeated when the websocket drops and discord.py auto-reconnects.
    try:
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
        log.info("slash commands synced")
    except Exception:
        log.exception("command sync failed")
    if not hourly_observed.is_running():
        hourly_observed.start()
    if not daily_prediction.is_running():
        daily_prediction.start()


@bot.event
async def on_ready():
    # Fires on initial connect AND after every reconnect — keep it cheap (no API calls here).
    log.info("ready as %s (id %s)", bot.user, bot.user.id if bot.user else "?")


def main():
    config.require("DISCORD_TOKEN", config.DISCORD_TOKEN)
    config.require("CHANNEL_ID", config.CHANNEL_ID)
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
