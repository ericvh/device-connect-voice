"""Device Connect mesh helpers for portal credentials (erivan01-voice)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_PORTAL_CREDENTIALS",
    "connect_mesh",
    "disconnect_mesh",
    "load_portal_credentials_metadata",
    "resolve_mesh_settings",
    "wait_for_device",
]

DEFAULT_PORTAL_CREDENTIALS = Path.home() / "Downloads" / "erivan01-voice.creds.json"


def load_portal_credentials_metadata(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in credentials file: {path}")
    nats = data.get("nats") or {}
    urls = nats.get("urls", ()) if isinstance(nats, dict) else ()
    if isinstance(urls, str):
        urls = (urls,) if urls.strip() else ()
    return {
        "device_id": data.get("device_id"),
        "tenant": data.get("tenant"),
        "messaging_urls": tuple(urls) if isinstance(urls, list) else urls,
    }


def resolve_mesh_settings(
    *,
    credentials_file: str | Path | None = None,
    tenant: str | None = None,
    device_id: str | None = None,
) -> tuple[str, str | None, tuple[str, ...]]:
    creds_path = Path(
        credentials_file
        or os.environ.get("NATS_CREDENTIALS_FILE")
        or os.environ.get("PORTAL_CREDENTIALS_FILE")
        or DEFAULT_PORTAL_CREDENTIALS
    ).expanduser()
    meta: dict[str, Any] = {}
    if creds_path.is_file():
        meta = load_portal_credentials_metadata(creds_path)

    zone = tenant or os.environ.get("TENANT") or meta.get("tenant") or "default"
    resolved_device_id = device_id or meta.get("device_id")
    urls = tuple(
        url.strip()
        for url in (
            os.environ.get("MESSAGING_URLS", "")
            or os.environ.get("NATS_URL", "")
            or ",".join(meta.get("messaging_urls", ()))
        ).split(",")
        if url.strip()
    )
    return zone, resolved_device_id, urls


def connect_mesh(*, credentials_file: str | Path | None = None) -> None:
    """Connect to portal using tenant/URLs from the credentials file."""
    from device_connect_agent_tools import connect

    path = Path(
        credentials_file
        or os.environ.get("NATS_CREDENTIALS_FILE")
        or DEFAULT_PORTAL_CREDENTIALS
    ).expanduser()
    os.environ.setdefault("NATS_CREDENTIALS_FILE", str(path))
    zone, _, urls = resolve_mesh_settings(credentials_file=path)
    os.environ.setdefault("TENANT", zone)
    os.environ.setdefault("MESSAGING_BACKEND", "nats")
    if urls:
        os.environ.setdefault("MESSAGING_URLS", ",".join(urls))
    connect()


def disconnect_mesh() -> None:
    from device_connect_agent_tools import disconnect

    disconnect()


def wait_for_device(device_id: str, *, timeout_s: float = 60.0, poll_s: float = 2.0) -> bool:
    from device_connect_agent_tools.tools import discover_devices

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        devices = discover_devices(device_type="whisper") or []
        for entry in devices:
            did = entry.get("device_id") if isinstance(entry, dict) else getattr(entry, "device_id", None)
            if did == device_id:
                return True
        time.sleep(poll_s)
    return False
