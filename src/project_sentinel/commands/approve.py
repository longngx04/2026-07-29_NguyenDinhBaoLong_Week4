"""Lệnh `approve`: người vận hành duyệt hoặc từ chối một request đã đề xuất."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from project_sentinel.commands.shared import _read_approval_request
from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.orchestrator import (
    RunContext,
    RunState,
    list_runs,
    load_run,
    resume_run,
)


def cmd_approve(args) -> int:
        ctx = RunContext.default()
        if args.run_id not in set(list_runs(ctx.runs_dir)):
            print(f"Error: Không tìm thấy lần chạy {args.run_id}", file=sys.stderr)
            return 2

        try:
            record = load_run(ctx.runs_dir, args.run_id)
        except (OSError, ValueError, KeyError):
            print(f"Error: Không đọc được lần chạy {args.run_id}", file=sys.stderr)
            return 2

        if record.state is not RunState.AWAITING_APPROVAL:
            print(
                f"Error: Lần chạy {args.run_id} đang ở {record.state.value}, "
                "không chờ phê duyệt",
                file=sys.stderr,
            )
            return 2
        if args.decision == "approve" and not ctx.gateway_api_key:
            print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
            return 2

        try:
            request = _read_approval_request(record.root / "approval-request.json")
        except (OSError, ValueError, TypeError) as exc:
            print(f"Error: Không đọc được phiếu duyệt: {exc}", file=sys.stderr)
            return 2

        decision = ApprovalDecision(
            approved=args.decision == "approve",
            decided_at=datetime.now(timezone.utc).isoformat(),
            decided_by="cli-operator",
            request_fingerprint=request.request_fingerprint,
        )
        try:
            write_decision(record.root / "decision.json", decision)
            record = resume_run(ctx, args.run_id)
        except (OSError, ValueError) as exc:
            print(f"Error: Không tiếp tục được lần chạy: {exc}", file=sys.stderr)
            return 2

        print(f"Lần chạy {args.run_id}: {record.state.value}")
        report_path = record.root / "report.md"
        if report_path.exists():
            print(f"Báo cáo: {report_path}")
        if record.state is RunState.FAILED:
            print(f"Lỗi: {record.error}", file=sys.stderr)
            return 1
        return 0
