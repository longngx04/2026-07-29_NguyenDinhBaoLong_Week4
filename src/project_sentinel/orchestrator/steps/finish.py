"""Bước 8–9: dựng báo cáo cho người đọc rồi chốt trạng thái kết thúc."""

from __future__ import annotations

import json

from project_sentinel.guardrails.redaction import redact
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.report import build_report
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.orchestrator.steps.common import (
    StepFailure,
    _write_json_artifact,
)

def step_report(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 8 — dựng báo cáo cuối."""
    record.state = RunState.REPORTING
    record.mark_step("report", "running")

    try:
        markdown, data = build_report(record)
    except (OSError, ValueError) as exc:
        raise StepFailure(f"Không dựng được báo cáo: {exc}") from exc
    safe_markdown, _ = redact(markdown)
    (record.root / "report.md").write_text(safe_markdown, encoding="utf-8")
    _write_json_artifact(record.root / "report.json", data)

    record.mark_step(
        "report", "done", detail={"findings_total": data["findings_total"]}
    )
    append_log(
        record.root,
        step="report",
        level="info",
        message="Đã dựng báo cáo cuối",
    )
    return record


def step_finalize(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 9 — chốt số liệu và đặt trạng thái kết thúc."""
    from project_sentinel.orchestrator.metrics import collect_metrics

    record.mark_step("finalize", "running")

    if not record.state.is_terminal():
        record.state = RunState.DONE

    metrics = collect_metrics(record)
    _write_json_artifact(record.root / "metrics.json", metrics)

    report_path = record.root / "report.json"
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            data = None
        if isinstance(data, dict):
            data["state"] = record.state.value
            _write_json_artifact(report_path, data)

    report_md = record.root / "report.md"
    if report_md.exists():
        text = report_md.read_text(encoding="utf-8")
        text = text.replace(
            "- Trạng thái: **REPORTING**",
            f"- Trạng thái: **{record.state.value}**",
            1,
        )
        report_md.write_text(text, encoding="utf-8")

    record.mark_step(
        "finalize", "done", detail={"total_ms": metrics["total_elapsed_ms"]}
    )
    append_log(
        record.root,
        step="finalize",
        level="info",
        message="Kết thúc lần chạy",
        state=record.state.value,
    )
    return record

__all__ = ["step_finalize", "step_report"]
