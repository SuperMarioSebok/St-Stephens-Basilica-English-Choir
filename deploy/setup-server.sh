#!/usr/bin/env bash
# One-time setup of Basilica Voice Coach on a fresh Ubuntu 24.04 server.
#
#   sudo bash setup-server.sh choir-practice.duckdns.org
#
# What it does: swap (small servers), firewall, automatic security updates, FluidSynth,
# Caddy (automatic HTTPS), a 'bvc' service user, the app from GitHub via a read-only
# deploy key, two systemd services (web + audio worker) and a nightly backup.
set -euo pipefail

DOMAIN="${1:?Usage: sudo bash setup-server.sh <domain-name>}"
REPO="${REPO:-https://github.com/SuperMarioSebok/St-Stephens-Basilica-English-Choir.git}"
BASE=/opt/bvc
APP=$BASE/app
DATA=$BASE/data

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo"; exit 1; }
. /etc/os-release
[ "${VERSION_ID:-}" = "24.04" ] || echo "Warning: tested for Ubuntu 24.04, this is ${PRETTY_NAME:-unknown}"

echo "== Swap (helps 1-2 GB servers build the frontend)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "== Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3-venv python3-pip nodejs npm fluidsynth fluid-soundfont-gm ffmpeg fonts-dejavu-core \
  caddy ufw unattended-upgrades sqlite3
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== Firewall: only SSH and web"
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

echo "== Service user and folders"
id bvc >/dev/null 2>&1 || useradd --system --home-dir $BASE --shell /bin/bash bvc
mkdir -p $BASE/.ssh $DATA /var/backups/bvc
chown -R bvc:bvc $BASE && chmod 700 $BASE/.ssh $DATA

echo "== Get the code"
if [ ! -d $APP/.git ]; then
  if [[ "$REPO" == git@* ]]; then
    # Private repository: use a read-only deploy key.
    [ -f $BASE/.ssh/id_ed25519 ] || sudo -u bvc ssh-keygen -q -t ed25519 -N "" -C "bvc-server" -f $BASE/.ssh/id_ed25519
    sudo -u bvc bash -c "ssh-keyscan -t ed25519 github.com >> $BASE/.ssh/known_hosts 2>/dev/null"
    echo "Add this key on GitHub: repository > Settings > Deploy keys (leave write access UNTICKED):"
    cat $BASE/.ssh/id_ed25519.pub
    read -rp "Press Enter once the key is added... "
  fi
  sudo -u bvc git clone -q "$REPO" $APP
fi

echo "== Backend"
sudo -u bvc python3 -m venv $APP/backend/.venv
sudo -u bvc $APP/backend/.venv/bin/pip install -q -r $APP/backend/requirements.txt

echo "== Frontend build"
cd $APP/frontend && sudo -u bvc npm ci --no-audit --no-fund -q && sudo -u bvc npx vite build

echo "== Services"
install -m 644 $APP/deploy/bvc-web.service /etc/systemd/system/bvc-web.service
install -m 644 $APP/deploy/bvc-worker.service /etc/systemd/system/bvc-worker.service
systemctl daemon-reload
systemctl enable --now bvc-web bvc-worker

echo "== HTTPS with Caddy (no access log, so feedback times are not logged)"
sed "s/__DOMAIN__/$DOMAIN/" $APP/deploy/Caddyfile > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "== Nightly backup at 03:15, keeps 14 days"
cat > /etc/cron.d/bvc-backup <<CRON
15 3 * * * root sqlite3 $DATA/bvc.sqlite3 ".backup /var/backups/bvc/db-\$(date +\%F).sqlite3" && tar -czf /var/backups/bvc/storage-\$(date +\%F).tgz -C $DATA storage && find /var/backups/bvc -mtime +14 -delete
CRON

echo
echo "Done. Open https://$DOMAIN in a minute (the certificate is issued on first visit)."
echo "Create accounts with:  sudo bash $APP/deploy/add-user.sh <username> <singer|voice_lead|director> [S|A|T|B]"
