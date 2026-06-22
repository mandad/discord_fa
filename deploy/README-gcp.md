# Deploy the aurora bot on Google Cloud (Compute Engine)

Persistent `discord.py` gateway bot → run it on a small always-on VM with systemd.
A free-tier **e2-micro** is plenty (Discord traffic is tiny). Outbound only — no inbound
ports, so no firewall rules needed.

The bot code is the **public** repo `mandad/discord_fa` — the VM installs it as a `git`
checkout and updates with `git pull` (no auth). `ship-position.py` lives in your **private**
repo `mandad/life-manager`; the VM pulls that one with **your GitHub auth** (`gh` CLI).

## 1. Create the VM (free-tier eligible region)

```bash
gcloud compute instances create aurora-bot \
  --machine-type=e2-micro \
  --zone=us-central1-a \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=10GB
gcloud compute ssh aurora-bot --zone=us-central1-a
```
(Free tier: one non-preemptible e2-micro/month in `us-west1`, `us-central1`, or `us-east1`,
≤30 GB standard PD.)

## 2. Authenticate GitHub (for the private ship-position.py source)

On the VM, do **one** of:
```bash
gh auth login                 # interactive (device code), OR
export GH_TOKEN=ghp_xxx       # a token with read access to mandad/life-manager
```
A fine-grained, read-only token scoped to just `life-manager` (Contents: Read) is the
least-privilege option; your existing classic token also works. (The bot repo is public, so
cloning/updating it needs no auth.)

## 3. Run the one-shot installer

The bot repo is public, so you can run the installer straight from it — no manual clone:
```bash
curl -fsSL https://raw.githubusercontent.com/mandad/discord_fa/main/deploy/setup.sh | bash
```
`setup.sh` installs deps + `gh`, creates the `aurora` service user, **`git clone`s
`mandad/discord_fa` into `/opt/aurora-bot`** (a checkout it can later `git pull`),
**fetches `ship-position.py` via your gh auth**, builds the venv, scaffolds `.env` with
`SHIP_SCRIPT_PATH` set, and installs+enables the systemd unit (it does **not** start the bot
yet — an empty token would crash-loop). Re-running `setup.sh` updates the checkout in place.

## 4. Secrets, smoke test, start

```bash
sudo -u aurora nano /opt/aurora-bot/.env          # set DISCORD_TOKEN, CHANNEL_ID
sudo -u aurora /opt/aurora-bot/.venv/bin/python /opt/aurora-bot/swpc.py
sudo -u aurora /opt/aurora-bot/.venv/bin/python /opt/aurora-bot/ship.py
sudo systemctl start aurora-bot
journalctl -u aurora-bot -f                        # expect "logged in as ..." + "commands synced"
```

## Updating the bot code (pull from GitHub)
After you push changes to `mandad/discord_fa`, update the VM:
```bash
bash /opt/aurora-bot/deploy/update.sh      # git pull origin/main + sync deps + restart
```
The hard reset leaves ignored files (`.env`, `.venv/`, `ship-position.py`, `state.json`) intact.

## Updating ship-position.py later
```bash
bash /opt/aurora-bot/deploy/fetch-ship-position.sh /tmp/sp.py \
  && sudo cp /tmp/sp.py /opt/aurora-bot/ship-position.py \
  && sudo systemctl restart aurora-bot
```

## Notes
- **No firewall changes**: the gateway connection is outbound; the bot needs no inbound ports.
- **Secrets**: `.env` (chmod 600) is fine for one VM. Harden the bot token with Secret Manager
  if you like; the GitHub token only needs read access to the one repo.
- **Cost**: free-tier region + e2-micro ≈ free; polling egress is negligible.
- `Restart=always` recovers crashes; `systemctl enable` recovers VM reboots.

## Running locally (any machine)
The default `SHIP_SCRIPT_PATH` in `config.py` points at the Windows mount, so your PC works
as-is. On a machine without that file, pull it with your gh auth and point the bot at it:
```bash
bash deploy/fetch-ship-position.sh ./ship-position.py
# then in .env:  SHIP_SCRIPT_PATH=./ship-position.py
```
