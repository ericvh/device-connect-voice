#!/usr/bin/env bash
# Vendor zenoh-pico for ESP-IDF / ESPHome (pinned release).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/firmware/vendor/zenoh-pico"
REF="${ZENOH_PICO_REF:-1.9.0}"
REPO="https://github.com/eclipse-zenoh/zenoh-pico.git"

if [[ -d "$DEST/.git" ]]; then
  echo "Updating $DEST @ $REF"
  git -C "$DEST" fetch --tags origin
  git -C "$DEST" checkout "$REF"
else
  echo "Cloning zenoh-pico $REF → $DEST"
  mkdir -p "$(dirname "$DEST")"
  git clone --depth 1 --branch "$REF" "$REPO" "$DEST"
fi

echo "zenoh-pico ready at $DEST ($(git -C "$DEST" rev-parse --short HEAD))"
