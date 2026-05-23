# On-device firmware (ESPHome)

Production **Device Connect** runs on the **ESP32-S3** in Home Assistant Voice Preview Edition, not on your Mac.

## Repository tree

```text
firmware/
├── README.md
├── secrets.yaml.example
├── components/device_connect/          ← ESPHome external component (stub)
└── esphome/
    ├── device-connect-voice.full.yaml  ← flashable merged Voice PE + Device Connect
    ├── device-connect-voice.overlay.yaml
    ├── UPSTREAM.lock
    └── README.md
```

| Artifact | Flashable as Voice PE? | Device Connect on mesh? |
|----------|------------------------|-------------------------|
| `device-connect-voice.overlay.yaml` alone | **No** | Stub only |
| `device-connect-voice.full.yaml` | **Yes** | After Phase 1–2 wiring |
| Python `--sim --portal` | N/A (Mac) | Yes (simulated) |

## Flash (USB) — Option B

```bash
cd ~/src/device-connect-voice
cp firmware/secrets.yaml.example firmware/esphome/secrets.yaml   # edit Wi-Fi
./scripts/flash_firmware.sh config
./scripts/flash_firmware.sh compile
DEVICE=/dev/cu.usbmodem1101 ./scripts/flash_firmware.sh upload
```

Requires **ESPHome ≥ 2026.5.0**. Regenerate merged YAML: `./scripts/prepare_firmware.sh`.

## STT on device

| Capability | Where it runs |
|------------|----------------|
| Wake word | ESP32 (`micro_wake_word`) |
| Mic capture / AEC | XMOS + ESP32 I2S |
| Whisper-scale STT | **Not on ESP32** — Wyoming / Assist on LAN or HA host |
| Device Connect RPCs | ESP32 (`device_connect` + zenoh-pico, in progress) |

## Portal credentials (must be on the device)

For **portal** operation the ESP32 must hold device NATS credentials (JWT + NKey from `erivan01-voice.creds.json`), not only your laptop. Phase 2 firmware reads `secrets.yaml` / NVS and connects to `nats://portal.deviceconnect.dev:4222`.

See [../docs/protocol.md](../docs/protocol.md) for subject names.
