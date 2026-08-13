from __future__ import annotations
import argparse
import os
import sys
from .allowlist import Allowlist
from .client import GatewayClient
from .models import SafePayloadType

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_BLOCKED = 3
EXIT_NETWORK_ERROR = 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    req = sub.add_parser("request")
    req.add_argument("--method", required=True)
    req.add_argument("--path", required=True)
    req.add_argument("--payload-type", choices=[p.value for p in SafePayloadType])
    req.add_argument("--target-field")
    req.add_argument("--base-url", default="http://127.0.0.1:9080")
    req.add_argument("--allowlist", default="configs/gateway/allowlist.yaml")
    req.add_argument("--log-path", default="artifacts/gateway/requests.log.jsonl")

    args = parser.parse_args(argv)

    api_key = os.environ.get("SENTINEL_API_KEY")
    if not api_key:
        print("Lỗi: thiếu biến môi trường SENTINEL_API_KEY", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        allowlist = Allowlist.from_yaml(args.allowlist)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Lỗi cấu hình allowlist: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    client = GatewayClient(args.base_url, api_key, allowlist, args.log_path)
    payload_type = SafePayloadType(args.payload_type) if args.payload_type else None
    result = client.request(args.method, args.path, payload_type, args.target_field)

    if result.error_type and result.error_type.value == "forbidden_by_allowlist":
        print("Bị chặn: endpoint không nằm trong allowlist", file=sys.stderr)
        return EXIT_BLOCKED
    if result.error_type and result.error_type.value in ("timeout", "connection"):
        print(f"Lỗi mạng: {result.error_type.value}", file=sys.stderr)
        return EXIT_NETWORK_ERROR

    print(f"status={result.status_code} elapsed_ms={result.elapsed_ms}")
    print(result.body_preview[:500] if result.body_preview else "(empty)")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
