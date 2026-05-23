"""Tests for VoiceWhisperDriver RPCs and Device Connect contract."""

from __future__ import annotations

from typing import Any

import pytest
from device_connect_edge import DeviceRuntime
from device_connect_edge.errors import FunctionInvocationError

from device_connect_voice.device_connect import VoiceWhisperDriver
from device_connect_voice.transport import SimVoiceTransport
from contract import REQUIRED_EVENTS, REQUIRED_FUNCTIONS


def test_runtime_exposes_contract_functions_and_events() -> None:
    driver = VoiceWhisperDriver(voice_transport=SimVoiceTransport())
    runtime = DeviceRuntime(
        driver=driver,
        device_id="test-whisper",
        tenant="test",
        allow_insecure=True,
    )

    function_names = {func.name for func in runtime.capabilities.functions}
    event_names = {event.name for event in runtime.capabilities.events}

    assert REQUIRED_FUNCTIONS <= function_names
    assert REQUIRED_EVENTS <= event_names
    assert driver.device_type == "whisper"


async def test_get_status_after_connect(connected_driver: VoiceWhisperDriver) -> None:
    status = await connected_driver.invoke("get_status")

    assert status["status"] == "success"
    assert status["device_type"] == "whisper"
    assert status["voice"]["phase"] == "idle"


async def test_transcribe_once_returns_simulated_transcript(
    connected_driver: VoiceWhisperDriver,
    captured_events: list[tuple[str, dict[str, Any]]],
) -> None:
    result = await connected_driver.invoke("transcribe_once", timeout_s=2.0, emit_event=True)

    assert result["status"] == "success"
    assert result["text"]
    transcript = await connected_driver.invoke("get_last_transcript")
    assert transcript["text"] == result["text"]
    assert "stt_event" in {name for name, _ in captured_events}


async def test_set_volume_emits_volume_changed(
    connected_driver: VoiceWhisperDriver,
    captured_events: list[tuple[str, dict[str, Any]]],
) -> None:
    result = await connected_driver.invoke("set_volume", volume=0.6, emit_event=True)

    assert result["status"] == "success"
    assert result["volume"] == 0.6
    assert "volume_changed" in {name for name, _ in captured_events}


async def test_set_volume_rejects_out_of_range(connected_driver: VoiceWhisperDriver) -> None:
    with pytest.raises(FunctionInvocationError, match="volume"):
        await connected_driver.invoke("set_volume", volume=1.5)


async def test_trigger_center_button_emits_event(
    connected_driver: VoiceWhisperDriver,
    captured_events: list[tuple[str, dict[str, Any]]],
) -> None:
    result = await connected_driver.invoke(
        "trigger_center_button",
        press_type="double_press",
        emit_event=True,
    )

    assert result["press_type"] == "double_press"
    assert "button_event" in {name for name, _ in captured_events}


async def test_list_led_effects_includes_rainbow(connected_driver: VoiceWhisperDriver) -> None:
    effects = await connected_driver.invoke("list_led_effects")
    effect_ids = {entry["id"] for entry in effects["effects"]}

    assert effects["status"] == "success"
    assert "rainbow" in effect_ids


async def test_adjust_volume_rejects_invalid_steps(connected_driver: VoiceWhisperDriver) -> None:
    result = await connected_driver.invoke("adjust_volume", increase_volume=True, steps=25)

    assert result["status"] == "error"
    assert "steps must be" in result["reason"]
