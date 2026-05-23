# Device Connect subject layout (voice / whisper)

Aligned with `device_connect_edge.device.DeviceRuntime` in [device-connect](https://github.com/arm/device-connect).

## Commands (agent → device)


| Subject                                   | Payload                                 |
| ----------------------------------------- | --------------------------------------- |
| `device-connect.{tenant}.{device_id}.cmd` | JSON-RPC 2.0 `{"id","method","params"}` |


### RPC methods (`device_type: whisper`)

#### Voice / STT


| Method                  | Parameters                 | Description                                                                  |
| ----------------------- | -------------------------- | ---------------------------------------------------------------------------- |
| `get_status`            | —                          | Phase, mute, STT, **controls** (button), **audio_output** (volume, playback) |
| `get_voice_phase`       | —                          | Current voice assistant phase                                                |
| `set_mute`              | `muted`                    | Microphone mute                                                              |
| `start_listen`          | —                          | Begin listen cycle                                                           |
| `stop_listen`           | —                          | End listen cycle                                                             |
| `get_last_transcript`   | —                          | Last STT text                                                                |
| `transcribe_once`       | `timeout_s`, `emit_event`  | Listen + wait for transcript                                                 |
| `detect_audio_activity` | `threshold`, `duration_ms` | VAD-style mic hint                                                           |


#### Center button


| Method                  | Parameters                 | Description                                                                |
| ----------------------- | -------------------------- | -------------------------------------------------------------------------- |
| `get_button_state`      | —                          | `pressed`, `last_event`                                                    |
| `trigger_center_button` | `press_type`, `emit_event` | `single`, `double_press`, `triple_press`, `long_press`, `easter_egg_press` |


#### Rotary dial / volume


| Method          | Parameters                               | Description                                |
| --------------- | ---------------------------------------- | ------------------------------------------ |
| `get_volume`    | —                                        | Volume, min/max, mute, media state         |
| `set_volume`    | `volume`, `emit_event`                   | Set level (0–1, clamped on device)         |
| `adjust_volume` | `increase_volume`, `steps`, `emit_event` | Dial-style step (~5% per step on hardware) |


#### Speaker / media output


| Method                    | Parameters | Description                                           |
| ------------------------- | ---------- | ----------------------------------------------------- |
| `get_audio_output_status` | —          | Playback state + volume                               |
| `play_media_url`          | `url`      | Play HTTP/Sendspin media                              |
| `play_announcement_url`   | `url`      | Short announcement / TTS URI                          |
| `stop_audio_output`       | —          | Stop playback                                         |
| `pause_audio_output`      | —          | Pause playback                                        |
| `play_device_sound`       | `sound_id` | Bundled UI sound (see `voice_state.DEVICE_SOUND_IDS`) |


## Events (device → subscribers)


| Event            | Fields                              | Description                           |
| ---------------- | ----------------------------------- | ------------------------------------- |
| `stt_event`      | `text`, `phase`, `stt_backend`      | Transcript ready                      |
| `audio_event`    | `kind`, `source`, `state`, `rms`, … | Mic activity                          |
| `button_event`   | `press_type`                        | Center button (physical or triggered) |
| `volume_changed` | `volume`, `muted`                   | Volume or mute changed                |


## Registration (infra / portal)


| Subject                            | Method           |
| ---------------------------------- | ---------------- |
| `device-connect.{tenant}.registry` | `registerDevice` |


## Heartbeat

`device-connect.{tenant}.{device_id}.heartbeat`

## D2D presence

`device-connect.{tenant}.{device_id}.presence`

## Hardware mapping (Voice PE ESPHome)


| RPC                     | ESPHome                                                 |
| ----------------------- | ------------------------------------------------------- |
| `trigger_center_button` | `center_button` / `button_press_event` scripts          |
| `adjust_volume`         | `control_volume` script + `media_player.volume_up/down` |
| `set_volume`            | `media_player.volume_set` on `external_media_player`    |
| `play_`*                | `external_media_player` play / announcement pipeline    |
| `play_device_sound`     | `play_sound` script + bundled `.flac` assets            |


## Python reference

Implemented in `src/device_connect_voice/device_connect.py` for simulation and CI.