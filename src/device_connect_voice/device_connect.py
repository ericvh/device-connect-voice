"""Device Connect driver for Home Assistant Voice PE (whisper / STT device type)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from device_connect_edge.drivers import DeviceDriver, emit, rpc
from device_connect_edge.types import DeviceIdentity, DeviceStatus

from device_connect_voice.transport import SimVoiceTransport, VoiceTransport
from device_connect_voice.voice_state import LED_EFFECT_IDS, VoicePhase

logger = logging.getLogger(__name__)


class VoiceWhisperDriver(DeviceDriver):
    """Expose voice assistant state and STT-oriented RPCs on the Device Connect mesh.

    Production firmware on ESP32 implements the same function names in the
    ``device_connect`` ESPHome component. This Python class is the contract
    reference and simulator.
    """

    device_type = "whisper"

    def __init__(
        self,
        *,
        voice_transport: VoiceTransport | None = None,
        stt_backend: str = "voice_assistant",
    ):
        super().__init__()
        self.voice_transport = voice_transport or SimVoiceTransport()
        self.stt_backend = stt_backend
        self._last_stt_event: dict[str, Any] | None = None

    @property
    def identity(self) -> DeviceIdentity:
        return DeviceIdentity(
            device_type=self.device_type,
            manufacturer="Seeed Studio",
            model="Home Assistant Voice Preview Edition",
            description=(
                "Voice assistant device with wake word, STT, center button, volume dial, "
                "and speaker output exposed for Device Connect agents"
            ),
        )

    @property
    def status(self) -> DeviceStatus:
        state = self.voice_transport.read_state()
        availability = "available" if state.assistant_connected else "unavailable"
        if state.phase == VoicePhase.ERROR:
            availability = "error"
        elif state.phase in {VoicePhase.LISTENING, VoicePhase.THINKING}:
            availability = "busy"
        return DeviceStatus(ts=datetime.now(UTC), availability=availability)

    async def connect(self) -> None:
        logger.info("VoiceWhisperDriver connecting (stt_backend=%s)", self.stt_backend)
        await self.voice_transport.start()

    async def disconnect(self) -> None:
        await self.voice_transport.stop()

    @rpc()
    async def get_status(self) -> dict[str, Any]:
        """Return voice phase, STT state, center button, dial volume, and speaker playback."""
        snap = self.voice_transport.read_state().as_status_dict()
        return {
            "status": "success",
            "device_type": self.device_type,
            "stt_backend": self.stt_backend,
            "voice": snap,
        }

    @rpc()
    async def get_voice_phase(self) -> dict[str, Any]:
        """Return the current voice assistant phase id and name."""
        snap = self.voice_transport.read_state()
        return {
            "status": "success",
            "phase": snap.phase_name(),
            "phase_id": int(snap.phase),
        }

    @rpc()
    async def set_mute(self, muted: bool = True) -> dict[str, Any]:
        """Mute or unmute microphone capture (maps to master mute on device)."""
        return await self.voice_transport.set_mute(muted)

    @rpc()
    async def start_listen(self) -> dict[str, Any]:
        """Start a listen cycle (push-to-talk / agent-triggered capture)."""
        return await self.voice_transport.start_listen()

    @rpc()
    async def stop_listen(self) -> dict[str, Any]:
        """Stop the active listen cycle."""
        return await self.voice_transport.stop_listen()

    @rpc()
    async def list_wake_word_models(self) -> dict[str, Any]:
        """List ``micro_wake_word`` models baked into firmware and their enabled state."""
        return await self.voice_transport.list_wake_word_models()

    @rpc()
    async def get_wake_word_status(self) -> dict[str, Any]:
        """Return active models, sensitivity, detection running, and last phrase."""
        return await self.voice_transport.get_wake_word_status()

    @rpc()
    async def enable_wake_word_model(
        self,
        model_id: str,
        emit_event: bool = False,
    ) -> dict[str, Any]:
        """Enable a wake phrase model (disables other non-internal models on device).

        Args:
            model_id: ``okay_nabu``, ``hey_jarvis``, ``hey_mycroft``, or ``stop`` (internal).
            emit_event: Reserved; model changes do not emit by default.
        """
        _ = emit_event
        return await self.voice_transport.enable_wake_word_model(model_id)

    @rpc()
    async def disable_wake_word_model(self, model_id: str) -> dict[str, Any]:
        """Disable a wake word model."""
        return await self.voice_transport.disable_wake_word_model(model_id)

    @rpc()
    async def set_wake_word_sensitivity(self, sensitivity: str) -> dict[str, Any]:
        """Set detection sensitivity (maps to Voice PE wake word sensitivity select).

        Args:
            sensitivity: ``slightly_sensitive``, ``moderately_sensitive``, or ``very_sensitive``.
        """
        return await self.voice_transport.set_wake_word_sensitivity(sensitivity)

    @rpc()
    async def start_wake_word_detection(self) -> dict[str, Any]:
        """Start on-device wake word listening (``micro_wake_word.start``)."""
        return await self.voice_transport.start_wake_word_detection()

    @rpc()
    async def stop_wake_word_detection(self) -> dict[str, Any]:
        """Stop on-device wake word listening (``micro_wake_word.stop``)."""
        return await self.voice_transport.stop_wake_word_detection()

    @rpc()
    async def trigger_wake_word(
        self,
        model_id: str = "okay_nabu",
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Fire wake-word handling as if the phrase was detected on-device.

        On hardware this is invoked from ``on_wake_word_detected`` (not usually by agents).
        Starts the voice assistant listen pipeline when successful.

        Args:
            model_id: Which enabled model detected the phrase.
            emit_event: When true, emit ``wake_word_detected``.
        """
        result = await self.voice_transport.trigger_wake_word(model_id)
        if result.get("status") == "success" and emit_event:
            await self._emit_wake_word_detected(
                str(result.get("wake_word", "")),
                str(result.get("model_id", model_id)),
            )
        return result

    @rpc()
    async def get_last_transcript(self) -> dict[str, Any]:
        """Return the most recent STT transcript produced on the device pipeline."""
        snap = self.voice_transport.read_state()
        return {
            "status": "success",
            "text": snap.last_transcript,
            "phase": snap.phase_name(),
            "stt_ready": snap.stt_ready,
        }

    @rpc()
    async def transcribe_once(
        self,
        timeout_s: float = 15.0,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Run one listen cycle and return transcript text when STT completes.

        On hardware this triggers ``voice_assistant`` and waits for the Wyoming /
        Assist STT pipeline (Whisper may run on a LAN server — not on the ESP32).

        Args:
            timeout_s: Maximum seconds to wait for a transcript.
            emit_event: When true, emit ``stt_event`` on success.
        """
        started = await self.voice_transport.start_listen()
        if started.get("status") != "success":
            return started

        deadline = time.monotonic() + max(1.0, min(timeout_s, 120.0))
        last_text = ""
        while time.monotonic() < deadline:
            snap = self.voice_transport.read_state()
            if snap.last_transcript and snap.last_transcript != last_text:
                last_text = snap.last_transcript
                if snap.phase == VoicePhase.IDLE:
                    break
            if snap.phase == VoicePhase.ERROR:
                return {
                    "status": "error",
                    "reason": snap.last_error or "voice assistant error",
                }
            await self._sleep_poll()

        await self.voice_transport.stop_listen()
        snap = self.voice_transport.read_state()
        if not snap.last_transcript:
            return {"status": "error", "reason": "timeout waiting for transcript"}

        payload = {
            "status": "success",
            "text": snap.last_transcript,
            "phase": snap.phase_name(),
            "stt_backend": self.stt_backend,
        }
        if emit_event:
            await self._emit_stt(payload)
        return payload

    @rpc()
    async def get_button_state(self) -> dict[str, Any]:
        """Return whether the center button is pressed and the last complex press type."""
        return await self.voice_transport.get_button_state()

    @rpc()
    async def trigger_center_button(
        self,
        press_type: str = "single",
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Trigger a center-button action (same semantics as physical multi-click).

        Args:
            press_type: ``single``, ``double_press``, ``triple_press``, ``long_press``,
                or ``easter_egg_press``.
            emit_event: When true, emit ``button_event`` after the action is accepted.
        """
        result = await self.voice_transport.trigger_center_button(press_type)
        if result.get("status") == "success" and emit_event:
            await self._emit_button_event(str(result.get("press_type", press_type)))
        return result

    @rpc()
    async def get_volume(self) -> dict[str, Any]:
        """Return speaker volume (rotary dial range) and output mute state."""
        return await self.voice_transport.get_volume()

    @rpc()
    async def set_volume(
        self,
        volume: float,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Set ``external_media_player`` volume (hardware clamps to ~0.4–0.85).

        Args:
            volume: Target level 0.0–1.0 (device enforces its own min/max).
            emit_event: When true, emit ``volume_changed``.
        """
        self._assert_range("volume", volume, 0.0, 1.0)
        result = await self.voice_transport.set_volume(volume)
        if result.get("status") == "success" and emit_event:
            await self._emit_volume_changed(float(result["volume"]))
        return result

    @rpc()
    async def adjust_volume(
        self,
        increase_volume: bool = True,
        steps: int = 1,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Step volume up or down like turning the rotary dial.

        Args:
            increase_volume: True for clockwise / louder, false for quieter.
            steps: Number of dial detents (each ~5%% on hardware).
            emit_event: When true, emit ``volume_changed``.
        """
        if steps < 1 or steps > 20:
            return {"status": "error", "reason": "steps must be in [1, 20]"}
        result = await self.voice_transport.adjust_volume(increase_volume, steps=steps)
        if result.get("status") == "success" and emit_event:
            await self._emit_volume_changed(float(result["volume"]))
        return result

    @rpc()
    async def get_audio_output_status(self) -> dict[str, Any]:
        """Return internal speaker playback state (idle, playing, paused, announcing)."""
        return await self.voice_transport.get_audio_output_status()

    @rpc()
    async def play_media_url(self, url: str) -> dict[str, Any]:
        """Play media from a URL on the device speaker (HTTP / Sendspin sources)."""
        return await self.voice_transport.play_media_url(url)

    @rpc()
    async def play_announcement_url(self, url: str) -> dict[str, Any]:
        """Play a short announcement URL (TTS / FLAC announcement pipeline)."""
        return await self.voice_transport.play_announcement_url(url)

    @rpc()
    async def stop_audio_output(self) -> dict[str, Any]:
        """Stop speaker playback."""
        return await self.voice_transport.stop_audio_output()

    @rpc()
    async def pause_audio_output(self) -> dict[str, Any]:
        """Pause speaker playback."""
        return await self.voice_transport.pause_audio_output()

    @rpc()
    async def play_device_sound(self, sound_id: str) -> dict[str, Any]:
        """Play a bundled UI sound (e.g. ``center_button_press``, ``wake_word_triggered``)."""
        return await self.voice_transport.play_device_sound(sound_id)

    @rpc()
    async def get_led_status(self) -> dict[str, Any]:
        """Return LED ring power, RGB, brightness, active effect, and override state."""
        result = await self.voice_transport.get_led_status()
        return result

    @rpc()
    async def list_led_effects(self) -> dict[str, Any]:
        """List supported ``set_led_effect`` ids and ESPHome effect names."""
        return {
            "status": "success",
            "effects": [
                {"id": key, "name": name} for key, name in sorted(LED_EFFECT_IDS.items())
            ],
        }

    @rpc()
    async def set_led_color(
        self,
        red: float,
        green: float,
        blue: float,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Set solid color on the 12-LED ring (channels 0.0–1.0).

        Maps to ``led_ring`` / ``voice_assistant_leds`` RGB on hardware.
        """
        for channel, value in (("red", red), ("green", green), ("blue", blue)):
            self._assert_range(channel, value, 0.0, 1.0)
        result = await self.voice_transport.set_led_color(red, green, blue)
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def set_led_brightness(
        self,
        brightness: float,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Set ring brightness (0.0–1.0)."""
        self._assert_range("brightness", brightness, 0.0, 1.0)
        result = await self.voice_transport.set_led_brightness(brightness)
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def set_led_effect(
        self,
        effect: str,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Play a ring animation (e.g. ``rainbow``, ``thinking``, ``listening``).

        Use ``list_led_effects`` for valid ``effect`` ids.
        """
        result = await self.voice_transport.set_led_effect(effect)
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def turn_led_on(
        self,
        red: float | None = None,
        green: float | None = None,
        blue: float | None = None,
        brightness: float | None = None,
        effect: str | None = None,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Turn the LED ring on; optionally set color, brightness, or effect."""
        result = await self.voice_transport.turn_led_on()
        if result.get("status") != "success":
            return result
        if brightness is not None:
            result = await self.set_led_brightness(brightness, emit_event=False)
        if effect is not None:
            result = await self.set_led_effect(effect, emit_event=False)
        if red is not None and green is not None and blue is not None:
            result = await self.set_led_color(red, green, blue, emit_event=False)
        if emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def turn_led_off(self, emit_event: bool = True) -> dict[str, Any]:
        """Turn the LED ring off."""
        result = await self.voice_transport.turn_led_off()
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def adjust_led_hue(
        self,
        increase_hue: bool = True,
        steps: int = 1,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Rotate ring hue (dial + center button held → ``control_hue`` on device)."""
        if steps < 1 or steps > 36:
            return {"status": "error", "reason": "steps must be in [1, 36]"}
        result = await self.voice_transport.adjust_led_hue(increase_hue, steps=steps)
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def release_led_control(self, emit_event: bool = True) -> dict[str, Any]:
        """Hand ring back to voice-assistant phase animations (``control_leds``)."""
        result = await self.voice_transport.release_led_control()
        if result.get("status") == "success" and emit_event:
            await self._emit_led_changed(result)
        return result

    @rpc()
    async def detect_audio_activity(
        self,
        threshold: float = 0.05,
        duration_ms: int = 120,
    ) -> dict[str, Any]:
        """Low-level activity hint while listening (not semantic STT)."""
        snap = self.voice_transport.read_state()
        active = snap.phase in {
            VoicePhase.LISTENING,
            VoicePhase.WAITING_FOR_COMMAND,
        }
        rms = 0.12 if active else 0.01
        event = {
            "kind": "audio_activity_detected" if active and rms >= threshold else "audio_activity_ended",
            "source": "microphone",
            "state": "active" if active else "inactive",
            "rms": rms,
            "threshold": threshold,
            "duration_ms": duration_ms,
        }
        await self._record_and_emit_audio_event(event)
        return {"status": "success", "event": event}

    @emit()
    async def stt_event(self, text: str, phase: str, stt_backend: str) -> None:
        """Emitted when a new transcript is available from the device STT pipeline."""
        pass

    @emit()
    async def audio_event(
        self,
        kind: str,
        source: str,
        state: str,
        rms: float,
        threshold: float,
        duration_ms: int,
    ) -> None:
        """Low-level microphone activity (VAD-style), not transcript semantics."""
        pass

    @emit()
    async def button_event(self, press_type: str) -> None:
        """Emitted when the center button fires (physical or ``trigger_center_button``)."""
        pass

    @emit()
    async def volume_changed(self, volume: float, muted: bool) -> None:
        """Emitted when volume changes from the dial or ``set_volume`` / ``adjust_volume``."""
        pass

    @emit()
    async def led_changed(
        self,
        on: bool,
        brightness: float,
        effect: str,
        manual_override: bool,
    ) -> None:
        """Emitted when an agent changes ring color, brightness, or effect."""
        pass

    @emit()
    async def wake_word_detected(self, wake_word: str, model_id: str) -> None:
        """Emitted when ``micro_wake_word`` detects a phrase (on-device)."""
        pass

    @staticmethod
    def _assert_range(name: str, value: float, minimum: float, maximum: float) -> None:
        if value < minimum or value > maximum:
            raise ValueError(f"{name}={value} outside supported range [{minimum}, {maximum}]")

    async def _emit_stt(self, payload: dict[str, Any]) -> None:
        self._last_stt_event = payload
        try:
            await self.stt_event(
                text=str(payload.get("text", "")),
                phase=str(payload.get("phase", "")),
                stt_backend=self.stt_backend,
            )
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    async def _record_and_emit_audio_event(self, event: dict[str, Any]) -> None:
        try:
            await self.audio_event(
                kind=event["kind"],
                source=event["source"],
                state=event["state"],
                rms=event["rms"],
                threshold=event["threshold"],
                duration_ms=event["duration_ms"],
            )
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    async def _emit_button_event(self, press_type: str) -> None:
        try:
            await self.button_event(press_type=press_type)
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    async def _emit_volume_changed(self, volume: float) -> None:
        snap = self.voice_transport.read_state()
        try:
            await self.volume_changed(volume=volume, muted=snap.output_muted)
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    async def _emit_wake_word_detected(self, wake_word: str, model_id: str) -> None:
        try:
            await self.wake_word_detected(wake_word=wake_word, model_id=model_id)
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    async def _emit_led_changed(self, payload: dict[str, Any]) -> None:
        snap = self.voice_transport.read_state()
        led = snap.as_led_dict()
        try:
            await self.led_changed(
                on=bool(led.get("on", False)),
                brightness=float(led.get("brightness", 0.0)),
                effect=str(led.get("effect", "none")),
                manual_override=bool(led.get("manual_override", False)),
            )
        except RuntimeError as exc:
            if "Driver not associated with a DeviceRuntime" not in str(exc):
                raise

    @staticmethod
    async def _sleep_poll() -> None:
        import asyncio

        await asyncio.sleep(0.05)
