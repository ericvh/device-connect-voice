# Changelog

All notable changes to `device-connect-voice` are documented in this file.

## [Unreleased]

### Added

- Tracked flashable `firmware/esphome/device-connect-voice.full.yaml` (upstream Voice PE + Device Connect) with `scripts/merge_voice_pe_yaml.py` and `UPSTREAM.lock`.
- `scripts/flash_firmware.sh` for config / compile / upload; merge injects Wi-Fi secrets for ESPHome 2026.5+.
- Expanded `device_connect` ESPHome component: JSON-RPC dispatch for whisper RPCs, Voice PE entity bindings, STT/wake hooks.
- Zenoh-pico LAN transport: `.cmd` queryable, event/heartbeat publish, peer or router mode (`scripts/vendor_zenoh_pico.sh`, `scripts/test_zenoh_voice_rpc.py`).
- Comprehensive [README.md](README.md) with architecture, design decisions, full RPC/event catalog, and portal setup.
- microWakeWord RPCs (`list_wake_word_models`, `enable_wake_word_model`, `set_wake_word_sensitivity`, …) and `wake_word_detected` event.
- LED ring RPCs (`set_led_color`, `set_led_effect`, `release_led_control`, etc.) and `led_changed` event.
- Portal defaults for `~/Downloads/erivan01-voice.creds.json` (`tenant` erivan01, `device_id` erivan01-voice).
- `device_connect_voice.mesh` helpers and `scripts/run_portal_sim.sh`.
- Center button, rotary dial (volume), and speaker/media RPCs plus `button_event` and `volume_changed`.
- Initial repository scaffold for on-device Device Connect on Home Assistant Voice PE.
- Python `VoiceWhisperDriver` with simulated ESP32 voice state (CI / RPC contract reference).
- CLI entry `device-connect-voice` with `--sim`, `--portal`, and LAN insecure modes.
- ESPHome external component `device_connect` (stub) and overlay YAML skeleton.
- Documentation: architecture, messaging subjects, firmware flash notes.
