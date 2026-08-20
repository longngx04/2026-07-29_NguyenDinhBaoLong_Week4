"""Năm số liệu đề bài yêu cầu ghi lại ở tuần 6.

Thời gian xử lý · số request · số cảnh báo · số lần Approve/Reject ·
lỗi khi gọi LLM hoặc ứng dụng.
"""

from __future__ import annotations

import json
from typing import Any

from project_sentinel.guardrails.events import read_events
from project_sentinel.orchestrator.run_log import read_log
from project_sentinel.orchestrator.state import RunRecord

LLM_STEPS = frozenset({"analyze"})
APP_STEPS = frozenset({"scan", "normalize", "probe", "scrub"})


def collect_metrics(record: RunRecord) -> dict[str, Any]:
    """Thu số liệu của một lần chạy từ chính các artifact của nó."""
    step_elapsed = {
        step.name: step.elapsed_ms
        for step in record.steps
        if step.finished_at is not None
    }

    gateway_log = record.root / "gateway-requests.jsonl"
    requests_total = requests_denied = 0
    if gateway_log.exists():
        for line in gateway_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("status") == "SENT":
                requests_total += 1
            elif entry.get("status") == "DENIED":
                requests_denied += 1

    findings_total = 0
    findings_path = record.root / "findings.json"
    if findings_path.exists():
        try:
            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            findings_payload = {}
        if isinstance(findings_payload, dict):
            findings = findings_payload.get("findings", [])
            if isinstance(findings, list):
                findings_total = len(findings)

    approved = rejected = 0
    for event in read_events(record.root / "events.jsonl"):
        if event.get("kind") != "approval":
            continue
        detail = event.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        if detail.get("approved"):
            approved += 1
        else:
            rejected += 1

    llm_errors = app_errors = other_errors = 0
    for entry in read_log(record.root):
        if entry.get("level") != "error":
            continue
        step = entry.get("step")
        if step in LLM_STEPS:
            llm_errors += 1
        elif step in APP_STEPS:
            app_errors += 1
        else:
            other_errors += 1

    return {
        "run_id": record.run_id,
        "state": record.state.value,
        "total_elapsed_ms": round(sum(step_elapsed.values()), 2),
        "step_elapsed_ms": step_elapsed,
        "requests_total": requests_total,
        "requests_denied": requests_denied,
        "findings_total": findings_total,
        "approvals": {"approved": approved, "rejected": rejected},
        "errors": {
            "llm": llm_errors,
            "app": app_errors,
            "other": other_errors,
            "total": llm_errors + app_errors + other_errors,
        },
    }
