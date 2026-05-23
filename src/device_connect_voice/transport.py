"""Transport boundary between Device Connect driver and on-device voice hardware."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import colorsys
import time

from device_connect_voice.voice_state import (
    BUTTON_EVENT_TYPES,
    DEVICE_SOUND_IDS,
    LED_EFFECT_IDS,
    WAKE_WORD_MODEL_IDS,
    WAKE_WORD_SENSITIVITY_LEVELS,
    VoiceDeviceState,
    VoicePhase,
)


def _hsv_to_rgb(hue: int, saturation: float = 1.0, value: float = 1.0) -> tuple[float, float, float]:
    r, g, b = colorsys.hsv_to_rgb((hue % 360) / 360.0, saturation, value)
    return r, g, b


def _rgb_to_hue(red: float, green: float, blue: float) -> int:
    h, _, _ = colorsys.rgb_to_hsv(red, green, blue)
    return int(h * 360) % 360


class VoiceTransport(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Connect to hardware or enter simulated ready state."""

    @abstractmethod
    async def stop(self) -> None:
        """Release hardware resources."""

    @abstractmethod
    def read_state(self) -> VoiceDeviceState:
        """Return the latest voice assistant state snapshot."""

    @abstractmethod
    async def set_mute(self, muted: bool) -> dict:
        """Hardware/software mute."""

    @abstractmethod
    async def start_listen(self) -> dict:
        """Begin a voice-assistant listen cycle (wake or push-to-talk)."""

    @abstractmethod
    async def stop_listen(self) -> dict:
        """Stop an active listen cycle."""

    @abstractmethod
    async def set_transcript(self, text: str) -> None:
        """Called when STT completes (firmware or Wyoming pipeline)."""

    @abstractmethod
    async def get_button_state(self) -> dict:
        """Center button pressed state and last complex press event."""

    @abstractmethod
    async def trigger_center_button(self, press_type: str) -> dict:
        """Simulate center button action (single/double/triple/long)."""

    @abstractmethod
    async def get_volume(self) -> dict:
        """Speaker volume and output mute state."""

    @abstractmethod
    async def set_volume(self, volume: float) -> dict:
        """Set media player volume (clamped to device min/max)."""

    @abstractmethod
    async def adjust_volume(self, increase_volume: bool, steps: int = 1) -> dict:
        """Step volume like the rotary dial (volume_up / volume_down)."""

    @abstractmethod
    async def get_audio_output_status(self) -> dict:
        """Playback state for internal speaker / external_media_player."""

    @abstractmethod
    async def play_media_url(self, url: str) -> dict:
        """Play HTTP/Sendspin media on the device speaker."""

    @abstractmethod
    async def play_announcement_url(self, url: str) -> dict:
        """Play a short announcement (TTS URI) on the announcement pipeline."""

    @abstractmethod
    async def stop_audio_output(self) -> dict:
        """Stop playback."""

    @abstractmethod
    async def pause_audio_output(self) -> dict:
        """Pause playback."""

    @abstractmethod
    async def play_device_sound(self, sound_id: str) -> dict:
        """Play a bundled UI sound (e.g. center_button_press)."""

    @abstractmethod
    async def get_led_status(self) -> dict:
        """Return LED ring on/brightness/RGB/effect state."""

    @abstractmethod
    async def set_led_color(self, red: float, green: float, blue: float) -> dict:
        """Set solid RGB on the ring (0.0–1.0 per channel)."""

    @abstractmethod
    async def set_led_brightness(self, brightness: float) -> dict:
        """Set ring brightness (0.0–1.0)."""

    @abstractmethod
    async def set_led_effect(self, effect: str) -> dict:
        """Run a named ring animation (see ``LED_EFFECT_IDS``)."""

    @abstractmethod
    async def turn_led_on(self) -> dict:
        """Power on the ring (optionally after agent override)."""

    @abstractmethod
    async def turn_led_off(self) -> dict:
        """Power off the ring."""

    @abstractmethod
    async def adjust_led_hue(self, increase_hue: bool, steps: int = 1) -> dict:
        """Step hue like dial + center button held (control_hue script)."""

    @abstractmethod
    async def release_led_control(self) -> dict:
        """Return ring to voice-assistant ``control_leds`` automation."""

    @abstractmethod
    async def list_wake_word_models(self) -> dict:
        """List micro_wake_word models and enabled state."""

    @abstractmethod
    async def enable_wake_word_model(self, model_id: str) -> dict:
        """Enable a wake word model (ESPHome ``micro_wake_word.enable_model``)."""

    @abstractmethod
    async def disable_wake_word_model(self, model_id: str) -> dict:
        """Disable a wake word model."""

    @abstractmethod
    async def set_wake_word_sensitivity(self, sensitivity: str) -> dict:
        """Set wake word probability cutoffs (Voice PE sensitivity select)."""

    @abstractmethod
    async def start_wake_word_detection(self) -> dict:
        """Start on-device wake word listening (``micro_wake_word.start``)."""

    @abstractmethod
    async def stop_wake_word_detection(self) -> dict:
        """Stop on-device wake word listening (``micro_wake_word.stop``)."""

    @abstractmethod
    async def get_wake_word_status(self) -> dict:
        """Return wake word models, sensitivity, and last detection."""

    @abstractmethod
    async def trigger_wake_word(self, model_id: str) -> dict:
        """Handle a detection (``on_wake_word_detected``) and start voice assistant."""


