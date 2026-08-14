"""Operator demo CLI using the same safe executor as ``make verify``."""

from __future__ import annotations

import argparse
import os
import sys

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import execute_candidate
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision, VerificationStatus
from project_sentinel.verification.rate_limit import ToolRateLimiter
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import RealTransport

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_BLOCKED = 3
EXIT_NETWORK_ERROR = 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--template-id", default="tmpl_health_get")
    request_parser.add_argument("--allowlist", default="configs/gateway/endpoint-allowlist.json")
    request_parser.add_argument("--templates", default="configs/verification/probe-templates.json")
    request_parser.add_argument("--log-path", default="artifacts/gateway/requests.log.jsonl")
    args = parser.parse_args(argv)

    api_key = os.environ.get("SENTINEL_GATEWAY_API_KEY")
    if not api_key:
        print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        allowlist = Allowlist.from_json(args.allowlist)
        templates = ProbeTemplateRegistry.from_json(args.templates)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    template = templates.get(args.template_id)
    if template is None:
        print("Blocked: template_id is not in the reviewed registry", file=sys.stderr)
        return EXIT_BLOCKED
    rule = allowlist.get_rule(template.endpoint_id, template.method)
    if rule is None:
        print("Blocked: template has no matching endpoint rule", file=sys.stderr)
        return EXIT_BLOCKED
    candidate = VerificationCandidate(
        candidate_id="gateway-demo",
        objective_id="operator-demo",
        proposal_id="operator-demo",
        decision=VerificationDecision.PLANNED,
        endpoint_id=template.endpoint_id,
        template_id=template.template_id,
        method=template.method,
        path=rule.path,
        target_field=template.target_field,
        payload_type=template.payload_type,
        reason="Operator selected a reviewed template",
    )
    result = execute_candidate(
        candidate,
        RealTransport(),
        allowlist,
        templates,
        api_key,
        rate_limiter=ToolRateLimiter(requests_per_minute=30, burst=5),
        log_path=args.log_path,
    )
    status_str = result.status.value if hasattr(result.status, "value") else str(result.status)
    print(f"status={status_str} http_status={result.status_code} elapsed_ms={result.execution_time_ms}")
    if status_str == VerificationStatus.DENIED.value:
        return EXIT_BLOCKED
    if status_str in {VerificationStatus.UNREACHABLE.value, VerificationStatus.FAILED.value}:
        return EXIT_NETWORK_ERROR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
