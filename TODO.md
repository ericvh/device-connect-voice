# device-connect-voice — TODO

On-device [Device Connect](https://deviceconnect.dev) driver for **Home Assistant Voice Preview Edition** (Seeed / ESP32-S3 + XMOS). The production runtime is **ESPHome firmware** on the board; the Python package is the RPC contract reference and CI simulator.

## Phase 0 — scaffold (done)

- [x] Repository layout, `README.md`, `CHANGELOG.md`, `pyproject.toml`
- [x] Python `VoiceWhisperDriver` (sim transport) matching firmware RPC names
- [x] ESPHome `device_connect` component stub + overlay YAML skeleton
- [x] Smoke test `tests/smoke_sim_runtime.py` (Python 3.12 venv)
- [ ] Confirm serial port (`/dev/cu.usbmodem1101`) and chip with `esptool.py flash_id`

## Phase 1 — on-device LAN (D2D / Zenoh)

- [x] Publish flashable `firmware/esphome/device-connect-voice.full.yaml` (regenerate via `scripts/merge_voice_pe_yaml.py` / `UPSTREAM.lock`)
- [x] Integrate **zenoh-pico** in `firmware/components/device_connect` (ESP-IDF via `ZENOH_ESPIDF` + vendored lib)
- [x] Subscribe `device-connect.{tenant}.{device_id}.cmd` (queryable + subscriber), publish heartbeats + events
- [x] D2D: peer mode when `zenoh_connect` empty (multicast `udp/224.0.0.225:7447`); client mode for `tcp/host:7447`
- [ ] End-to-end LAN test: `scripts/test_zenoh_voice_rpc.py` against flashed board
- [x] Wake word RPC contract (`list_wake_word_models`, `enable_wake_word_model`, `wake_word_detected`, …)
- [x] Wire wake word RPCs to ESPHome: `micro_wake_word.*`, `wake_word_sensitivity`, `on_wake_word_detected` (C++ + YAML hooks)
- [x] Wire RPCs to ESPHome globals: `voice_assistant_phase`, mute, last transcript (`on_stt_end` → `dc_last_transcript`)
- [x] `start_listen` / `stop_listen` → `voice_assistant.request_start` / `request_stop` (in firmware RPC)
- [x] Emit `stt_event` / `wake_word_detected` / `volume_changed` / `led_changed` / `button_event` (logged; Zenoh publish TODO)

## Phase 2 — portal (NATS)

- [ ] Provision portal credentials onto device (NVS / `secrets.yaml`)
- [ ] ESP32 NATS client (or TLS MQTT bridge — document tradeoff)
- [ ] `registerDevice` + JWT auth against `portal.deviceconnect.dev`
- [ ] `local_zenoh` advertisement for hybrid portal + LAN invoke

## Phase 3 — STT stack on device

- [ ] Document: full **Whisper** on ESP32-S3 is not feasible; use **Wyoming** STT on LAN or Assist pipeline
- [ ] Optional: ESP-SR / microWakeWord-only mode without HA
- [ ] Optional: stream PCM to LAN Wyoming Whisper server; cache transcript on device

## Phase 4 — agent UX

- [ ] `AGENTS.md` (portal creds, `invoke_device` examples)
- [ ] MCP `device-connect` config snippet
- [ ] CI: `tests/smoke_sim_runtime.py` in GitHub Actions

## Decisions

| Topic | Choice |
|-------|--------|
| Primary runtime | ESPHome on ESP32-S3 |
| Python package | Contract + sim only (not Mac production path) |
| `device_type` | `whisper` |
| LAN transport | Zenoh-pico (target) |
| Portal transport | NATS (target) |
| STT | Voice Assistant / Wyoming; expose transcript via RPC |
