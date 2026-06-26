#!/usr/bin/env bash
# Post-deploy health check for the aurora bot. Run on the VM (sudo-capable user or the service user):
#   bash /opt/aurora-bot/deploy/healthcheck.sh
# Remotely from your machine:
#   gcloud compute ssh aurora-bot --project=aurora-bot --zone=<zone> \
#     --command='bash /opt/aurora-bot/deploy/healthcheck.sh'
#
# Checks: systemd unit active, startup markers + recent errors in the journal, and live smoke
# tests of the feeds (SWPC+OVATION, ship position, UAF GI). Exit 0 = PASS, 1 = FAIL.
set -uo pipefail

APP_DIR="${APP_DIR:-/opt/aurora-bot}"
APP_USER="${APP_USER:-aurora}"
PY="$APP_DIR/.venv/bin/python"
fail=0

# run smoke tests as the service user (loads its .env), unless we already are that user
if [ "$(id -un)" = "$APP_USER" ]; then RUN=(bash -c); else RUN=(sudo -u "$APP_USER" bash -c); fi

say() { printf '\n=== %s ===\n' "$1"; }

say "systemd service"
if systemctl list-unit-files aurora-bot.service >/dev/null 2>&1; then
  if systemctl is-active --quiet aurora-bot; then
    echo "active: yes"
  else
    echo "active: NO  -> sudo systemctl start aurora-bot"; fail=1
  fi
  systemctl status aurora-bot --no-pager -n 0 2>/dev/null | sed -n '1,3p'
else
  echo "(no systemd unit installed — skipping service check)"
fi

say "startup markers (whole journal)"
# Capture once: piping journalctl into `grep -q` trips SIGPIPE under `set -o pipefail`
# (grep closes the pipe on first match) and would report a false "not seen".
jrnl=$(journalctl -u aurora-bot --no-pager 2>/dev/null)
grep -qE "ready as "             <<<"$jrnl" && echo "logged in:     yes" || echo "logged in:     not seen"
grep -qE "slash commands synced" <<<"$jrnl" && echo "commands sync: yes" || echo "commands sync: not seen"
errs=$(journalctl -u aurora-bot -n 300 --no-pager 2>/dev/null | grep -cE "Traceback|ERROR")
echo "errors (last 300 log lines): $errs"

say "recent logs (last 20)"
journalctl -u aurora-bot -n 20 --no-pager 2>/dev/null || echo "(journal unavailable)"

smoke() { # name script fatal(1/0)
  local name="$1" script="$2" fatal="$3" out rc
  say "smoke: $name"
  out=$("${RUN[@]}" "cd '$APP_DIR' && '$PY' '$script'" 2>&1); rc=$?
  echo "$out" | tail -6
  if [ "$rc" -eq 0 ]; then
    echo "[$name] OK"
  else
    echo "[$name] FAILED (rc=$rc)"
    [ "$fatal" = "1" ] && fail=1
  fi
}

smoke "SWPC Kp + OVATION" swpc.py 1
smoke "ship position"     ship.py 1
smoke "UAF GI forecast"   gi.py   0   # GI is often blocked from cloud IPs; non-fatal

say "result"
if [ "$fail" = "0" ]; then echo "HEALTH: PASS"; else echo "HEALTH: FAIL"; fi
exit "$fail"
