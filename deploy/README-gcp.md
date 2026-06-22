# Deploy the aurora bot on Google Cloud (Compute Engine)

Persistent `discord.py` gateway bot → run it on a small always-on VM with systemd.
A free-tier **e2-micro** is plenty (Discord traffic is tiny). Outbound only — no inbound
ports, so no firewall rules needed.

`ship-position.py` lives in your **private** repo `mandad/life-manager`. The VM pulls it with
**your GitHub auth** (the `gh` CLI), so no copying from your PC.

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

## 2. Get the bot code onto the VM

`git clone` your bot repo, or copy from your PC:
```bash
# from the discord_fa project dir on your PC:
gcloud compute scp --recurse . aurora-bot:~/discord_fa --zone=us-central1-a
```

## 3. Authenticate GitHub (to pull ship-position.py from the private repo)

On the VM, do **one** of:
```bash
gh auth login                 # interactive (device code), OR
export GH_TOKEN=ghp_xxx       # a token with read access to mandad/life-manager
```
A fine-grained, read-only token scoped to just `life-manager` (Contents: Read) is the
least-privilege option; your existing classic token also works.

## 4. Run the one-shot installer

```bash
cd ~/discord_fa
bash deploy/setup.sh
```
`setup.sh` installs deps + `gh`, creates the `aurora` service user, copies the app to
`/opt/aurora-bot`, **fetches `ship-position.py` via `deploy/fetch-ship-position.sh`** (your gh
auth), builds the venv, scaffolds `.env` with `SHIP_SCRIPT_PATH` set, and installs+enables the
systemd unit (it does **not** start the bot yet — no token in `.env` would crash-loop).

## 5. Secrets, smoke test, start

```bash
sudo -u aurora nano /opt/aurora-bot/.env          # set DISCORD_TOKEN, CHANNEL_ID
sudo -u aurora /opt/aurora-bot/.venv/bin/python /opt/aurora-bot/swpc.py
sudo -u aurora /opt/aurora-bot/.venv/bin/python /opt/aurora-bot/ship.py
sudo systemctl start aurora-bot
journalctl -u aurora-bot -f                        # expect "logged in as ..." + "commands synced"
```

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
