# Agent guide — Device Connect Voice (whisper)

Production device runs **ESPHome on the board**. Use this guide when the flashed firmware (or sim host) is on the Device Connect mesh.

## Connect

```python
from device_connect_agent_tools import connect, discover_devices, invoke_device

connect()  # requires NATS_CREDENTIALS_FILE for portal
whisper_devices = discover_devices(device_type="whisper")
```

Portal credentials: `~/Downloads/erivan01-voice.creds.json` → **tenant** `erivan01`, **device_id** `erivan01-voice`.

```python
from device_connect_voice.mesh import connect_mesh, disconnect_mesh, wait_for_device

connect_mesh(credentials_file="~/Downloads/erivan01-voice.creds.json")
wait_for_device("erivan01-voice", timeout_s=60)  # after firmware is on mesh
# invoke_device("erivan01-voice", ...)
disconnect_mesh()
```

## Invoke

```python
invoke_device("erivan01-voice", "get_status", {})
invoke_device("erivan01-voice", "get_voice_phase", {})
invoke_device("erivan01-voice", "transcribe_once", {"timeout_s": 25, "emit_event": True})
invoke_device("erivan01-voice", "get_last_transcript", {})
invoke_device("erivan01-voice", "set_mute", {"muted": True})
invoke_device("erivan01-voice", "get_button_state", {})
invoke_device("erivan01-voice", "trigger_center_button", {"press_type": "double_press"})
invoke_device("erivan01-voice", "adjust_volume", {"increase_volume": True, "steps": 2})
invoke_device("erivan01-voice", "play_announcement_url", {"url": "https://example/tts.flac"})
invoke_device("erivan01-voice", "play_device_sound", {"sound_id": "wake_word_triggered"})
invoke_device("erivan01-voice", "set_led_effect", {"effect": "rainbow"})
invoke_device("erivan01-voice", "set_led_color", {"red": 0.1, "green": 0.7, "blue": 0.95})
invoke_device("erivan01-voice", "release_led_control", {})
invoke_device("erivan01-voice", "enable_wake_word_model", {"model_id": "hey_jarvis"})
invoke_device("erivan01-voice", "set_wake_word_sensitivity", {"sensitivity": "moderately_sensitive"})
```

### Controls & speaker

- **Center button** — `get_button_state`, `trigger_center_button` (`single`, `double_press`, `triple_press`, `long_press`)
- **Dial** — `get_volume`, `set_volume`, `adjust_volume` (maps to rotary encoder → `external_media_player`)
- **Speaker** — `get_audio_output_status`, `play_media_url`, `play_announcement_url`, `stop_audio_output`, `pause_audio_output`, `play_device_sound`
- **LED ring** — `get_led_status`, `list_led_effects`, `set_led_color`, `set_led_brightness`, `set_led_effect`, `turn_led_on`, `turn_led_off`, `adjust_led_hue`, `release_led_control`
- **Wake word** — `list_wake_word_models`, `enable_wake_word_model`, `set_wake_word_sensitivity`, `start_wake_word_detection`, `trigger_wake_word` (firmware normally fires detection)

## Events

Subscribe to `stt_event`, `wake_word_detected`, `button_event`, `volume_changed`, `led_changed`, and `audio_event` (mic VAD only).

## MCP

```json
"device-connect": {
  "command": "/path/to/device-connect-voice/.venv/bin/python",
  "args": ["-m", "device_connect_agent_tools.mcp"],
  "env": {
    "NATS_CREDENTIALS_FILE": "/Users/erivan01/Downloads/erivan01-voice.creds.json"
  }
}
```

## Failure modes

| Symptom | Likely cause |
|---------|----------------|
| No `whisper` devices | Firmware not running / not on mesh |
| `transcribe_once` timeout | STT pipeline not configured (Wyoming / HA) |
| Portal permission errors | Wrong tenant — use tenant from creds file |
