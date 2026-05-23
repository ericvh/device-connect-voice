#!/usr/bin/env bash
# Regenerate firmware/esphome/device-connect-voice.full.yaml from upstream Voice PE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/vendor_zenoh_pico.sh"
exec python3 "$ROOT/scripts/merge_voice_pe_yaml.py" "$@"
