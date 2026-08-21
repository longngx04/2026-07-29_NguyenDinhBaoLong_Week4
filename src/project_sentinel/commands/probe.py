"""Lệnh `probe`: gửi một request thủ công qua Gateway để kiểm tra hạ tầng."""

from __future__ import annotations

import os
import sys
from typing import Optional

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.approval import (
    ApprovalDecision,
    build_request,
    prompt_cli,
    requires_approval,
)
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import send_probe


def cmd_probe(args) -> int:
        api_key = os.getenv("SENTINEL_GATEWAY_API_KEY", "")
        if not api_key:
            print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
            return 2

        try:
            allowlist = Allowlist.from_json(args.allowlist)
        except (OSError, ValueError) as exc:
            print(f"Error: Failed to load allowlist: {exc}", file=sys.stderr)
            return 2

        probe = SafeProbe(method=args.method, path=args.path, payload_kind=args.payload_kind)
        probe_decision: Optional[ApprovalDecision] = None
        if requires_approval(probe):
            probe_decision = prompt_cli(
                build_request("cli", probe, purpose="Probe khởi động thủ công từ CLI")
            )

        outcome = send_probe(
            probe, allowlist, api_key, approval=probe_decision, log_path=str(args.log)
        )
        if not outcome.sent:
            print(f"DENIED: {outcome.denied_reason}")
            return 1
        print(f"SENT: {args.method} {args.path} -> {outcome.status_code} ({outcome.elapsed_ms}ms)")
        return 0
