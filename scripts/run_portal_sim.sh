#!/usr/bin/env bash
# Run the reference driver on the portal (sim transport until ESP32 firmware is live).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CREDS="${NATS_CREDENTIALS_FILE:-$HOME/Downloads/erivan01-voice.creds.json}"
cd "$ROOT"
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export NATS_CREDENTIALS_FILE="$CREDS"
exec python -m device_connect_voice --sim --portal --portal-credentials "$CREDS"
