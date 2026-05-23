"""CLI for reference/sim Device Connect voice driver (on-device firmware is primary)."""

from __future__ import annotations

import argparse
import asyncio

from device_connect_voice.logging_setup import configure_driver_logging
from device_connect_voice.runtime_launcher import gather_cli_run_params, run_device_connect

configure_driver_logging()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Device Connect voice driver (sim / contract reference). "
            "Flash firmware/esphome for on-device operation."
        ),
    )
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--tenant", default=None)
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Simulated ESP32 voice state (default when not flashing hardware).",
    )
    parser.add_argument(
        "--serial-port",
        default=None,
        help="Reserved: host serial bridge to ESPHome (not implemented).",
    )
    parser.add_argument("--messaging-backend", default=None)
    parser.add_argument("--messaging-url", action="append", default=None)
    parser.add_argument("--nats-credentials-file", default=None)
    parser.add_argument("--portal", action="store_true")
    parser.add_argument("--portal-credentials", default=None)
    parser.add_argument("--portal-credentials-glob", default=None)
    parser.add_argument("--portal-credentials-dir", default=None)
    parser.add_argument(
        "--discovery-mode",
        default=None,
        choices=["d2d", "infra"],
        help="d2d = LAN Zenoh peer mesh; infra = registry (portal).",
    )
    parser.add_argument("--allow-insecure", action="store_true")
    return parser


async def _run_cli(args: argparse.Namespace) -> None:
    params = gather_cli_run_params(args)
    await run_device_connect(params)


def main() -> None:
    parser = build_parser()
    asyncio.run(_run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
