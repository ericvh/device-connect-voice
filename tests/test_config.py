"""Tests for portal and driver configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from device_connect_voice.config import (
    DriverConfig,
    apply_portal_config,
    find_portal_credentials_file,
    load_portal_credentials,
    resolve_portal_credentials_file,
)


def test_driver_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVICE_ID", "test-voice")
    monkeypatch.setenv("TENANT", "acme")
    monkeypatch.setenv("VOICE_SIM", "true")
    monkeypatch.setenv("MESSAGING_URLS", "nats://a:4222, nats://b:4222")
    monkeypatch.setenv("DEVICE_CONNECT_ALLOW_INSECURE", "yes")
    monkeypatch.setenv("DEVICE_CONNECT_PORTAL", "1")
    monkeypatch.setenv("DEVICE_CONNECT_LOCAL_ZENOH_ROUTES", "tcp/10.0.0.1:7447")

    config = DriverConfig.from_env()

    assert config.device_id == "test-voice"
    assert config.tenant == "acme"
    assert config.simulate is True
    assert config.messaging_urls == ("nats://a:4222", "nats://b:4222")
    assert config.allow_insecure is True
    assert config.portal is True
    assert config.local_zenoh_routes == ("tcp/10.0.0.1:7447",)


def test_load_portal_credentials(tmp_path: Path) -> None:
    creds_path = tmp_path / "tenant-device.creds.json"
    creds_path.write_text(
        json.dumps(
            {
                "device_id": "tenant-device",
                "tenant": "tenant",
                "nats": {"urls": ["nats://portal.example:4222"]},
            }
        ),
        encoding="utf-8",
    )

    creds = load_portal_credentials(creds_path)

    assert creds.path == creds_path
    assert creds.device_id == "tenant-device"
    assert creds.tenant == "tenant"
    assert creds.messaging_urls == ("nats://portal.example:4222",)


def test_load_portal_credentials_rejects_non_object(tmp_path: Path) -> None:
    creds_path = tmp_path / "bad.creds.json"
    creds_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_portal_credentials(creds_path)


def test_find_portal_credentials_file_picks_newest_match(tmp_path: Path) -> None:
    older = tmp_path / "erivan01-old.json"
    newer = tmp_path / "erivan01-new.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    newer.touch()

    found = find_portal_credentials_file(pattern="erivan01*.json", search_dir=tmp_path)

    assert found == newer


def test_resolve_portal_credentials_explicit_path() -> None:
    assert (
        resolve_portal_credentials_file(
            explicit_path="/tmp/explicit.creds.json",
            portal=True,
            pattern="*.json",
            search_dir="/tmp",
        )
        == "/tmp/explicit.creds.json"
    )


def test_resolve_portal_credentials_skips_when_not_portal() -> None:
    assert (
        resolve_portal_credentials_file(
            explicit_path=None,
            portal=False,
            pattern="*.json",
            search_dir="/tmp",
        )
        is None
    )


def test_apply_portal_config_fills_messaging_and_ids() -> None:
    from device_connect_voice.config import PortalCredentials

    base = DriverConfig(
        device_id="fallback-device",
        tenant="fallback-tenant",
        portal=True,
    )
    portal = PortalCredentials(
        path=Path("/tmp/x.creds.json"),
        device_id="portal-device",
        tenant="portal-tenant",
        messaging_urls=("nats://from-creds:4222",),
    )

    updated = apply_portal_config(
        base,
        portal_credentials=portal,
        explicit_device_id=None,
        explicit_tenant=None,
    )

    assert updated.device_id == "portal-device"
    assert updated.tenant == "portal-tenant"
    assert updated.messaging_backend == "nats"
    assert updated.messaging_urls == ("nats://from-creds:4222",)
    assert updated.discovery_mode == "infra"


def test_apply_portal_config_noop_when_portal_disabled() -> None:
    base = DriverConfig(portal=False, device_id="local")
    updated = apply_portal_config(
        base,
        portal_credentials=None,
        explicit_device_id="override",
        explicit_tenant="override-tenant",
    )
    assert updated is base
