#!/usr/bin/env bash
# sudo bash add-user.sh elvis director        |  sudo bash add-user.sh lead_tenor voice_lead T
set -euo pipefail
USER_NAME="${1:?username}"; ROLE="${2:?singer|voice_lead|director}"; PART="${3:-}"
cd /opt/bvc/app/backend
sudo -u bvc .venv/bin/python -m bvc.cli --data-dir /opt/bvc/data add-user "$USER_NAME" --role "$ROLE" ${PART:+--part "$PART"}
