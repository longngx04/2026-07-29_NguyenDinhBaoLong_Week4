"""Chín bước của luồng. Mỗi bước là một hàm thuần (record, ctx) -> record.

Bước nào hỏng thì ném StepFailure với thông điệp đọc được; runner bắt lại và
chuyển trạng thái sang FAILED.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.config import AppConfig
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.events import append_event
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.probe.proposal import validate_objective

SUBPROCESS_TIMEOUT_SECONDS = 900


class StepFailure(Exception):
    """Một bước không hoàn thành được, kèm lý do cho người đọc."""


def _run_command(
    command: list[str], *, cwd: Path, step: str, root: str | Path
) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise StepFailure(f"Bước {step} quá hạn {SUBPROCESS_TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise StepFailure(f"Bước {step} không chạy được lệnh: {exc}") from exc

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:]
        raise StepFailure(f"Bước {step} thất bại (mã {result.returncode}): {tail}")

    if result.stdout and result.stdout.strip():
        append_log(root, step=step, level="info", message=result.stdout.strip())


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

    detail = {
        "input_findings": int(summary.get("input_finding_count", 0)),
        "groups": int(summary.get("group_count", 0)),
        "records": int(summary.get("output_record_count", 0)),
        "llm_calls": int(summary.get("llm_call_count", 0)),
        "invalid_outputs": int(summary.get("invalid_output_count", 0)),
    }
    record.mark_step("analyze", "done", detail=detail)
    append_log(
        record.root,
        step="analyze",
        level="info",
        message="Phân tích xong",
        **detail,
    )
    return record


def step_propose(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 4 — lấy đề xuất của agent và kẹp nó về đúng allowlist."""
    source = record.root / "analysis.jsonl"
    if not source.exists():
        raise StepFailure(
            "Không có analysis.jsonl để lấy đề xuất; bước analyze chưa chạy"
        )

    record.mark_step("propose", "running")

    objective = None
    analysis_id = None
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StepFailure(
                f"analysis.jsonl chứa dòng JSON không hợp lệ: {exc}"
            ) from exc
        if not isinstance(entry, dict):
            raise StepFailure("analysis.jsonl chứa dòng không phải JSON object")
        if entry.get("verification_objective"):
            objective = entry["verification_objective"]
            analysis_id = entry.get("analysis_id")
            break

    allowlist = Allowlist.from_json(ctx.allowlist_path)
    decision = validate_objective(objective, allowlist)

    payload = {
        "accepted": decision.accepted,
        "reason": decision.reason,
        "probe": (
            {
                "method": decision.probe.method,
                "path": decision.probe.path,
                "payload_kind": decision.probe.payload_kind,
            }
            if decision.probe
            else None
        ),
        "source_analysis_id": analysis_id,
        "objective": objective,
    }
    (record.root / "proposal.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if objective is not None and not decision.accepted:
        append_event(
            record.root / "events.jsonl",
            run_id=record.run_id,
            kind="allowlist_block",
            detail={
                "endpoint_hint": objective.get("endpoint_hint")
                if isinstance(objective, dict)
                else None,
                "reason": decision.reason,
            },
        )
        append_log(
            record.root,
            step="propose",
            level="warn",
            message=f"Đề xuất bị chặn: {decision.reason}",
        )
    else:
        append_log(
            record.root,
            step="propose",
            level="info",
            message=decision.reason,
        )

    record.mark_step("propose", "done", detail={"accepted": decision.accepted})
    return record
