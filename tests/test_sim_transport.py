"""Tests for SimVoiceTransport behavior."""

from __future__ import annotations

import pytest

from device_connect_voice.transport import SimVoiceTransport
from device_connect_voice.voice_state import VoicePhase


@pytest.fixture
async def transport() -> SimVoiceTransport:
    sim = SimVoiceTransport()
    await sim.start()
    yield sim
    await sim.stop()


async def test_start_sets_idle_and_stt_ready(transport: SimVoiceTransport) -> None:
    state = transport.read_state()
    assert state.phase == VoicePhase.IDLE
    assert state.stt_ready is True
    assert state.wake_word_detection_running is True


async def test_set_volume_clamps_to_device_range(transport: SimVoiceTransport) -> None:
    low = await transport.set_volume(0.0)
    high = await transport.set_volume(9.0)

    assert low["volume"] == transport.read_state().volume_min
    assert high["volume"] == transport.read_state().volume_max


async def test_enable_wake_word_model_exclusivity(transport: SimVoiceTransport) -> None:
    result = await transport.enable_wake_word_model("hey_jarvis")
    state = transport.read_state()

    assert result["status"] == "success"
    assert state.wake_word_models["hey_jarvis"]["enabled"] is True
    assert state.wake_word_models["okay_nabu"]["enabled"] is False


async def test_trigger_wake_word_requires_enabled_model(transport: SimVoiceTransport) -> None:
    await transport.enable_wake_word_model("hey_jarvis")
    result = await transport.trigger_wake_word("hey_jarvis")

    assert result["status"] == "success"
    assert result["model_id"] == "hey_jarvis"
    assert transport.read_state().last_wake_word_model_id == "hey_jarvis"


async def test_trigger_center_button_normalizes_aliases(transport: SimVoiceTransport) -> None:
    double = await transport.trigger_center_button("double")
    long = await transport.trigger_center_button("long")

    assert double["press_type"] == "double_press"
    assert long["press_type"] == "long_press"


async def test_invalid_led_effect_returns_error(transport: SimVoiceTransport) -> None:
    result = await transport.set_led_effect("not_a_real_effect")

    assert result["status"] == "error"
    assert "effect must be one of" in result["reason"]


async def test_muted_blocks_wake_word_detection_start(transport: SimVoiceTransport) -> None:
    await transport.set_mute(True)
    result = await transport.start_wake_word_detection()

    assert result["status"] == "error"
    assert result["reason"] == "microphone muted"
