"""Bước 6–7: gửi request đã duyệt qua Gateway, rồi lọc response nhận về.

Response từ ứng dụng đích là dữ liệu không đáng tin. Nó bị quét injection rồi
mới tới bộ che — theo đúng thứ tự đó, vì bỏ chỉ dẫn tấn công đi trước thì bộ che
không phải xử lý nội dung do kẻ tấn công dựng riêng để đánh lừa nó.
"""

from __future__ import annotations

import json

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.approval import read_decision
from project_sentinel.guardrails.events import append_event
from project_sentinel.guardrails.injection import scan as scan_injection
from project_sentinel.guardrails.injection import wrap_untrusted
from project_sentinel.guardrails.redaction import (
    RedactionEvent,
    merge_events,
    redact,
)
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.orchestrator.steps.common import (
    StepFailure,
    _write_json_artifact,
)
from project_sentinel.orchestrator.steps.propose import _load_proposal
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import send_probe

def step_probe(
    record: RunRecord, ctx: RunContext, *, transport=None
) -> RunRecord:
    """Bước 6 — gửi request đã được duyệt qua Gateway."""
    proposal = _load_proposal(record)
    decision = read_decision(record.root / "decision.json")

    if decision is not None:
        record.mark_step(
            "approval", "done", detail={"approved": decision.approved}
        )

    if not proposal.get("accepted") or not proposal.get("probe"):
        outcome = {
            "sent": False,
            "denied_reason": proposal.get("reason", "Không có probe"),
        }
        _write_json_artifact(record.root / "probe-result.json", outcome)
        record.mark_step("probe", "skipped", detail=outcome)
        return record

    record.state = RunState.PROBING
    record.mark_step("probe", "running")

    try:
        probe = SafeProbe(**proposal["probe"])
        allowlist = Allowlist.from_json(ctx.allowlist_path)
    except (OSError, TypeError, ValueError) as exc:
        raise StepFailure(f"Không dựng được probe an toàn: {exc}") from exc

    result = send_probe(
        probe,
        allowlist,
        ctx.gateway_api_key,
        approval=decision,
        transport=transport,
        log_path=str(record.root / "gateway-requests.jsonl"),
        events_path=str(record.root / "events.jsonl"),
    )

    outcome = {
        "sent": result.sent,
        "status_code": result.status_code,
        "body_preview": result.body_preview,
        "elapsed_ms": result.elapsed_ms,
        "error_class": result.error_class,
        "error_reason": result.error_reason,
        "denied_reason": result.denied_reason,
        # body_preview về tới đây đã sạch. Không mang theo con số này thì bước
        # scrub chỉ thấy chuỗi đã che và sẽ báo "0 redaction" cho một response
        # thật sự có dữ liệu nhạy cảm.
        "redactions": [
            {"kind": event.kind, "count": event.count}
            for event in result.redactions
        ],
    }
    _write_json_artifact(record.root / "probe-result.json", outcome)

    if not result.sent:
        record.state = (
            RunState.REJECTED
            if decision is not None and not decision.approved
            else RunState.PROBING
        )
        record.mark_step(
            "probe", "skipped", detail={"denied_reason": result.denied_reason}
        )
        append_log(
            record.root,
            step="probe",
            level="warn",
            message=f"Không gửi request: {result.denied_reason}",
        )
        return record

    record.mark_step("probe", "done", detail={"status_code": result.status_code})
    append_log(
        record.root,
        step="probe",
        level="info",
        message="Đã gửi request qua Gateway",
        status_code=result.status_code,
    )
    return record


def _read_probe_result(record: RunRecord) -> dict:
    source = record.root / "probe-result.json"
    if not source.exists():
        return {}
    try:
        result = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StepFailure(f"Không đọc được probe-result.json: {exc}") from exc
    if not isinstance(result, dict):
        raise StepFailure("probe-result.json không phải JSON object")
    return result


def _upstream_redactions(probe: dict) -> list[RedactionEvent]:
    """Đọc lại số liệu redaction do cửa ra `send_probe` ghi vào probe-result.json.

    File này người khác có thể sửa, nên mọi dòng hỏng bị bỏ qua thay vì làm
    sập bước scrub — thà báo thiếu còn hơn mất cả lần chạy.
    """
    raw = probe.get("redactions")
    if not isinstance(raw, list):
        return []
    events: list[RedactionEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        count = item.get("count")
        if not isinstance(kind, str) or not kind:
            continue
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            continue
        events.append(RedactionEvent(kind=kind, count=count))
    return events


def step_scrub(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 7 — quét injection rồi che PII, theo đúng thứ tự đó."""
    probe = _read_probe_result(record)
    if not probe.get("sent"):
        record.mark_step(
            "scrub", "skipped", detail={"reason": "Không có response để lọc"}
        )
        return record

    record.state = RunState.SCRUBBING
    record.mark_step("scrub", "running")

    body = probe.get("body_preview", "") or ""
    if not isinstance(body, str):
        raise StepFailure("body_preview trong probe-result.json không phải chuỗi")
    verdict = scan_injection(body)
    if verdict.verdict == "suspicious":
        append_event(
            record.root / "events.jsonl",
            run_id=record.run_id,
            kind="injection",
            detail={
                "patterns": [match.pattern_name for match in verdict.matches],
                "excerpts": [match.excerpt for match in verdict.matches],
            },
        )
        append_log(
            record.root,
            step="scrub",
            level="warn",
            message="Phát hiện nội dung điều khiển trong response",
        )

    cleaned, found_here = redact(verdict.sanitized_text)
    redactions = merge_events([*_upstream_redactions(probe), *found_here])
    if redactions:
        append_event(
            record.root / "events.jsonl",
            run_id=record.run_id,
            kind="redaction",
            detail={
                "kinds": {redaction.kind: redaction.count for redaction in redactions}
            },
        )

    payload = {
        "original_bytes": len(body.encode("utf-8")),
        "injection": {
            "verdict": verdict.verdict,
            "matches": [
                {
                    "pattern_name": match.pattern_name,
                    "excerpt": match.excerpt,
                }
                for match in verdict.matches
            ],
        },
        "redactions": [
            {"kind": redaction.kind, "count": redaction.count}
            for redaction in redactions
        ],
        "safe_text": wrap_untrusted(cleaned),
    }
    _write_json_artifact(record.root / "scrubbed.json", payload)

    record.mark_step("scrub", "done", detail={"injection": verdict.verdict})
    return record



__all__ = ["step_probe", "step_scrub"]
