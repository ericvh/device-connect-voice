"""Voice assistant phase model aligned with Home Assistant Voice PE ESPHome."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import time
from typing import Any


class VoicePhase(IntEnum):
    IDLE = 1
    WAITING_FOR_COMMAND = 2
    LISTENING = 3
    THINKING = 4
    REPLYING = 5
    NOT_READY = 10
    ERROR = 11


PHASE_NAMES: dict[int, str] = {
    VoicePhase.IDLE: "idle",
    VoicePhase.WAITING_FOR_COMMAND: "waiting_for_command",
    VoicePhase.LISTENING: "listening",
    VoicePhase.THINKING: "thinking",
    VoicePhase.REPLYING: "replying",
    VoicePhase.NOT_READY: "not_ready",
    VoicePhase.ERROR: "error",
}


# Center button: simple press is handled on-device; complex presses are exposed as events.
BUTTON_EVENT_TYPES = frozenset(
    {"single", "double_press", "triple_press", "long_press", "easter_egg_press"}
)

# Named UI sounds shipped with home-assistant-voice-pe (play via play_device_sound).
LED_RING_COUNT = 12

# snake_case id → ESPHome effect name on voice_assistant_leds / led_ring
LED_EFFECT_IDS: dict[str, str] = {
    "none": "none",
    "waiting_for_command": "Waiting for Command",
    "listening": "Listening For Command",
    "thinking": "Thinking",
    "replying": "Replying",
    "error": "Error",
    "muted_or_silent": "Muted or Silent",
    "twinkle": "Twinkle",
    "volume_display": "Volume Display",
    "jack_unplugged": "Jack Unplugged",
    "jack_plugged": "Jack Plugged",
    "center_button_touched": "Center Button Touched",
    "timer_ring": "Timer Ring",
    "timer_tick": "Timer tick",
    "tick": "Tick",
    "rainbow": "Rainbow",
    "factory_reset": "Factory Reset Coming Up",
    "voice_kit_startup_failed": "Voice kit startup failed",
}

# Voice PE bundled micro_wake_word model ids (ESPHome component ids).
WAKE_WORD_MODEL_IDS = frozenset({"okay_nabu", "hey_jarvis", "hey_mycroft", "stop"})

WAKE_WORD_SENSITIVITY_LEVELS = frozenset(
    {"slightly_sensitive", "moderately_sensitive", "very_sensitive"}
)

DEFAULT_WAKE_WORD_MODELS: tuple[dict[str, Any], ...] = (
    {
        "model_id": "okay_nabu",
        "phrase": "okay nabu",
        "enabled": True,
        "internal": False,
    },
    {
        "model_id": "hey_jarvis",
        "phrase": "hey jarvis",
        "enabled": False,
        "internal": False,
    },
    {
        "model_id": "hey_mycroft",
        "phrase": "hey mycroft",
        "enabled": False,
        "internal": False,
    },
    {
        "model_id": "stop",
        "phrase": "stop",
        "enabled": False,
        "internal": True,
    },
)

DEVICE_SOUND_IDS = frozenset(
    {
        "wake_word_triggered",
        "center_button_press",
        "center_button_double_press",
        "center_button_triple_press",
        "center_button_long_press",
        "mute_switch_on",
        "mute_switch_off",
        "timer_finished",
        "jack_connected",
        "jack_disconnected",
    }
)


@dataclass
class VoiceDeviceState:
    """In-process mirror of ESPHome globals exposed to Device Connect."""

    phase: VoicePhase = VoicePhase.NOT_READY
    muted: bool = False
    wake_word_enabled: bool = True
    wake_word_detection_running: bool = False
    wake_word_sensitivity: str = "slightly_sensitive"
    last_wake_word: str | None = None
    last_wake_word_model_id: str | None = None
    wake_word_models: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_transcript: str = ""
    last_error: str | None = None
    stt_ready: bool = False
    assistant_connected: bool = False
    # Center button (binary_sensor center_button + template button_press_event)
    center_button_pressed: bool = False
    last_button_event: str | None = None
    # Rotary dial → external_media_player volume (0.4–0.85 on hardware)
    volume: float = 0.5
    volume_min: float = 0.4
    volume_max: float = 0.85
    output_muted: bool = False
    dial_touched: bool = False
    # Speaker / media_player external_media_player
    media_state: str = "idle"  # idle | playing | paused | announcing
    media_title: str = ""
    # LED ring (led_ring + voice_assistant_leds, 12× WS2812)
    led_on: bool = True
    led_brightness: float = 0.66
    led_red: float = 0.094
    led_green: float = 0.733
    led_blue: float = 0.949
    led_hue: int = 195
    led_effect: str = "none"
    led_manual_override: bool = False
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.wake_word_models:
            self.wake_word_models = {
                entry["model_id"]: dict(entry) for entry in DEFAULT_WAKE_WORD_MODELS
            }

    def touch(self) -> None:
        self.updated_at = time.time()

    def active_wake_word_models(self) -> list[dict[str, Any]]:
        return [
            dict(model)
            for model in self.wake_word_models.values()
            if model.get("enabled") and not model.get("internal")
        ]

    def as_wake_word_dict(self) -> dict:
        return {
            "detection_running": self.wake_word_detection_running,
            "sensitivity": self.wake_word_sensitivity,
            "last_detected": {
                "phrase": self.last_wake_word,
                "model_id": self.last_wake_word_model_id,
            },
            "models": list(self.wake_word_models.values()),
            "active_models": self.active_wake_word_models(),
        }

    def phase_name(self) -> str:
        return PHASE_NAMES.get(int(self.phase), "unknown")

    def as_controls_dict(self) -> dict:
        return {
            "center_button_pressed": self.center_button_pressed,
            "last_button_event": self.last_button_event,
            "dial_touched": self.dial_touched,
        }

    def as_led_dict(self) -> dict:
        effect_name = LED_EFFECT_IDS.get(self.led_effect, self.led_effect)
        return {
            "on": self.led_on,
            "brightness": self.led_brightness,
            "rgb": {
                "red": self.led_red,
                "green": self.led_green,
                "blue": self.led_blue,
            },
            "hue": self.led_hue,
            "effect": self.led_effect,
            "effect_name": effect_name,
            "manual_override": self.led_manual_override,
            "led_count": LED_RING_COUNT,
        }

    def as_audio_output_dict(self) -> dict:
        return {
            "volume": self.volume,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "muted": self.output_muted,
            "media_state": self.media_state,
            "media_title": self.media_title,
        }

    def as_status_dict(self) -> dict:
        return {
            "phase": self.phase_name(),
            "phase_id": int(self.phase),
            "muted": self.muted,
            "wake_word_enabled": self.wake_word_enabled,
            "wake_word": self.as_wake_word_dict(),
            "stt_ready": self.stt_ready,
            "assistant_connected": self.assistant_connected,
            "last_transcript": self.last_transcript,
            "last_error": self.last_error,
            "controls": self.as_controls_dict(),
            "audio_output": self.as_audio_output_dict(),
            "led_ring": self.as_led_dict(),
            "updated_at": self.updated_at,
        }
