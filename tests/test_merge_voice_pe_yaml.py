"""Tests for firmware YAML merge helper (offline)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MERGE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_voice_pe_yaml.py"
_spec = importlib.util.spec_from_file_location("merge_voice_pe_yaml", _MERGE_SCRIPT)
assert _spec and _spec.loader
_merge_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_merge_module)
merge = _merge_module.merge

MINIMAL_UPSTREAM = """
substitutions:
  name: test
esphome:
  name: test
wifi:
  id: wifi_id
external_components:
  - git: https://example/voice-kit
    refresh: 0s

audio_dac:
  - platform: dummy
globals:
  - id: voice_assistant_phase
    type: int
    initial_value: ${voice_assist_not_ready_phase_id}
voice_assistant:
  on_stt_vad_start:
    - logger.log: start
micro_wake_word:
  on_wake_word_detected:
    - logger.log: wake
"""


def test_merge_injects_device_connect_blocks() -> None:
    merged = merge(
        MINIMAL_UPSTREAM,
        upstream_ref="test",
        upstream_url="https://example/upstream.yaml",
    )

    assert "dc_device_id:" in merged
    assert "device_connect:" in merged
    assert "dc_last_transcript" in merged
    assert "id(dc).on_wake_word_detected" in merged
    assert "id(dc).on_stt_text" in merged
    assert merged.startswith("# Merged Home Assistant Voice PE")


def test_merge_rejects_duplicate_dc_substitutions() -> None:
    upstream = MINIMAL_UPSTREAM.replace(
        "substitutions:",
        "substitutions:\n  dc_device_id: already",
        1,
    )

    with pytest.raises(SystemExit):
        merge(upstream, upstream_ref="test", upstream_url="https://example")
