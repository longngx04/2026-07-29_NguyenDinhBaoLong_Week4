"""Bước 1–3: quét, chuẩn hoá, phân tích. Đưa dữ liệu vào luồng."""

from __future__ import annotations

import json
import shutil

from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.config import AppConfig
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.orchestrator.steps.common import StepFailure, _run_command

def step_scan(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 1 — chạy SAST, ghi raw.json vào thư mục run."""
    record.state = RunState.SCANNING
    record.mark_step("scan", "running")
    append_log(record.root, step="scan", level="info", message="Bắt đầu quét mã nguồn")

    target = record.root / "raw.json"
    _run_command(
        [*ctx.scan_command, str(target)],
        cwd=ctx.repo_root,
        step="scan",
        root=record.root,
    )

    used_fallback = False
    if not target.exists():
        fallback = ctx.repo_root / "artifacts" / "raw" / "opengrep.json"
        if not fallback.exists():
            raise StepFailure("Bước scan không sinh ra raw.json")
        shutil.copy(fallback, target)
        used_fallback = True
        append_log(
            record.root,
            step="scan",
            level="warn",
            message="Lệnh quét không sinh raw.json — dùng lại báo cáo cũ trong artifacts/raw/",
        )

    try:
        report = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StepFailure(f"raw.json không phải JSON hợp lệ: {exc}") from exc

    if not isinstance(report.get("results"), list):
        raise StepFailure("raw.json thiếu mảng results — không phải báo cáo OpenGrep")

    count = len(report["results"])
    record.mark_step(
        "scan", "done", detail={"raw_results": count, "used_fallback": used_fallback}
    )
    append_log(
        record.root,
        step="scan",
        level="info",
        message="Quét xong",
        raw_results=count,
        used_fallback=used_fallback,
    )
    return record


def step_normalize(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 2 — chuẩn hoá về định dạng chung, ghi findings.json."""
    source = record.root / "raw.json"
    if not source.exists():
        raise StepFailure("Không có raw.json để chuẩn hoá; bước scan chưa chạy")

    record.state = RunState.NORMALIZING
    record.mark_step("normalize", "running")
    append_log(record.root, step="normalize", level="info", message="Bắt đầu chuẩn hoá")

    target = record.root / "findings.json"
    _run_command(
        [*ctx.normalize_command, "--input", str(source), "--output", str(target)],
        cwd=ctx.repo_root,
        step="normalize",
        root=record.root,
    )

    if not target.exists():
        raise StepFailure("Bước normalize không sinh ra findings.json")

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StepFailure(f"findings.json không phải JSON hợp lệ: {exc}") from exc

    if not isinstance(payload, dict):
        raise StepFailure("findings.json không phải JSON object — không đúng định dạng")

    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise StepFailure("findings.json thiếu mảng findings")

    record.mark_step("normalize", "done", detail={"findings": len(findings)})
    append_log(
        record.root,
        step="normalize",
        level="info",
        message="Chuẩn hoá xong",
        findings=len(findings),
    )
    return record


def step_analyze(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 3 — agent đọc findings, tra kho tri thức, sinh báo cáo JSONL."""
    source = record.root / "findings.json"
    if not source.exists():
        raise StepFailure(
            "Không có findings.json để phân tích; bước normalize chưa chạy"
        )

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StepFailure(f"findings.json không phải JSON hợp lệ: {exc}") from exc

    if not isinstance(payload, dict):
        raise StepFailure("findings.json không phải JSON object — không đúng định dạng")

    if not isinstance(payload.get("findings"), list):
        raise StepFailure("findings.json thiếu mảng findings")

    record.state = RunState.ANALYZING
    record.mark_step("analyze", "running")
    append_log(
        record.root, step="analyze", level="info", message="Bắt đầu phân tích findings"
    )

    config = AppConfig.from_env(
        input_findings_path=source,
        output_jsonl_path=record.root / "analysis.jsonl",
        summary_path=record.root / "analysis-summary.json",
    )

    try:
        summary = run_pipeline(config)
    except Exception as exc:
        append_log(
            record.root,
            step="analyze",
            level="error",
            message=f"Agent thất bại: {exc}",
        )
        raise StepFailure(f"Bước analyze thất bại: {exc}") from exc

    if not isinstance(summary, dict):
        raise StepFailure("Kết quả phân tích không hợp lệ (không phải dict)")

    try:
        detail = {
            "input_findings": int(summary.get("input_finding_count", 0)),
            "groups": int(summary.get("group_count", 0)),
            "records": int(summary.get("output_record_count", 0)),
            "llm_calls": int(summary.get("llm_call_count", 0)),
            "invalid_outputs": int(summary.get("invalid_output_count", 0)),
        }
    except (TypeError, ValueError) as exc:
        raise StepFailure(
            f"Tóm tắt phân tích có số liệu không hợp lệ: {exc}"
        ) from exc

    record.mark_step("analyze", "done", detail=detail)
    append_log(
        record.root,
        step="analyze",
        level="info",
        message="Phân tích xong",
        **detail,
    )
    return record



__all__ = ["step_analyze", "step_normalize", "step_scan"]
