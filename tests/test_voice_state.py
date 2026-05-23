"""Tests for voice assistant state snapshots."""

from __future__ import annotations

from device_connect_voice.voice_state import (
    DEFAULT_WAKE_WORD_MODELS,
    VoiceDeviceState,
    VoicePhase,
)


def test_voice_device_state_default_wake_word_models() -> None:
    state = VoiceDeviceState()

    assert len(state.wake_word_models) == len(DEFAULT_WAKE_WORD_MODELS)
    assert state.wake_word_models["okay_nabu"]["enabled"] is True
    assert state.active_wake_word_models()[0]["model_id"] == "okay_nabu"


def test_as_status_dict_includes_nested_sections() -> None:
    state = VoiceDeviceState(phase=VoicePhase.LISTENING, last_transcript="hello")
    status = state.as_status_dict()

    assert status["phase"] == "listening"
    assert status["phase_id"] == int(VoicePhase.LISTENING)
    assert status["last_transcript"] == "hello"
    assert "controls" in status
    assert "audio_output" in status
    assert "led_ring" in status
    assert status["wake_word"]["models"]


def test_as_led_dict_maps_effect_name() -> None:
    state = VoiceDeviceState(led_effect="rainbow")
    led = state.as_led_dict()

    assert led["effect"] == "rainbow"
    assert led["effect_name"] == "Rainbow"
