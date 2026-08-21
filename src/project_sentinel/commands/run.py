"""Lệnh `run`: chạy chín bước đầu-cuối, dừng giữa chừng chờ phê duyệt."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from project_sentinel.commands.shared import _read_approval_request
from project_sentinel.guardrails.approval import ApprovalDecision, prompt_cli, write_decision
from project_sentinel.orchestrator import (
    RunContext,
    RunState,
    resume_run,
    start_run,
)


def cmd_run(args) -> int:
        ctx = RunContext.default()
        if not ctx.gateway_api_key:
            print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
            return 2

        if bool(args.probe_method) != bool(args.probe_path):
            print(
                "Error: --probe-method và --probe-path phải đi cùng nhau",
                file=sys.stderr,
            )
            return 2
        if args.probe_method:
            ctx = ctx.replace(
                probe_override={
                    "description": "Bước kiểm chứng do người vận hành chỉ định",
                    "endpoint_hint": f"{args.probe_method} {args.probe_path}",
                    "payload_kind": args.probe_payload_kind,
                    "rationale": (
                        "Người vận hành chọn request này để quan sát phản hồi; "
                        "allowlist Gateway vẫn kiểm tra như thường."
                    ),
                }
            )
        record = start_run(ctx)
        print(f"Lần chạy {record.run_id}: {record.state.value}")

        if record.state is RunState.FAILED:
            print(f"Lỗi: {record.error}", file=sys.stderr)
            return 1

        if record.state is RunState.AWAITING_APPROVAL:
            request_path = record.root / "approval-request.json"
            try:
                request = _read_approval_request(request_path)
            except (OSError, ValueError, TypeError) as exc:
                print(f"Error: Không đọc được phiếu duyệt: {exc}", file=sys.stderr)
                return 2

            if args.yes:
                decision = ApprovalDecision(
                    approved=True,
                    decided_at=datetime.now(timezone.utc).isoformat(),
                    decided_by="cli-auto",
                    request_fingerprint=request.request_fingerprint,
                )
            else:
                decision = prompt_cli(request)

            try:
                write_decision(record.root / "decision.json", decision)
                record = resume_run(ctx, record.run_id)
            except (OSError, ValueError) as exc:
                print(f"Error: Không tiếp tục được lần chạy: {exc}", file=sys.stderr)
                return 2

        print(f"Kết thúc: {record.state.value}")
        report_path = record.root / "report.md"
        if report_path.exists():
            print(f"Báo cáo: {report_path}")
        if record.state is RunState.FAILED:
            print(f"Lỗi: {record.error}", file=sys.stderr)
            return 1
        return 0
