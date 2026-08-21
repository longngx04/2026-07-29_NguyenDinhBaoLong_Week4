"""Dựng báo cáo cuối từ các artifact của một lần chạy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_sentinel.guardrails.events import count_by_kind, read_events
from project_sentinel.orchestrator.state import RunRecord


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def _nonnegative_count(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def build_report(record: RunRecord) -> tuple[str, dict]:
    """Trả về (markdown, dữ liệu json) của báo cáo cuối."""
    root = record.root
    findings_payload = _read_json(root / "findings.json", {})
    findings = (
        findings_payload.get("findings", [])
        if isinstance(findings_payload, dict)
        else []
    )
    if not isinstance(findings, list):
        findings = []

    analyses = _read_jsonl(root / "analysis.jsonl")
    proposal = _read_json(root / "proposal.json", {})
    probe = _read_json(root / "probe-result.json", {})
    scrubbed = _read_json(root / "scrubbed.json", {})
    proposal = proposal if isinstance(proposal, dict) else {}
    probe = probe if isinstance(probe, dict) else {}
    scrubbed = scrubbed if isinstance(scrubbed, dict) else {}
    events = read_events(root / "events.jsonl")
    event_counts = count_by_kind(events)
    approvers: set[str] = set()
    for event in events:
        if event.get("kind") != "approval":
            continue
        detail = event.get("detail")
        if not isinstance(detail, dict):
            continue
        who = detail.get("decided_by")
        if who:
            approvers.add(str(who))
    approval_decided_by = sorted(approvers)

    analysis_summary = _read_json(root / "analysis-summary.json", {})
    analysis_summary = (
        analysis_summary if isinstance(analysis_summary, dict) else {}
    )
    llm_calls = _nonnegative_count(analysis_summary.get("llm_call_count"))
    invalid_outputs = _nonnegative_count(
        analysis_summary.get("invalid_output_count")
    )

    severities: dict[str, int] = {}
    for item in analyses:
        key = item.get("severity", "unknown")
        severities[key] = severities.get(key, 0) + 1

    injection = scrubbed.get("injection", {})
    injection = injection if isinstance(injection, dict) else {}
    data = {
        "run_id": record.run_id,
        "state": record.state.value,
        "created_at": record.created_at,
        "findings_total": len(findings),
        "analysis_groups": len(analyses),
        "severities": severities,
        "proposal_accepted": bool(proposal.get("accepted")),
        "probe_sent": bool(probe.get("sent")),
        "probe_status_code": probe.get("status_code"),
        "injection_verdict": injection.get("verdict"),
        "event_counts": event_counts,
        "approval_decided_by": approval_decided_by,
        "llm": {"calls": llm_calls, "invalid_outputs": invalid_outputs},
    }

    approver_text = ", ".join(approval_decided_by) or "(không có bước phê duyệt)"

    lines: list[str] = [
        f"# Báo cáo bảo mật — lần chạy `{record.run_id}`",
        "",
        "## Tổng quan",
        "",
        f"- Trạng thái: **{record.state.value}**",
        f"- Cảnh báo thô: **{len(findings)}**",
        f"- Nhóm sau phân tích: **{len(analyses)}**",
        f"- Mức nghiêm trọng: {severities or 'không có'}",
        f"- Người phê duyệt: {approver_text}",
    ]
    if "cli-auto" in approvers:
        lines.append(
            "> Lần chạy này dùng `--yes`: phê duyệt tự động, "
            "KHÔNG có người vận hành xác nhận."
        )
    lines += [
        f"- Lời gọi LLM: {llm_calls} "
        f"({invalid_outputs} phản hồi không hợp lệ)",
        "",
        "## Phát hiện",
        "",
    ]

    if not analyses:
        lines.append("Không có phát hiện nào.")
    for item in analyses:
        locations = ", ".join(
            f"{location.get('file')}:{location.get('line')}"
            for location in item.get("locations", [])
        )
        remediation = item.get("remediation", [])
        if not isinstance(remediation, list):
            remediation = []
        lines += [
            f"### {item.get('title', 'Không tên')} — `{item.get('severity', '?')}`",
            "",
            f"- Vị trí: {locations or 'không rõ'}",
            f"- Độ tin cậy: {item.get('confidence', '?')}",
            f"- Giải thích: {item.get('explanation', '')}",
            f"- Khắc phục: {'; '.join(str(value) for value in remediation) or 'chưa có'}",
            "",
        ]

    lines += ["## Kiểm chứng", ""]
    if proposal.get("accepted"):
        target = proposal.get("probe", {})
        target = target if isinstance(target, dict) else {}
        lines.append(
            f"- Agent đề xuất: `{target.get('method')} {target.get('path')}`"
        )
    else:
        lines.append(
            f"- Không có probe nào được gửi: {proposal.get('reason', 'không rõ')}"
        )

    if probe.get("sent"):
        lines.append(
            f"- Kết quả qua Gateway: HTTP **{probe.get('status_code')}** "
            f"trong {probe.get('elapsed_ms')}ms"
        )
    elif probe.get("denied_reason"):
        lines.append(f"- Bị chặn: {probe['denied_reason']}")

    lines += ["", "## Sự kiện bảo mật", ""]
    if event_counts:
        for kind, count in sorted(event_counts.items()):
            lines.append(f"- `{kind}`: {count}")
    else:
        lines.append("Không ghi nhận sự kiện nào.")

    if injection.get("verdict") == "suspicious":
        lines += [
            "",
            "> Response từ ứng dụng chứa nội dung cố gắng điều khiển agent. "
            "Nội dung đó đã bị cắt bỏ trước khi vào prompt.",
        ]

    return "\n".join(lines) + "\n", data
