"""Smoke-test VoiceWhisperDriver RPC contract (no messaging loop)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from device_connect_edge import DeviceRuntime

from device_connect_voice.device_connect import VoiceWhisperDriver
from device_connect_voice.transport import SimVoiceTransport
from contract import REQUIRED_EVENTS, REQUIRED_FUNCTIONS


async def main() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    driver = VoiceWhisperDriver(voice_transport=SimVoiceTransport())
    runtime = DeviceRuntime(
        driver=driver,
        device_id="ha-voice-sim-smoke",
        tenant="smoke",
        allow_insecure=True,
    )
    driver.set_event_callback(lambda name, payload: events.append((name, payload)))

    function_names = {func.name for func in runtime.capabilities.functions}
    event_names = {event.name for event in runtime.capabilities.events}
    missing_functions = sorted(REQUIRED_FUNCTIONS - function_names)
    missing_events = sorted(REQUIRED_EVENTS - event_names)
    if missing_functions or missing_events:
        raise AssertionError(
            {"missing_functions": missing_functions, "missing_events": missing_events}
        )

    await driver.connect()
    status = await driver.invoke("get_status")
    await driver.invoke("set_mute", muted=False)
    models = await driver.invoke("list_wake_word_models")
    await driver.invoke("enable_wake_word_model", model_id="hey_jarvis")
    await driver.invoke("set_wake_word_sensitivity", sensitivity="moderately_sensitive")
    tx = await driver.invoke("transcribe_once", timeout_s=2.0)
    ww = await driver.invoke("trigger_wake_word", model_id="hey_jarvis")
    await asyncio.sleep(0.25)
    transcript = await driver.invoke("get_last_transcript")
    await driver.invoke("detect_audio_activity", threshold=0.05)
    btn = await driver.invoke("trigger_center_button", press_type="double_press")
    vol = await driver.invoke("set_volume", volume=0.6)
    await driver.invoke("play_device_sound", sound_id="center_button_press")
    await driver.invoke("stop_audio_output")
    led = await driver.invoke("set_led_effect", effect="rainbow")
    await driver.invoke("set_led_color", red=1.0, green=0.2, blue=0.1)
    await driver.invoke("release_led_control")
    await driver.disconnect()

    if len(models.get("models", [])) < 3:
        raise AssertionError(f"list_wake_word_models failed: {models}")
    if ww.get("model_id") != "hey_jarvis":
        raise AssertionError(f"trigger_wake_word failed: {ww}")
    if btn.get("press_type") != "double_press":
        raise AssertionError(f"trigger_center_button failed: {btn}")
    if vol.get("volume") != 0.6:
        raise AssertionError(f"set_volume failed: {vol}")
    event_names_seen = {name for name, _ in events}
    if led.get("effect") != "rainbow":
        raise AssertionError(f"set_led_effect failed: {led}")
    required_events = {"button_event", "volume_changed", "led_changed", "wake_word_detected"}
    if not required_events.issubset(event_names_seen):
        raise AssertionError(f"expected {required_events}, got {events!r}")

    if status["voice"]["phase"] not in {"idle", "not_ready"}:
        raise AssertionError(f"unexpected phase after disconnect: {status}")
    if tx.get("status") != "success" or not tx.get("text"):
        raise AssertionError(f"transcribe_once failed: {tx}")
    if transcript.get("text") != tx.get("text"):
        raise AssertionError("get_last_transcript mismatch")
    if "stt_event" not in {name for name, _ in events}:
        raise AssertionError(f"expected stt_event, got {events!r}")

    print(
        json.dumps(
            {
                "status": "ok",
                "device_id": runtime.device_id,
                "functions": sorted(function_names),
                "events": sorted(event_names),
                "transcript": tx.get("text"),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
