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
from project_sentinel.guardrails.approval import (
    build_request,
    read_decision,
    requires_approval,
)
from project_sentinel.guardrails.events import append_event
from project_sentinel.guardrails.injection import scan as scan_injection
from project_sentinel.guardrails.injection import wrap_untrusted
from project_sentinel.guardrails.redaction import redact, redact_structure
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.report import build_report
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.probe.proposal import SafeProbe, validate_objective
from project_sentinel.probe.tool import send_probe

SUBPROCESS_TIMEOUT_SECONDS = 900


class StepFailure(Exception):
    """Một bước không hoàn thành được, kèm lý do cho người đọc."""


def _write_json_artifact(path: Path, payload: dict) -> None:
    """Ghi JSON sau nút thắt redaction bắt buộc của orchestrator."""
    safe_payload, _ = redact_structure(payload)
    path.write_text(
        json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


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


def step_propose(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 4 — lấy đề xuất của agent và kẹp nó về đúng allowlist."""
    source = record.root / "analysis.jsonl"
    if not source.exists():
        raise StepFailure(
            "Không có analysis.jsonl để lấy đề xuất; bước analyze chưa chạy"
        )

    record.mark_step("propose", "running")

    candidates: list[tuple[str | None, dict[str, Any]]] = []
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
            candidates.append(
                (entry.get("analysis_id"), entry["verification_objective"])
            )

    analysis_id, objective = candidates[0] if candidates else (None, None)

    append_log(
        record.root,
        step="propose",
        level="info",
        message="Bắt đầu chọn đề xuất kiểm chứng",
        objectives_found=len(candidates),
        chosen_analysis_id=analysis_id,
    )

    try:
        allowlist = Allowlist.from_json(ctx.allowlist_path)
    except (OSError, ValueError) as exc:
        raise StepFailure(
            f"Không đọc được allowlist {ctx.allowlist_path}: {exc}"
        ) from exc

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
        "objectives_found": len(candidates),
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


def _load_proposal(record: RunRecord) -> dict:
    source = record.root / "proposal.json"
    if not source.exists():
        raise StepFailure("Không có proposal.json; bước propose chưa chạy")
    try:
        proposal = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StepFailure(f"Không đọc được proposal.json: {exc}") from exc
    if not isinstance(proposal, dict):
        raise StepFailure("proposal.json không phải JSON object")
    return proposal


def step_approval(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 5 — dừng lại chờ người duyệt, nếu request thuộc loại rủi ro."""
    proposal = _load_proposal(record)

    if not proposal.get("accepted") or not proposal.get("probe"):
        record.mark_step(
            "approval", "skipped", detail={"reason": "Không có probe được duyệt"}
        )
        append_log(
            record.root,
            step="approval",
            level="info",
            message="Bỏ qua phê duyệt: không có probe hợp lệ",
        )
        return record

    try:
        probe = SafeProbe(**proposal["probe"])
    except (TypeError, ValueError) as exc:
        raise StepFailure(f"Probe trong proposal.json không hợp lệ: {exc}") from exc

    if not requires_approval(probe):
        record.mark_step(
            "approval", "skipped", detail={"reason": "GET trơn, không cần duyệt"}
        )
        append_log(
            record.root,
            step="approval",
            level="info",
            message="Bỏ qua phê duyệt: request không rủi ro",
        )
        return record

    objective = proposal.get("objective")
    if not isinstance(objective, dict):
        objective = {}
    purpose = objective.get("description") or "Kiểm chứng finding"
    request = build_request(record.run_id, probe, purpose=purpose)
    _write_json_artifact(record.root / "approval-request.json", request.to_dict())

    record.state = RunState.AWAITING_APPROVAL
    record.mark_step("approval", "running")
    append_log(
        record.root,
        step="approval",
        level="info",
        message="Chờ người vận hành phê duyệt",
    )
    return record


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

    cleaned, redactions = redact(verdict.sanitized_text)
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

    metrics = collect_metrics(record)
    _write_json_artifact(record.root / "metrics.json", metrics)

    if not record.state.is_terminal():
        record.state = RunState.DONE

    report_path = record.root / "report.json"
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            data = None
        if isinstance(data, dict):
            data["state"] = record.state.value
            _write_json_artifact(report_path, data)

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
