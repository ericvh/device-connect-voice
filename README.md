# device-connect-voice

[Device Connect](https://deviceconnect.dev) driver for the **Home Assistant Voice Preview Edition** (Seeed Studio): a `whisper` device type that exposes on-device voice, controls, LEDs, and speaker I/O to AI agents over the portal or LAN mesh.

The design mirrors [reachy-mini-driver](https://github.com/ericvh/reachy-mini-driver) (Python `DeviceDriver` + `device_connect_edge` + MCP), but the **production runtime lives on the ESP32-S3**, not on a USB-attached Mac.

---

## What this project does

| Goal | How |
|------|-----|
| Let agents **discover** a voice satellite | `device_type: whisper` on Device Connect |
| **Invoke** hardware capabilities remotely | 27 JSON-RPC functions (`invoke_device`) |
| **Subscribe** to state changes | 5 events (`stt_event`, `wake_word_detected`, …) |
| Work **portal or LAN** | NATS (`portal.deviceconnect.dev`) or Zenoh D2D |
| Stay **on-device** for real use | ESPHome + `device_connect` C++ component (in progress) |

Agents do not need Home Assistant, USB, or a host bridge once firmware is complete — only network access to the mesh (and, for custom wake words, a one-time ESPHome flash).

---

## Hardware

| Component | Detail |
|-----------|--------|
| Product | [Home Assistant Voice Preview Edition](https://www.home-assistant.io/voice-pe/) (Seeed) |
| SoC | ESP32-S3 (16 MB flash, 8 MB PSRAM) |
| Audio DSP | XMOS XU316 (AEC, noise suppression, I2S) |
| UI | Center button, rotary dial, 12-LED ring, internal speaker, 3.5 mm out |
| Stock stack | [ESPHome `home-assistant-voice-pe`](https://github.com/esphome/home-assistant-voice-pe) |
| Dev USB (typical) | `/dev/cu.usbmodem1101` — ESP32 CDC (flash/logs), not the XMOS DFU port |

---

## Architecture

### Target (production)

```text
┌─────────────────────────────────────────────────────────────┐
│  Home Assistant Voice PE (ESP32-S3 + XMOS)                  │
│  ESPHome: voice_assistant, micro_wake_word, led_ring, …     │
│  device_connect component (zenoh-pico / NATS)               │
└───────────────────────────┬─────────────────────────────────┘
                            │ Wi-Fi
                            ▼
              Device Connect mesh (portal or LAN)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   Cursor MCP          Python agent        Other tenants
   (agent-tools)       (invoke_device)
```

### Today (development)

| Layer | Runs where | On mesh as `erivan01-voice`? |
|-------|------------|------------------------------|
| **ESPHome `device_connect`** | ESP32 | **No** — stub only (logs, no RPC transport yet) |
| **`device_connect_voice` (Python)** | Host (sim) | **Yes**, if you run `./scripts/run_portal_sim.sh` |
| **Your agent** | Laptop | Connects via portal creds only |

The Python package is the **RPC contract reference** and CI simulator until Phase 1–2 firmware ships.

```text
Agent  →  NATS (portal)  →  [ Python sim on Mac ]  →  (no physical device yet)
Agent  →  NATS (portal)  →  [ ESP32 firmware ]     →  mic / LEDs / speaker   ← goal
```

---

## Design decisions

### 1. On-device runtime, not a Mac bridge

**Decision:** Device Connect runs on the **ESP32** via an ESPHome external component, not as a permanent Python process on the USB host.

**Why:** The user goal is a satellite that works like Reachy’s on-robot driver: plug in power, join Wi‑Fi, appear on the portal. A Mac-only bridge would duplicate HA Voice PE’s existing ESPHome stack and tie operation to USB.

**Tradeoff:** Requires **zenoh-pico** (LAN) and/or an **ESP32 NATS client** (portal) in C++ — more work than reusing `device-connect-edge` Python on a Pi.

### 2. `device_type: whisper`

**Decision:** Register as `whisper`, not `voice` or `sensor`.

**Why:** Signals STT-oriented capabilities to agents (`transcribe_once`, `stt_event`) without implying a full “whisper.cpp on chip” implementation.

**Clarification:** **Whisper-scale STT does not run on the ESP32.** The name reflects the *agent-facing role* (speech → text). STT is performed by the **voice_assistant** pipeline (Wyoming / Home Assistant Assist), often with Whisper on a **LAN server**.

### 3. Python package = contract + simulator

**Decision:** `src/device_connect_voice/` implements the same RPC names as firmware will, with `SimVoiceTransport` for tests and portal bring-up.

**Why:** Agents and MCP can be developed before ESP32 transport is finished; smoke tests run without hardware.

**Not for production:** Do not rely on `--sim --portal` as the long-term deployment — it registers the **host** as the device, not the board.

### 4. Mirror Voice PE ESPHome semantics

**Decision:** RPCs map to real ESPHome IDs and scripts from `home-assistant-voice-pe` (`external_media_player`, `control_volume`, `micro_wake_word`, `led_ring`, `control_leds`, etc.).

**Why:** Avoid inventing a parallel API that diverges from what the hardware already does.

**Examples:**

| RPC | ESPHome |
|-----|---------|
| `adjust_volume` | `control_volume` + `media_player.volume_up/down` |
| `trigger_wake_word` | `on_wake_word_detected` → `voice_assistant.start` |
| `release_led_control` | Clear `color_changed`, run `control_leds` |
| `enable_wake_word_model` | `micro_wake_word.enable_model` |

### 5. Low-level vs semantic events

**Decision:** `audio_event` carries RMS/VAD-style hints; `stt_event` and `wake_word_detected` carry language-level results.

**Why:** Matches Reachy-mini pattern — reduces accidental leakage of “fake semantics” over the mesh while still allowing rich subscriptions when STT/wake word completes.

### 6. LED agent override vs voice phases

**Decision:** Agent LED commands set `manual_override`; `release_led_control` returns the ring to phase-driven `control_leds`.

**Why:** Voice PE normally owns the ring during idle/listening/thinking/replying. Agents can temporarily style the ring without permanently breaking HA’s LED logic.

### 7. Wake word: control, not train, over Device Connect

**Decision:** Expose `list_wake_word_models`, `enable_wake_word_model`, `set_wake_word_sensitivity`, `wake_word_detected` — **not** cloud registration of new `.tflite` models.

**Why:** microWakeWord **training** is offline (train → host `.json` + `.tflite` → add to ESPHome YAML → reflash). Device Connect only remote-controls models **already flashed**.

**Bundled models (Voice PE):** `okay_nabu`, `hey_jarvis`, `hey_mycroft`, plus internal `stop`.

### 8. Portal vs LAN

| Mode | Transport | Credentials | Use case |
|------|-----------|-------------|----------|
| **Portal** | NATS `nats://portal.deviceconnect.dev:4222` | JWT + NKey on **device** and on **agent** | Remote agents, MCP |
| **LAN D2D** | Zenoh peer / multicast | Usually no portal JWT; `DEVICE_CONNECT_ALLOW_INSECURE` | Local lab, no cloud registry |

Portal creds for this project resolve to **`tenant: erivan01`**, **`device_id: erivan01-voice`** (from `~/Downloads/erivan01-voice.creds.json`).

### 9. Portal credentials: device and agent (both, for production)

**Yes — for the board to appear on the portal as `erivan01-voice`, the portal credentials must be provisioned on the device**, not only on your laptop.

| Where | What uses creds | Required for |
|-------|-----------------|--------------|
| **ESP32 firmware** | `device_connect` NATS client | Device `registerDevice`, heartbeats, RPC handler, event publish |
| **Agent / Cursor** | `device_connect_agent_tools` / MCP | `discover_devices`, `invoke_device`, subscribe |

The same `erivan01-voice.creds.json` (JWT + `nats.nkey_seed`) is the usual starting point for **development**, but production should treat it as **device secrets**:

- **Burn / provision into firmware** — e.g. ESPHome `secrets.yaml` → compiled into the image, or written to NVS on first boot (Phase 2). The device must authenticate as `erivan01-voice` in tenant `erivan01`.
- **Never commit** creds to git; rotate if leaked.
- **Agents** keep a copy (or separate user credentials with ACLs to invoke that device) on the machine running MCP — that does **not** replace on-device provisioning.

```text
┌──────────────┐     NATS (portal)      ┌──────────────┐
│  ESP32       │ ◄──────────────────► │  Registry    │
│  JWT burned  │   registerDevice     │  + routing   │
│  in firmware │   cmd / events       └──────▲───────┘
└──────────────┘                            │
                                            │ same tenant
┌──────────────┐     NATS (portal)          │
│  Cursor MCP  │ ◄────────────────────────┘
│  creds in    │   invoke_device("erivan01-voice", …)
│  mcp.json    │
└──────────────┘
```

**Today:** only the **host sim** (`./scripts/run_portal_sim.sh`) uses the creds file to impersonate the device on the portal. The flashed ESP32 stub does **not** connect to NATS yet.

**LAN-only D2D** can work without portal JWT on the device (Zenoh peer mesh). Portal mode always needs credentials **on the device** if the device is the thing registering.

### 10. Host vs agent responsibilities

| Role | Needs USB? | Needs portal creds? | Needs device on Wi‑Fi? |
|------|------------|---------------------|-------------------------|
| **Agent / Cursor** | No | Yes (for portal) | Yes (device registered) |
| **Developer flashing** | Yes (ESP32 port) | No | No (for flash only) |
| **End user** | No | No | Yes |

---

## Voice and STT pipeline (on device)

```text
Mic (I2S) ──► micro_wake_word (TFLite, on ESP32)
                  │
                  ▼ on_wake_word_detected
              voice_assistant.start
                  │
                  ▼
              STT (Wyoming / HA Assist — typically off-chip)
                  │
                  ▼
              transcript → get_last_transcript / stt_event
```

| Step | Where | Device Connect |
|------|--------|----------------|
| Wake word | ESP32 | `wake_word_detected`, `trigger_wake_word` |
| Push-to-talk | ESP32 | `start_listen`, `transcribe_once` |
| STT | Pipeline server / HA | `transcribe_once`, `get_last_transcript`, `stt_event` |
| TTS / reply | Speaker pipeline | `play_announcement_url`, `play_media_url` |

---

## RPC surface (27 functions)

Full parameter details: [docs/protocol.md](docs/protocol.md).

### Voice / STT (8)

| Function | Summary |
|----------|---------|
| `get_status` | Phase, mute, controls, audio, LED ring, wake word state |
| `get_voice_phase` | Assistant phase id/name |
| `set_mute` | Master mic mute |
| `start_listen` / `stop_listen` | Push-to-talk cycle |
| `get_last_transcript` | Last STT text |
| `transcribe_once` | Listen and wait for transcript |
| `detect_audio_activity` | VAD-style hint (not STT) |

### microWakeWord (8)

| Function | Summary |
|----------|---------|
| `list_wake_word_models` | Models and `enabled` flags |
| `get_wake_word_status` | Sensitivity, detection running, last phrase |
| `enable_wake_word_model` / `disable_wake_word_model` | Select active phrase |
| `set_wake_word_sensitivity` | `slightly_sensitive` / `moderately_sensitive` / `very_sensitive` |
| `start_wake_word_detection` / `stop_wake_word_detection` | `micro_wake_word.start` / `.stop` |
| `trigger_wake_word` | Handle detection (usually firmware; starts VA) |

### Center button (2)

| Function | Summary |
|----------|---------|
| `get_button_state` | Pressed + last complex press |
| `trigger_center_button` | `single`, `double_press`, `triple_press`, `long_press`, `easter_egg_press` |

### Rotary dial / volume (3)

| Function | Summary |
|----------|---------|
| `get_volume` | Level, min/max (~0.4–0.85 on PE), mute |
| `set_volume` | Set level (0–1) |
| `adjust_volume` | Dial-style steps (~5% per step) |

### Speaker (6)

| Function | Summary |
|----------|---------|
| `get_audio_output_status` | idle / playing / paused / announcing |
| `play_media_url` | HTTP / Sendspin media |
| `play_announcement_url` | Short TTS / announcement URI |
| `stop_audio_output` / `pause_audio_output` | Playback control |
| `play_device_sound` | Bundled UI sounds (`wake_word_triggered`, `center_button_press`, …) |

### LED ring (9)

| Function | Summary |
|----------|---------|
| `get_led_status` | On, RGB, brightness, effect, override flag |
| `list_led_effects` | Valid animation ids |
| `set_led_color` / `set_led_brightness` / `set_led_effect` | Direct styling |
| `turn_led_on` / `turn_led_off` | Power |
| `adjust_led_hue` | Dial + button held (hue) |
| `release_led_control` | Return to voice-assistant LEDs |

---

## Events (5)

| Event | When |
|-------|------|
| `stt_event` | New transcript |
| `wake_word_detected` | microWakeWord fired (`wake_word`, `model_id`) |
| `button_event` | Center button action |
| `volume_changed` | Volume or mute changed |
| `led_changed` | Agent changed ring |
| `audio_event` | Low-level mic activity (not text) |

Subscribe on: `device-connect.{tenant}.{device_id}.event.{name}` (see [docs/protocol.md](docs/protocol.md)).

---

## Repository layout

```text
device-connect-voice/
├── README.md
├── src/device_connect_voice/          ← Python driver (contract + portal sim) ✅ usable
├── tests/smoke_sim_runtime.py
├── scripts/run_portal_sim.sh
├── docs/protocol.md
├── firmware/                          ← on-device (in progress) ⚠️ see below
│   ├── components/device_connect/     ← ESPHome component stub
│   └── esphome/
│       ├── device-connect-voice.full.yaml      ← flashable merged Voice PE
│       └── device-connect-voice.overlay.yaml   ← merge input (not standalone)
└── AGENTS.md, TODO.md, CHANGELOG.md
```

| Path | Purpose | Ready? |
|------|---------|--------|
| [src/device_connect_voice/](src/device_connect_voice/) | `VoiceWhisperDriver`, portal sim, mesh helpers | **Yes** (sim / contract) |
| [firmware/components/device_connect/](firmware/components/device_connect/) | ESPHome C++ component | **Stub** (no mesh RPC) |
| [firmware/esphome/device-connect-voice.full.yaml](firmware/esphome/device-connect-voice.full.yaml) | Merged Voice PE + Device Connect | **Flash** (component still stub) |
| [firmware/esphome/device-connect-voice.overlay.yaml](firmware/esphome/device-connect-voice.overlay.yaml) | Patch source for `merge_voice_pe_yaml.py` | Do not flash alone |
| [firmware/esphome/README.md](firmware/esphome/README.md) | Flash + refresh upstream | |
| [firmware/README.md](firmware/README.md) | Merge + flash workflow | |
| [docs/protocol.md](docs/protocol.md) | Subject names + hardware mapping table |
| [AGENTS.md](AGENTS.md) | Portal + `invoke_device` cheat sheet |
| [tests/smoke_sim_runtime.py](tests/smoke_sim_runtime.py) | Contract test without broker |
| [scripts/run_portal_sim.sh](scripts/run_portal_sim.sh) | Portal + sim driver |
| [TODO.md](TODO.md) | Firmware phases |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

---

## Quick start

Requires **Python 3.11–3.12** (3.14 not supported by `device-connect-edge` constraints).

```bash
cd ~/src/device-connect-voice
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Smoke test (no network)

```bash
python tests/smoke_sim_runtime.py
# or: ./scripts/run_smoke.sh
```

### Portal (simulated device on mesh)

Uses `~/Downloads/erivan01-voice.creds.json` by default when present.

```bash
export NATS_CREDENTIALS_FILE=~/Downloads/erivan01-voice.creds.json
./scripts/run_portal_sim.sh
# equivalent:
# python -m device_connect_voice --sim --portal
```

Until ESP32 firmware registers, this is how `erivan01-voice` appears on the portal — from the **host sim**, not the USB device.

### LAN device-to-device (no portal)

```bash
DEVICE_CONNECT_ALLOW_INSECURE=true \
DEVICE_CONNECT_DISCOVERY_MODE=d2d \
python -m device_connect_voice --sim --device-id erivan01-voice
```

### Agents (Python)

```python
from device_connect_voice.mesh import connect_mesh, wait_for_device, disconnect_mesh
from device_connect_agent_tools import invoke_device

connect_mesh(credentials_file="~/Downloads/erivan01-voice.creds.json")
wait_for_device("erivan01-voice", timeout_s=60)

invoke_device("erivan01-voice", "get_status", {})
invoke_device("erivan01-voice", "transcribe_once", {"timeout_s": 25})
invoke_device("erivan01-voice", "enable_wake_word_model", {"model_id": "hey_jarvis"})
invoke_device("erivan01-voice", "set_led_effect", {"effect": "rainbow"})

disconnect_mesh()
```

See [AGENTS.md](AGENTS.md) for MCP `~/.cursor/mcp.json` and more examples.

---

## Cursor / MCP

```json
"device-connect": {
  "command": "/path/to/device-connect-voice/.venv/bin/python",
  "args": ["-m", "device_connect_agent_tools.mcp"],
  "env": {
    "NATS_CREDENTIALS_FILE": "/Users/erivan01/Downloads/erivan01-voice.creds.json"
  }
}
```

Discover: `device_type="whisper"`. Invoke: `device_id` **`erivan01-voice`**.

---

## Firmware (on-device path) — status

**What you can use today:** Python driver + portal sim ([Quick start](#quick-start)).  
**What is not done yet:** Zenoh/NATS RPC wiring in `device_connect` (Phase 1–2).

The repo includes a **tracked merged YAML**:

- `firmware/esphome/device-connect-voice.full.yaml` — upstream [home-assistant-voice-pe](https://github.com/esphome/home-assistant-voice-pe) + `device_connect` (regenerate with `./scripts/prepare_firmware.sh`)
- `firmware/components/device_connect/` — ESPHome external component (**stub**)

### To flash hardware

```bash
cd firmware/esphome
cp ../secrets.yaml.example secrets.yaml   # Wi‑Fi (+ portal NATS in Phase 2)
esphome compile device-connect-voice.full.yaml
esphome upload device-connect-voice.full.yaml --device /dev/cu.usbmodem1101
```

**Do not** upload `device-connect-voice.overlay.yaml` alone — it is not the full Voice PE image.

**Portal on device (required for production):** provision NATS JWT + NKey from `erivan01-voice.creds.json` in `secrets.yaml` (Phase 2 code still TODO). See [TODO.md](TODO.md).

---

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DEVICE_ID` | `ha-voice-1` | Overridden by portal creds → `erivan01-voice` |
| `TENANT` | `default` | Overridden by portal creds → `erivan01` |
| `NATS_CREDENTIALS_FILE` | `~/Downloads/erivan01-voice.creds.json` | Auto when `--portal` |
| `DEVICE_CONNECT_PORTAL` | off | Set via `--portal` |
| `DEVICE_CONNECT_ALLOW_INSECURE` | off | LAN dev only |
| `DEVICE_CONNECT_DISCOVERY_MODE` | — | `d2d` or `infra` |
| `DEVICE_CONNECT_LOCAL_ZENOH_ROUTES` | — | Advertised LAN locators |
| `VOICE_SIM` | off | Force simulated transport |

---

## Roadmap

| Phase | Status | Deliverable |
|-------|--------|-------------|
| 0 — Scaffold | Done | Python contract, sim, docs, ESPHome stub |
| 1 — LAN / Zenoh | Planned | `device_connect` subscribes to `.cmd`, wires RPCs to ESPHome |
| 2 — Portal / NATS | Planned | On-device JWT, `registerDevice` as `erivan01-voice` |
| 3 — STT options | Planned | Wyoming-only mode, optional LAN Whisper |
| 4 — CI / polish | Planned | GitHub Actions, published install docs |

Details: [TODO.md](TODO.md).

---

## Security notes

- Portal credential files contain **JWT and NKey seeds** — never commit them (`.gitignore` includes `*.creds.json`).
- `transcribe_once` and `capture`-style RPCs move **speech-derived text** over the mesh; scope agent ACLs accordingly.
- `play_media_url` / `play_announcement_url` can trigger **network fetches and audio output** on the device.

---

## Related projects

- [Device Connect](https://github.com/arm/device-connect) — protocol and SDKs
- [reachy-mini-driver](https://github.com/ericvh/reachy-mini-driver) — architectural template
- [home-assistant-voice-pe](https://github.com/esphome/home-assistant-voice-pe) — upstream firmware
- [ESPHome micro_wake_word](https://esphome.io/components/micro_wake_word/) — on-device wake word

---

## License

Apache-2.0 (aligned with Device Connect edge packages).
