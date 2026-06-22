#!/usr/bin/env bash
# Update the deployed bot to the latest commit on GitHub, then restart.
# Pulls the public bot repo (no auth). Ignored files (.env, .venv, ship-position.py, state.json)
# are untouched by the hard reset. Run as a sudo-capable user:  bash /opt/aurora-bot/deploy/update.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aurora-bot}"
APP_USER="${APP_USER:-aurora}"
BOT_REF="${BOT_REF:-main}"

echo "==> pulling origin/$BOT_REF into $APP_DIR"
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --depth 1 origin "$BOT_REF"
OLD="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BOT_REF"
NEW="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"

echo "==> $OLD -> $NEW; syncing deps"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> restarting service"
sudo systemctl restart aurora-bot
echo "done. journalctl -u aurora-bot -f to verify."
