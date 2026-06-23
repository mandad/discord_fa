# Aurora Forecast Bot — NOAA Ship Fairweather

Discord bot that tracks the live position of NOAA Ship Fairweather and posts aurora forecasts
for that position, pinging **@everyone** whenever the forecast planetary **Kp index reaches ≥ 4**.

- **Daily** post: the Kp / aurora *prediction* (3-day predicted Kp peaks + aurora % at the ship),
  with each window timestamped in UTC **and** ship-local time. Local time uses the ship's actual
  civil timezone (via `timezonefinder`, DST-aware), defaulting to Alaska (`America/Anchorage`)
  over open ocean or when no position is available.
- **Hourly** post: *observed* conditions (current aurora % at the ship + observed Kp), times in
  ship-local time. Posts only when aurora chance at the ship is ≥ `MIN_AURORA_PCT` (default 1%).
  Omits SOG/COG (unreliable while stationary).
- **`/aurora`** slash command: current conditions on demand.
- **Alert**: `@everyone` on each new forecast window with Kp ≥ `KP_THRESHOLD`, **but only if the
  sky at the ship is darker than nautical twilight** (sun below −12°) at that time — so daylight
  windows (e.g. high-latitude summer) don't ping. Deduped per window; times shown UTC + local.
  Each alert embeds the **UAF Geophysical Institute Alaska viewline diagram** for that Kp, the
  **NOAA SWPC predicted viewline** images (tonight + tomorrow night), and a cross-reference of
  our SWPC forecast vs GI's 3-day forecast.
- **Cross-reference**: the daily prediction and alerts compare our SWPC Kp against the University
  of Alaska Geophysical Institute forecast and link the GI page.

## Data sources (all public, no key)

| What | Source |
|------|--------|
| Ship position | `ship-position.py` → public mfphub AIS feed (no secret) |
| Kp forecast | `services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json` |
| GI forecast + viewline | `gi.alaska.edu/monitors/aurora-forecast` (3-day Kp JSON + `idl_graphics/ak/Alaska_{Kp}.png`) |
| NOAA predicted viewline | `services.swpc.noaa.gov/experimental/images/aurora_dashboard/{tonights,tomorrow_nights}_static_viewline_forecast.png` |
| Aurora nowcast | `services.swpc.noaa.gov/json/ovation_aurora_latest.json` (OVATION, % visible per 1° cell) |

## Setup

### 1. Create the Discord bot
1. https://discord.com/developers/applications → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token. (No privileged intents needed.)
3. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`; bot permissions
   **Send Messages**, **Embed Links**, **Mention Everyone**. Open the URL, invite to your server.
4. In Discord (Developer Mode on), right-click the target channel → **Copy Channel ID**.

### 2. Configure
```bash
cd /mnt/c/Users/damia/OneDrive/Documents/code/discord_fa
cp .env.example .env          # then edit: DISCORD_TOKEN, CHANNEL_ID (and optionally GUILD_ID)
python3 -m venv .venv         # deps live in a project venv (PEP 668 system python is locked)
.venv/bin/python -m pip install -r requirements.txt
```

### 3. Run / verify
```bash
.venv/bin/python swpc.py     # smoke test: Kp + OVATION + aurora % at a test point
.venv/bin/python ship.py     # smoke test: parsed ship fix
.venv/bin/python bot.py      # start the bot
```
`/aurora` should appear in the server (instant if `GUILD_ID` is set; global sync can take ~1h).
To test the alert path, set `KP_THRESHOLD=0` in `.env`, start the bot, confirm one `@everyone`
alert posts and is **not** repeated on the next hourly loop, then restore `KP_THRESHOLD=4`.

## Keep alive with Windows Task Scheduler

The bot is a long-running process; Task Scheduler launches it and restarts it if it dies.

1. **Task Scheduler → Create Task** (not basic).
2. **General**: "Run whether user is logged on or not" optional; "Run with highest privileges" not required.
3. **Triggers** → New → **At log on** (and/or **At startup**).
4. **Actions** → New → Program: `powershell.exe`
   Arguments: `-ExecutionPolicy Bypass -File "C:\Users\damia\OneDrive\Documents\code\discord_fa\start-bot.ps1"`
5. **Settings**: check **"If the task fails, restart every"** `1 minute`, attempts `999`; and
   **"Run task as soon as possible after a scheduled start is missed."**

`start-bot.ps1` runs `wsl.exe -d Ubuntu -- bash -lc '... python3 bot.py'`. Edit the distro name
in that file if yours isn't `Ubuntu` (check with `wsl -l -q`).

## Files
| File | Role |
|------|------|
| `bot.py` | entrypoint: loops, `/aurora`, alert posting |
| `swpc.py` | NOAA SWPC fetch + Kp/aurora helpers |
| `ship.py` | wraps `ship-position.py` subprocess |
| `forecast.py` | builds the Discord embeds |
| `alerts.py` | Kp ≥ threshold dedupe (`state.json`) |
| `config.py` | `.env` loading |
