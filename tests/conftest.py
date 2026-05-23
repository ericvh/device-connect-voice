"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any

import pytest

from device_connect_voice.device_connect import VoiceWhisperDriver
from device_connect_voice.transport import SimVoiceTransport


@pytest.fixture
def captured_events() -> list[tuple[str, dict[str, Any]]]:
    return []


@pytest.fixture
def sim_transport() -> SimVoiceTransport:
    return SimVoiceTransport()


@pytest.fixture
def driver(
    sim_transport: SimVoiceTransport,
    captured_events: list[tuple[str, dict[str, Any]]],
) -> VoiceWhisperDriver:
    voice_driver = VoiceWhisperDriver(voice_transport=sim_transport)
    voice_driver.set_event_callback(
        lambda name, payload: captured_events.append((name, payload))
    )
    return voice_driver


@pytest.fixture
async def connected_driver(driver: VoiceWhisperDriver) -> VoiceWhisperDriver:
    await driver.connect()
    yield driver
    await driver.disconnect()
