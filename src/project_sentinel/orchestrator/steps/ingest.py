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

    # DAST chay SAU SAST va khong bao gio keo buoc nay fail. SAST la xuong song

    # cua pipeline; mot may khong co Docker van phai chay duoc run.
    dast_status = "skipped"
    dast_reason: str | None = None
    if not ctx.dast_command:
        dast_reason = "Khong cau hinh lenh DAST"
    else:
        alerts = record.root / "zap-alerts.json"
        access_log = record.root / "gateway-access.log"
        try:
            _run_command(
                [*ctx.dast_command, str(alerts), str(access_log)],
                cwd=ctx.repo_root,
                step="scan",
                root=record.root,
            )
        except StepFailure as exc:
            dast_reason = str(exc)
        else:
            if alerts.exists() and access_log.exists():
                dast_status = "done"
            else:
                dast_reason = "Lenh DAST khong sinh du hai artifact"

    if dast_status == "done":
        append_log(record.root, step="scan", level="info", message="DAST xong")
    else:
        append_log(
            record.root,
            step="scan",
            level="warn",
            message=f"Bo qua DAST: {dast_reason}",
        )

    detail = {"raw_results": count, "used_fallback": used_fallback, "dast": dast_status}
    if dast_reason:
        detail["dast_reason"] = dast_reason
    record.mark_step("scan", "done", detail=detail)
    append_log(
        record.root,
        step="scan",
        level="info",
        message="Quét xong",
        raw_results=count,
        used_fallback=used_fallback,
    )
    return record


def _normalise_finding_fields(findings: list[dict]) -> None:
    """Ep cwe/owasp ve list cho moi finding, sua tai cho.

    zap_normalizer cho list, normalizer.py cua OpenGrep cho gia tri vo huong.
    De ca hai hinh dang vao findings.json thi moi thu doc no ve sau — prompt,
    validator, report — deu phai xu ly hai truong hop.
    """
    for item in findings:
        for field in ("cwe", "owasp"):
            value = item.get(field)
            if value is None or value == "":
                item[field] = []
            elif not isinstance(value, list):
                item[field] = [str(value)]


def step_normalize(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 2 — chuẩn hoá về định dạng chung, ghi findings.json."""
    from project_sentinel.analysis.correlation import (
        correlate,
        parse_gateway_access_log,
    )
    from project_sentinel.ingestion.merge_findings import merge_files
    from project_sentinel.ingestion.zap_normalizer import run_normalize

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

    zap_added = 0
    alerts_path = record.root / "zap-alerts.json"
    if alerts_path.exists():
        zap_normalized = record.root / "zap-findings.json"
        zap_added = len(run_normalize(alerts_path, zap_normalized))
        # Ghi ra file thu ba roi doi ten, KHONG merge_files([target, x], target):
        # doc va ghi cung mot duong dan chi dung duoc nho merge_files tinh co doc
        # het truoc khi ghi. Dua vao mot chi tiet noi tai nhu vay la mong manh.
        combined = record.root / ".findings.merged.json"
        merge_files([target, zap_normalized], combined)
        combined.replace(target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        # Hai normalizer dung hai hinh dang cho cung mot truong: zap_normalizer
        # cho cwe/owasp la list, normalizer.py cua OpenGrep cho gia tri vo huong.
        # Chuan hoa ve list ngay sau khi tron, vi list la dang tong quat hon va
        # moi thu doc findings.json sau day chi con mot hinh dang de xu ly.
        _normalise_finding_fields(payload["findings"])
        payload["findings"] = correlate(
            payload["findings"],
            parse_gateway_access_log(record.root / "gateway-access.log"),
            project_root=ctx.repo_root,
        )
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        findings = payload["findings"]

    correlated = sum(
        1
        for f in findings
        if (f.get("runtime_evidence") or {}).get("strength", "no_route") != "no_route"
    )
    record.mark_step(
        "normalize",
        "done",
        detail={
            "findings": len(findings),
            "zap_findings": zap_added,
            "correlated": correlated,
        },
    )
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
