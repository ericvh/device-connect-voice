"""Device Connect whisper RPC contract (functions + events)."""

from __future__ import annotations

REQUIRED_FUNCTIONS = frozenset(
    {
        "get_status",
        "get_voice_phase",
        "set_mute",
        "start_listen",
        "stop_listen",
        "get_last_transcript",
        "transcribe_once",
        "detect_audio_activity",
        "get_button_state",
        "trigger_center_button",
        "get_volume",
        "set_volume",
        "adjust_volume",
        "get_audio_output_status",
        "play_media_url",
        "play_announcement_url",
        "stop_audio_output",
        "pause_audio_output",
        "play_device_sound",
        "get_led_status",
        "list_led_effects",
        "set_led_color",
        "set_led_brightness",
        "set_led_effect",
        "turn_led_on",
        "turn_led_off",
        "adjust_led_hue",
        "release_led_control",
        "list_wake_word_models",
        "get_wake_word_status",
        "enable_wake_word_model",
        "disable_wake_word_model",
        "set_wake_word_sensitivity",
        "start_wake_word_detection",
        "stop_wake_word_detection",
        "trigger_wake_word",
    }
)

REQUIRED_EVENTS = frozenset(
    {
        "stt_event",
        "audio_event",
        "button_event",
        "volume_changed",
        "led_changed",
        "wake_word_detected",
    }
)
