# ESPHome configs in this repo

## Files


| File                                | Purpose                                                                      |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| `device-connect-voice.full.yaml`    | **Flashable** merged Voice PE + Device Connect (~1.9k lines, tracked in git) |
| `device-connect-voice.overlay.yaml` | Patch blocks fed into `scripts/merge_voice_pe_yaml.py`                       |
| `UPSTREAM.lock`                     | Upstream repo/ref pin when refreshing the full YAML                          |
| `secrets.yaml`                      | Local only (from `../secrets.yaml.example`) — never commit                   |


## Requirements

- **ESPHome ≥ 2026.5.0** (Voice PE upstream `min_version`; `brew upgrade esphome` on macOS)
- `firmware/esphome/secrets.yaml` with `wifi_ssid` / `wifi_password` (from `../secrets.yaml.example`)

## Flash (Option B — from this repo)

```bash
# repo root
cp firmware/secrets.yaml.example firmware/esphome/secrets.yaml   # edit Wi-Fi
./scripts/flash_firmware.sh config    # fast validate
./scripts/flash_firmware.sh compile   # first build downloads voice_kit + models (long)
DEVICE=/dev/cu.usbmodem1101 ./scripts/flash_firmware.sh upload
```

`device_connect` runs **JSON-RPC** on Voice PE hardware plus **zenoh-pico** when `zenoh_enabled: true` (see [../components/device_connect/README.md](../components/device_connect/README.md)).

Before first compile: `./scripts/vendor_zenoh_pico.sh`


| `zenoh_connect`        | Mode                     |
| ---------------------- | ------------------------ |
| `""` (default)         | Peer / LAN multicast D2D |
| `tcp/192.168.x.x:7447` | Client to Zenoh router   |


Test from Mac: `python scripts/test_zenoh_voice_rpc.py get_status`

## Refresh upstream Voice PE

When [home-assistant-voice-pe](https://github.com/esphome/home-assistant-voice-pe) changes:

```bash
# From repo root
./scripts/prepare_firmware.sh
git diff firmware/esphome/device-connect-voice.full.yaml
```

Edit `device-connect-voice.overlay.yaml` (or `scripts/merge_voice_pe_yaml.py`) if new upstream layout breaks the merge, then re-run the script and commit.

## Do not flash the overlay alone

`device-connect-voice.overlay.yaml` is a minimal skeleton for CI/component compile only. It omits `voice_kit`, `micro_wake_word`, `voice_assistant`, LEDs, and button/dial support.