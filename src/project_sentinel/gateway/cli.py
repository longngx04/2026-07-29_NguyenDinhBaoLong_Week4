"""Operator demo CLI routing strictly through probe tool."""

from __future__ import annotations

import argparse
import os
import sys

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import send_probe

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_BLOCKED = 3
EXIT_NETWORK_ERROR = 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--method", default="GET")
    request_parser.add_argument("--path", default="/WebGoat/actuator/health")
    request_parser.add_argument("--payload-kind", default=None)
    request_parser.add_argument("--allowlist", default="configs/gateway/endpoint-allowlist.json")
    request_parser.add_argument("--log-path", default="artifacts/gateway/requests.log.jsonl")
    args = parser.parse_args(argv)

    api_key = os.environ.get("SENTINEL_GATEWAY_API_KEY")
    if not api_key:
        print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        allowlist = Allowlist.from_json(args.allowlist)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    outcome = send_probe(
        SafeProbe(method=args.method, path=args.path, payload_kind=args.payload_kind),
        allowlist,
        api_key,
        log_path=args.log_path,
    )
    if not outcome.sent:
        print(f"Blocked: {outcome.denied_reason}", file=sys.stderr)
        return EXIT_BLOCKED
    if outcome.error_class is not None:
        print(f"Network error: {outcome.error_reason}", file=sys.stderr)
        return EXIT_NETWORK_ERROR

    return EXIT_OK
