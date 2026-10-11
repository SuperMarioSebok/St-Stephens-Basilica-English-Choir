#!/usr/bin/env bash
# Pull the latest code from GitHub and restart:  sudo bash /opt/bvc/app/deploy/update.sh
set -euo pipefail
# Practice videos need FFmpeg and fonts (no-op if already installed).
dpkg -s ffmpeg fonts-dejavu-core >/dev/null 2>&1 || apt-get install -y -q ffmpeg fonts-dejavu-core
cd /opt/bvc/app
sudo -u bvc git pull --ff-only
sudo -u bvc backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo -u bvc npm ci --no-audit --no-fund -q && sudo -u bvc npx vite build
systemctl restart bvc-web bvc-worker
echo "Updated to $(git -C /opt/bvc/app log --oneline -1)"
