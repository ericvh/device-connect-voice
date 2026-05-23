# device_connect (ESPHome external component)

On-device **Device Connect** driver for Home Assistant Voice PE (`device_type: whisper`).

## What works

- **JSON-RPC 2.0** (`handle_rpc`) — same method names as `VoiceWhisperDriver` in Python.
- **ESPHome bindings** — `voice_assistant`, `micro_wake_word`, media, LEDs, mute, volume script, …
- **Zenoh-pico (Phase 1b)** when `zenoh_enabled: true`:
  - **Queryable + subscriber** on `device-connect/{tenant}/{device_id}/cmd`
  - **Publishes** `heartbeat`, `stt_event`, `wake_word_detected`, `volume_changed`, `led_changed`, `button_event`, …
  - **Peer mode** (empty `zenoh_connect`): multicast `udp/224.0.0.225:7447` for LAN D2D
  - **Client mode** (`zenoh_connect: tcp/192.168.x.x:7447`): connect to a Zenoh router

## Build

zenoh-pico is vendored before compile:

```bash
./scripts/vendor_zenoh_pico.sh   # firmware/vendor/zenoh-pico @ 1.9.0
./scripts/flash_firmware.sh compile
```

ESPHome sets `-DZENOH_ESPIDF` so zenoh-pico uses the ESP-IDF platform port (not Arduino).

## YAML

```yaml
device_connect:
  id: dc
  device_id: erivan01-voice
  tenant: erivan01
  zenoh_enabled: true
  zenoh_connect: ""              # peer/D2D, or tcp/10.0.0.1:7447 for router
```

## Test from laptop (same LAN)

```bash
pip install eclipse-zenoh

# Peer / multicast (matches empty zenoh_connect on device)
python scripts/test_zenoh_voice_rpc.py get_status

# Via Zenoh router
ZENOH_CONNECT=tcp/192.168.1.10:7447 python scripts/test_zenoh_voice_rpc.py get_voice_phase
```

## Files

| File | Role |
|------|------|
| `__init__.py` | Schema, bindings, zenoh-pico library link |
| `device_connect.cpp` | Setup, loop, mesh event routing |
| `device_connect_rpc.cpp` | RPC handlers |
| `device_connect_zenoh.cpp` | Zenoh session, queryable, publish |

## Not yet

- Portal NATS (Phase 2)
- `requestRegistration` over Zenoh registry subject
- Complex center-button press scripts (`double_press`, …)
