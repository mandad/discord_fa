"""Configuration loaded from environment / .env.

Only DISCORD_TOKEN and CHANNEL_ID are required. Ship position comes from the public
mfphub AIS feed (no secret), so SHIP_SCRIPT_PATH just needs to point at ship-position.py.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- required secrets ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0") or "0")

# --- optional, with sensible defaults ---
SHIP_SCRIPT_PATH = os.environ.get(
    "SHIP_SCRIPT_PATH",
    "/mnt/c/Users/damia/OneDrive/Documents/LLM_Land/scripts/ship-position.py",
)
SHIP_NAME = os.environ.get("SHIP_NAME", "FAIRWEATHER")
KP_THRESHOLD = float(os.environ.get("KP_THRESHOLD", "4"))
# Minimum OVATION aurora visibility (%) at the ship for the hourly post to publish.
MIN_AURORA_PCT = float(os.environ.get("MIN_AURORA_PCT", "1"))
DAILY_POST_UTC = int(os.environ.get("DAILY_POST_UTC", "18"))  # hour (UTC) for the daily prediction
# Restrict slash-command sync to one guild for instant availability (optional).
GUILD_ID = int(os.environ.get("GUILD_ID", "0") or "0")

STATE_PATH = Path(os.environ.get("STATE_PATH", str(Path(__file__).resolve().parent / "state.json")))


def require(name: str, value) -> None:
    if not value:
        raise SystemExit(f"missing required config: {name} (set it in .env)")
