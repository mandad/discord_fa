#!/usr/bin/env bash
# One-shot VM install for the aurora bot (Debian/Ubuntu).
# Run from the checked-out project dir:  bash deploy/setup.sh
#
# Prereqs on the VM:
#   - You are a sudo-capable user.
#   - GitHub auth available to fetch ship-position.py from the private repo, i.e. EITHER
#       gh auth login        (interactive), OR
#       export GH_TOKEN=...   (a token with read access to mandad/life-manager)
# The bot itself is then run by a dedicated, non-login 'aurora' service user via systemd.
set -euo pipefail

APP_DIR=/opt/aurora-bot
APP_USER=aurora
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # project root (parent of deploy/)

echo "==> [1/6] system packages (python venv, gh, git, curl)"
sudo apt-get update -qq
if ! command -v gh >/dev/null 2>&1; then
  # GitHub CLI apt repo
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
  sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
  sudo apt-get update -qq
fi
sudo apt-get install -y python3-venv python3-full git curl gh

echo "==> [2/6] service user + app dir"
id "$APP_USER" &>/dev/null || sudo useradd -r -m -d "$APP_DIR" "$APP_USER"
sudo mkdir -p "$APP_DIR"
sudo cp -r "$SRC_DIR"/. "$APP_DIR"/
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> [3/6] fetch ship-position.py via GitHub auth (your gh login / GH_TOKEN)"
# Run as the invoking user so it uses YOUR gh auth, then place + chown to the service user.
TMP_SHIP="$(mktemp)"
bash "$SRC_DIR/deploy/fetch-ship-position.sh" "$TMP_SHIP"
sudo cp "$TMP_SHIP" "$APP_DIR/ship-position.py"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR/ship-position.py"
rm -f "$TMP_SHIP"

echo "==> [4/6] python venv + deps"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> [5/6] .env scaffold"
if [ ! -f "$APP_DIR/.env" ]; then
  sudo -u "$APP_USER" cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi
# point the bot at the fetched script (idempotent)
if ! sudo grep -q '^SHIP_SCRIPT_PATH=' "$APP_DIR/.env"; then
  echo "SHIP_SCRIPT_PATH=$APP_DIR/ship-position.py" | sudo tee -a "$APP_DIR/.env" >/dev/null
fi
sudo chmod 600 "$APP_DIR/.env"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR/.env"

echo "==> [6/6] systemd service (enabled, NOT started yet)"
sudo cp "$APP_DIR/deploy/aurora-bot.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aurora-bot

cat <<EOF

Done. Final steps:
  1. Edit secrets:   sudo -u $APP_USER nano $APP_DIR/.env      # set DISCORD_TOKEN, CHANNEL_ID
  2. Smoke test:     sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/swpc.py
                     sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/ship.py
  3. Start:          sudo systemctl start aurora-bot
  4. Logs:           journalctl -u aurora-bot -f     # expect "logged in as ..." + "commands synced"

To refresh ship-position.py later:
  bash $APP_DIR/deploy/fetch-ship-position.sh /tmp/sp.py && sudo cp /tmp/sp.py $APP_DIR/ship-position.py && sudo systemctl restart aurora-bot
EOF
