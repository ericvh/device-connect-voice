#!/usr/bin/env bash
# Compile and optionally upload device-connect-voice.full.yaml (Option B).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ESPHOME_DIR="$ROOT/firmware/esphome"
YAML="$ESPHOME_DIR/device-connect-voice.full.yaml"
SECRETS="$ESPHOME_DIR/secrets.yaml"
EXAMPLE="$ROOT/firmware/secrets.yaml.example"

usage() {
  cat <<EOF
Usage: $(basename "$0") [compile|upload|config]
  compile   Build firmware (default)
  config    Validate YAML only (fast)
  upload    Build and flash (set DEVICE=/dev/cu.usbmodem1101)

Environment:
  DEVICE    Serial port for upload (required for upload)
EOF
}

cmd="${1:-compile}"
if [[ "$cmd" == "-h" || "$cmd" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "$SECRETS" ]]; then
  echo "Creating $SECRETS from example — edit Wi-Fi / portal secrets before upload."
  cp "$EXAMPLE" "$SECRETS"
fi

# Voice PE upstream min_version (see device-connect-voice.full.yaml header)
need="2026.5.0"
have="$(esphome version 2>/dev/null | awk '{print $2}')"
if [[ -n "$have" ]] && [[ "$(printf '%s\n%s\n' "$need" "$have" | sort -V | head -1)" != "$need" ]]; then
  echo "ESPHome $have is older than required $need. Run: pip install -U 'esphome>=2026.5.0'"
  exit 1
fi

cd "$ESPHOME_DIR"
case "$cmd" in
  config)
    esphome config "$YAML"
    ;;
  compile)
    esphome compile "$YAML"
    ;;
  upload)
    : "${DEVICE:?Set DEVICE=/dev/cu.usbmodem1101 (or pass as env)}"
    esphome upload "$YAML" --device "$DEVICE"
    ;;
  *)
    usage
    exit 1
    ;;
esac