class SimVoiceTransport(VoiceTransport):
    """Simulates ESPHome voice phases for CI and RPC contract tests."""

    def __init__(self) -> None:
        self._state = VoiceDeviceState()
        self._listen_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._state.phase = VoicePhase.IDLE
        self._state.assistant_connected = True
        self._state.stt_ready = True
        self._state.wake_word_detection_running = True
        self._sync_wake_word_enabled_flag()
        self._state.touch()

    async def stop(self) -> None:
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self._state.phase = VoicePhase.NOT_READY
        self._state.assistant_connected = False
        self._state.wake_word_detection_running = False
        self._state.touch()

    def read_state(self) -> VoiceDeviceState:
        return self._state

    def _sync_wake_word_enabled_flag(self) -> None:
        self._state.wake_word_enabled = bool(self._state.active_wake_word_models())

    def _normalize_model_id(self, model_id: str) -> str:
        return model_id.strip().lower().replace("-", "_")

    async def list_wake_word_models(self) -> dict:
        return {
            "status": "success",
            "models": list(self._state.wake_word_models.values()),
        }

    async def enable_wake_word_model(self, model_id: str) -> dict:
        normalized = self._normalize_model_id(model_id)
        if normalized not in WAKE_WORD_MODEL_IDS:
            return {
                "status": "error",
                "reason": f"model_id must be one of {sorted(WAKE_WORD_MODEL_IDS)}",
            }
        model = self._state.wake_word_models.get(normalized)
        if model is None:
            return {"status": "error", "reason": f"unknown model_id: {normalized}"}
        if not model.get("internal"):
            for other_id, other in self._state.wake_word_models.items():
                if other_id != normalized and not other.get("internal"):
                    other["enabled"] = False
        model["enabled"] = True
        self._sync_wake_word_enabled_flag()
        self._state.touch()
        return {"status": "success", "model_id": normalized, "enabled": True}

    async def disable_wake_word_model(self, model_id: str) -> dict:
        normalized = self._normalize_model_id(model_id)
        if normalized not in WAKE_WORD_MODEL_IDS:
            return {
                "status": "error",
                "reason": f"model_id must be one of {sorted(WAKE_WORD_MODEL_IDS)}",
            }
        model = self._state.wake_word_models.get(normalized)
        if model is None:
            return {"status": "error", "reason": f"unknown model_id: {normalized}"}
        model["enabled"] = False
        self._sync_wake_word_enabled_flag()
        self._state.touch()
        return {"status": "success", "model_id": normalized, "enabled": False}

    async def set_wake_word_sensitivity(self, sensitivity: str) -> dict:
        normalized = sensitivity.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in WAKE_WORD_SENSITIVITY_LEVELS:
            return {
                "status": "error",
                "reason": f"sensitivity must be one of {sorted(WAKE_WORD_SENSITIVITY_LEVELS)}",
            }
        self._state.wake_word_sensitivity = normalized
        self._state.touch()
        return {"status": "success", "sensitivity": normalized}

    async def start_wake_word_detection(self) -> dict:
        if self._state.muted:
            return {"status": "error", "reason": "microphone muted"}
        self._state.wake_word_detection_running = True
        self._state.touch()
        return {"status": "success", "detection_running": True}

    async def stop_wake_word_detection(self) -> dict:
        self._state.wake_word_detection_running = False
        self._state.touch()
        return {"status": "success", "detection_running": False}

    async def get_wake_word_status(self) -> dict:
        return {"status": "success", **self._state.as_wake_word_dict()}

    async def trigger_wake_word(self, model_id: str) -> dict:
        """Simulate ``on_wake_word_detected`` → voice_assistant.start."""
        normalized = self._normalize_model_id(model_id)
        model = self._state.wake_word_models.get(normalized)
        if model is None:
            return {"status": "error", "reason": f"unknown model_id: {normalized}"}
        phrase = str(model.get("phrase", normalized))
        if not self._state.wake_word_detection_running:
            return {"status": "error", "reason": "wake word detection not running"}
        if self._state.muted:
            return {"status": "error", "reason": "microphone muted"}
        if model is None or not model.get("enabled"):
            return {"status": "error", "reason": f"model {normalized!r} is not enabled"}
        self._state.last_wake_word = phrase
        self._state.last_wake_word_model_id = normalized
        self._state.touch()
        if self._listen_task and not self._listen_task.done():
            return {
                "status": "success",
                "wake_word": phrase,
                "model_id": normalized,
                "voice_assistant_started": False,
                "reason": "listen already in progress",
            }
        self._listen_task = asyncio.create_task(self._simulate_listen_cycle())
        return {
            "status": "success",
            "wake_word": phrase,
            "model_id": normalized,
            "voice_assistant_started": True,
        }

    async def set_mute(self, muted: bool) -> dict:
        self._state.muted = muted
        self._state.touch()
        return {"status": "success", "muted": muted}

    async def start_listen(self) -> dict:
        if self._state.muted:
            return {"status": "error", "reason": "microphone muted"}
        if self._listen_task and not self._listen_task.done():
            return {"status": "error", "reason": "listen already in progress"}

        self._listen_task = asyncio.create_task(self._simulate_listen_cycle())
        return {"status": "success", "listening": True}

    async def stop_listen(self) -> dict:
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self._state.phase = VoicePhase.IDLE
        self._state.touch()
        return {"status": "success", "listening": False}

    async def set_transcript(self, text: str) -> None:
        self._state.last_transcript = text
        self._state.touch()

    async def get_button_state(self) -> dict:
        return {
            "status": "success",
            "pressed": self._state.center_button_pressed,
            "last_event": self._state.last_button_event,
        }

    async def trigger_center_button(self, press_type: str) -> dict:
        normalized = press_type.strip().lower().replace("-", "_")
        if normalized == "double":
            normalized = "double_press"
        elif normalized == "triple":
            normalized = "triple_press"
        elif normalized == "long":
            normalized = "long_press"
        if normalized not in BUTTON_EVENT_TYPES:
            return {
                "status": "error",
                "reason": f"press_type must be one of {sorted(BUTTON_EVENT_TYPES)}",
            }
        self._state.last_button_event = normalized
        self._state.center_button_pressed = normalized == "single"
        self._state.touch()
        return {"status": "success", "press_type": normalized}

    async def get_volume(self) -> dict:
        return {
            "status": "success",
            **self._state.as_audio_output_dict(),
        }

    async def set_volume(self, volume: float) -> dict:
        clamped = max(self._state.volume_min, min(self._state.volume_max, float(volume)))
        self._state.volume = clamped
        self._state.touch()
        return {"status": "success", "volume": clamped}

    async def adjust_volume(self, increase_volume: bool, steps: int = 1) -> dict:
        step = 0.05 * max(1, min(steps, 20))
        for _ in range(max(1, min(steps, 20))):
            if increase_volume:
                self._state.volume = min(self._state.volume_max, self._state.volume + step)
            else:
                self._state.volume = max(self._state.volume_min, self._state.volume - step)
        self._state.dial_touched = True
        self._state.touch()
        return {
            "status": "success",
            "volume": self._state.volume,
            "increase_volume": increase_volume,
            "steps": steps,
        }

    async def get_audio_output_status(self) -> dict:
        return {
            "status": "success",
            **self._state.as_audio_output_dict(),
        }

    async def play_media_url(self, url: str) -> dict:
        if not url.strip():
            return {"status": "error", "reason": "url is required"}
        self._state.media_state = "playing"
        self._state.media_title = url.strip()[:120]
        self._state.touch()
        return {"status": "success", "media_state": self._state.media_state, "url": url.strip()}

    async def play_announcement_url(self, url: str) -> dict:
        if not url.strip():
            return {"status": "error", "reason": "url is required"}
        self._state.media_state = "announcing"
        self._state.media_title = url.strip()[:120]
        self._state.touch()
        return {"status": "success", "media_state": self._state.media_state, "url": url.strip()}

    async def stop_audio_output(self) -> dict:
        self._state.media_state = "idle"
        self._state.media_title = ""
        self._state.touch()
        return {"status": "success", "media_state": "idle"}

    async def pause_audio_output(self) -> dict:
        if self._state.media_state == "playing":
            self._state.media_state = "paused"
        self._state.touch()
        return {"status": "success", "media_state": self._state.media_state}

    async def play_device_sound(self, sound_id: str) -> dict:
        normalized = sound_id.strip().lower()
        if normalized not in DEVICE_SOUND_IDS:
            return {
                "status": "error",
                "reason": f"sound_id must be one of {sorted(DEVICE_SOUND_IDS)}",
            }
        self._state.media_state = "announcing"
        self._state.media_title = normalized
        self._state.touch()
        return {"status": "success", "sound_id": normalized}

    def _apply_led_rgb(self, red: float, green: float, blue: float) -> None:
        self._state.led_red = max(0.0, min(1.0, red))
        self._state.led_green = max(0.0, min(1.0, green))
        self._state.led_blue = max(0.0, min(1.0, blue))
        self._state.led_hue = _rgb_to_hue(self._state.led_red, self._state.led_green, self._state.led_blue)
        self._state.led_on = True
        self._state.led_manual_override = True
        self._state.led_effect = "none"
        self._state.touch()

    async def get_led_status(self) -> dict:
        return {"status": "success", **self._state.as_led_dict()}

    async def set_led_color(self, red: float, green: float, blue: float) -> dict:
        self._apply_led_rgb(red, green, blue)
        return {"status": "success", **self._state.as_led_dict()}

    async def set_led_brightness(self, brightness: float) -> dict:
        self._state.led_brightness = max(0.0, min(1.0, float(brightness)))
        self._state.led_on = self._state.led_brightness > 0.0
        self._state.led_manual_override = True
        self._state.touch()
        return {"status": "success", "brightness": self._state.led_brightness}

    async def set_led_effect(self, effect: str) -> dict:
        normalized = effect.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in LED_EFFECT_IDS:
            return {
                "status": "error",
                "reason": f"effect must be one of {sorted(LED_EFFECT_IDS)}",
            }
        self._state.led_effect = normalized
        self._state.led_on = True
        self._state.led_manual_override = True
        self._state.touch()
        return {
            "status": "success",
            "effect": normalized,
            "effect_name": LED_EFFECT_IDS[normalized],
        }

    async def turn_led_on(self) -> dict:
        self._state.led_on = True
        if self._state.led_brightness < 0.2:
            self._state.led_brightness = 0.66
        self._state.led_manual_override = True
        self._state.touch()
        return {"status": "success", "on": True}

    async def turn_led_off(self) -> dict:
        self._state.led_on = False
        self._state.led_manual_override = True
        self._state.touch()
        return {"status": "success", "on": False}

    async def adjust_led_hue(self, increase_hue: bool, steps: int = 1) -> dict:
        count = max(1, min(steps, 36))
        for _ in range(count):
            if increase_hue:
                self._state.led_hue = (self._state.led_hue + 10) % 360
            else:
                self._state.led_hue = (self._state.led_hue + 350) % 360
        r, g, b = _hsv_to_rgb(self._state.led_hue, 1.0, max(0.2, self._state.led_brightness))
        self._apply_led_rgb(r, g, b)
        return {"status": "success", "hue": self._state.led_hue, **self._state.as_led_dict()}

    async def release_led_control(self) -> dict:
        self._state.led_manual_override = False
        self._state.led_effect = "none"
        self._state.touch()
        return {
            "status": "success",
            "manual_override": False,
            "message": "voice assistant control_leds resumed",
        }

    async def _simulate_listen_cycle(self) -> None:
        try:
            self._state.phase = VoicePhase.WAITING_FOR_COMMAND
            self._state.touch()
            await asyncio.sleep(0.05)
            self._state.phase = VoicePhase.LISTENING
            self._state.touch()
            await asyncio.sleep(0.12)
            self._state.phase = VoicePhase.THINKING
            self._state.touch()
            await asyncio.sleep(0.08)
            self._state.last_transcript = "simulated transcript from device microphone"
            self._state.phase = VoicePhase.IDLE
            self._state.touch()
        except asyncio.CancelledError:
            self._state.phase = VoicePhase.IDLE
            self._state.touch()
            raise


