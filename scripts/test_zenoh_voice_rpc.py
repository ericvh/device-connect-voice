#!/usr/bin/env python3
"""Invoke device-connect-voice over Zenoh (LAN D2D or router).

Requires: pip install eclipse-zenoh, device on same LAN with zenoh_enabled.

Examples:
  ZENOH_CONNECT=tcp/192.168.1.10:7447 python scripts/test_zenoh_voice_rpc.py get_status
  python scripts/test_zenoh_voice_rpc.py get_voice_phase   # peer/multicast default
"""

from __future__ import annotations

import json
import os
import sys
import uuid

TENANT = os.environ.get("TENANT", "erivan01")
DEVICE_ID = os.environ.get("DEVICE_ID", "erivan01-voice")


def subject_to_keyexpr(subject: str) -> str:
    if "/" in subject:
        return subject
    key = subject.replace(".", "/")
    if key.endswith("/>"):
        return key[:-2] + "/**"
    return key


def main() -> int:
    try:
        import zenoh
    except ImportError:
        print("Install eclipse-zenoh: pip install eclipse-zenoh", file=sys.stderr)
        return 1

    method = sys.argv[1] if len(sys.argv) > 1 else "get_status"
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    connect = os.environ.get("ZENOH_CONNECT", "").strip()
    conf = zenoh.Config()
    if connect:
        conf.insert_json5("mode", '"client"')
        endpoint = connect
        if connect.startswith("zenoh://"):
            endpoint = "tcp/" + connect[len("zenoh://") :]
        elif connect.startswith("zenoh+tls://"):
            endpoint = "tls/" + connect[len("zenoh+tls://") :]
        elif "/" not in connect:
            endpoint = "tcp/" + connect
        conf.insert_json5("connect/endpoints", json.dumps([endpoint]))
    else:
        conf.insert_json5("mode", '"peer"')

    cmd_subject = f"device-connect.{TENANT}.{DEVICE_ID}.cmd"
    key = subject_to_keyexpr(cmd_subject)
    req_id = f"test-{uuid.uuid4().hex[:8]}"
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    ).encode()

    print(f"Zenoh query {key} method={method}")
    with zenoh.open(conf) as session:
        replies = session.get(key, payload=payload, timeout=15)
        for reply in replies:
            if reply.ok is None:
                print("no reply", file=sys.stderr)
                continue
            data = bytes(reply.ok.payload)
            print(data.decode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