class EsphomeSerialTransport(VoiceTransport):
    """Placeholder for UART/API bridge to flashed ESPHome (not yet implemented)."""

    def __init__(self, port: str) -> None:
        self._port = port
        self._state = VoiceDeviceState(phase=VoicePhase.NOT_READY)

    async def start(self) -> None:
        raise NotImplementedError(
            f"ESPHome serial transport for {self._port!r} is not implemented; "
            "flash firmware/components/device_connect and use on-device Zenoh."
        )

    async def stop(self) -> None:
        pass

    def read_state(self) -> VoiceDeviceState:
        return self._state

    async def set_mute(self, muted: bool) -> dict:
        raise NotImplementedError

    async def start_listen(self) -> dict:
        raise NotImplementedError

    async def stop_listen(self) -> dict:
        raise NotImplementedError

    async def set_transcript(self, text: str) -> None:
        raise NotImplementedError

    async def get_button_state(self) -> dict:
        raise NotImplementedError

    async def trigger_center_button(self, press_type: str) -> dict:
        raise NotImplementedError

    async def get_volume(self) -> dict:
        raise NotImplementedError

    async def set_volume(self, volume: float) -> dict:
        raise NotImplementedError

    async def adjust_volume(self, increase_volume: bool, steps: int = 1) -> dict:
        raise NotImplementedError

    async def get_audio_output_status(self) -> dict:
        raise NotImplementedError

    async def play_media_url(self, url: str) -> dict:
        raise NotImplementedError

    async def play_announcement_url(self, url: str) -> dict:
        raise NotImplementedError

    async def stop_audio_output(self) -> dict:
        raise NotImplementedError

    async def pause_audio_output(self) -> dict:
        raise NotImplementedError

    async def play_device_sound(self, sound_id: str) -> dict:
        raise NotImplementedError

    async def get_led_status(self) -> dict:
        raise NotImplementedError

    async def set_led_color(self, red: float, green: float, blue: float) -> dict:
        raise NotImplementedError

    async def set_led_brightness(self, brightness: float) -> dict:
        raise NotImplementedError

    async def set_led_effect(self, effect: str) -> dict:
        raise NotImplementedError

    async def turn_led_on(self) -> dict:
        raise NotImplementedError

    async def turn_led_off(self) -> dict:
        raise NotImplementedError

    async def adjust_led_hue(self, increase_hue: bool, steps: int = 1) -> dict:
        raise NotImplementedError

    async def release_led_control(self) -> dict:
        raise NotImplementedError

    async def list_wake_word_models(self) -> dict:
        raise NotImplementedError

    async def enable_wake_word_model(self, model_id: str) -> dict:
        raise NotImplementedError

    async def disable_wake_word_model(self, model_id: str) -> dict:
        raise NotImplementedError

    async def set_wake_word_sensitivity(self, sensitivity: str) -> dict:
        raise NotImplementedError

    async def start_wake_word_detection(self) -> dict:
        raise NotImplementedError

    async def stop_wake_word_detection(self) -> dict:
        raise NotImplementedError

    async def get_wake_word_status(self) -> dict:
        raise NotImplementedError

    async def trigger_wake_word(self, model_id: str) -> dict:
        raise NotImplementedError
