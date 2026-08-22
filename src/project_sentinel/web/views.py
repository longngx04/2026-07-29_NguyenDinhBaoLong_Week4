"""Đọc artifact của các lần chạy và dựng dữ liệu cho template.

Module này CHỈ ĐỌC. Không thay đổi trạng thái, không gọi mạng, không chạy bước
nào. Mọi thay đổi đều thuộc về orchestrator.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from project_sentinel.guardrails.events import read_events
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.metrics import collect_metrics
from project_sentinel.orchestrator.run_log import read_log
from project_sentinel.orchestrator.state import RunRecord, list_runs, load_run

MAX_RUNS_ON_OVERVIEW = 20


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(default, dict) and not isinstance(data, dict):
            return default
        if isinstance(default, list) and not isinstance(data, list):
            return default
        return data
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    results = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    results.append(parsed)
            except Exception:
                continue
    except Exception:
        return []
    return results


def overview_data(ctx: RunContext) -> dict:
    """Số liệu tổng hợp và danh sách các lần chạy gần đây."""
    rows = []
    totals = {"runs": 0, "findings": 0, "requests": 0, "approved": 0, "rejected": 0, "errors": 0}

    for run_id in list_runs(ctx.runs_dir)[:MAX_RUNS_ON_OVERVIEW]:
        try:
            record = load_run(ctx.runs_dir, run_id)
            metrics = collect_metrics(record)
        except Exception:
            continue
        rows.append({
            "run_id": run_id,
            "state": record.state.value,
            "created_at": record.created_at,
            "findings": metrics["findings_total"],
            "requests": metrics["requests_total"],
            "elapsed_ms": metrics["total_elapsed_ms"],
        })
        totals["runs"] += 1
        totals["findings"] += metrics["findings_total"]
        totals["requests"] += metrics["requests_total"]
        totals["approved"] += metrics["approvals"]["approved"]
    has_active = any(
        row["state"] not in {"DONE", "FAILED", "REJECTED"}
        for row in rows
    )

    return {
        "runs": rows,
        "totals": totals,
        "demo_run": os.getenv("SENTINEL_DEMO_RUN") or None,
        "has_active": has_active,
    }



def _strength_distribution(findings: list) -> dict[str, int]:
    """Đếm `runtime_evidence.strength`, CHỈ trên finding tĩnh.

    Finding động đã LÀ bằng chứng runtime nên `correlate` cố ý không gắn khối
    này cho chúng; đếm cả hai sẽ trộn hai thứ khác nghĩa vào một biểu đồ.

    Trả dict rỗng khi lần chạy không có DAST. Hiện một khối toàn số 0 làm
    người đọc tưởng đã quét mà không tìm ra gì.
    """
    counts: dict[str, int] = {}
    for item in findings:
        if not isinstance(item, dict) or item.get("tool") == "zap":
            continue
        strength = (item.get("runtime_evidence") or {}).get("strength")
        if strength:
            counts[str(strength)] = counts.get(str(strength), 0) + 1
    return counts


def _load_findings(record) -> list:
    raw = _read_json(record.root / "findings.json", {})
    findings = raw.get("findings", []) if isinstance(raw, dict) else []
    return findings if isinstance(findings, list) else []


def run_data(ctx: RunContext, run_id: str) -> dict:
    """Tiến trình chín bước của một lần chạy."""
    record = load_run(ctx.runs_dir, run_id)
    return {
        "run": record,
        "steps": [
            {
                "index": step.index,
                "name": step.name,
                "status": step.status,
                "elapsed_ms": step.elapsed_ms,
                "detail": step.detail,
            }
            for step in record.steps
        ],
        "metrics": collect_metrics(record),
        # `completeness: PARTIAL` nghĩa là vài nhóm biến mất khỏi báo cáo.
        # report.md nói điều đó ngay dòng đầu; màn hình này trước đây im lặng.
        "analysis_summary": _read_json(record.root / "analysis-summary.json", {}),
        "strengths": _strength_distribution(_load_findings(record)),
        "log": read_log(record.root)[-50:],
    }


def findings_data(ctx: RunContext, run_id: str) -> dict:
    record = load_run(ctx.runs_dir, run_id)
    findings = _load_findings(record)
    severities: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    for item in findings:
        if not isinstance(item, dict):
            continue
        key = str(item.get("severity", "unknown"))
        severities[key] = severities.get(key, 0) + 1
        tool = str(item.get("tool") or "unknown")
        by_tool[tool] = by_tool.get(tool, 0) + 1
    return {
        "run": record,
        "findings": findings,
        "severities": severities,
        # Một finding ZAP gộp theo loại alert, một finding OpenGrep là một vị
        # trí trong mã. Gộp chúng vào một con số là trộn hai loại hạt.
        "by_tool": by_tool,
        "strengths": _strength_distribution(findings),
    }


def analysis_data(ctx: RunContext, run_id: str) -> dict:
    record = load_run(ctx.runs_dir, run_id)
    return {
        "run": record,
        "records": _read_jsonl(record.root / "analysis.jsonl"),
        "proposal": _read_json(record.root / "proposal.json", {}),
    }


def events_data(ctx: RunContext, run_id: str) -> dict:
    record = load_run(ctx.runs_dir, run_id)
    return {
        "run": record,
        "events": read_events(record.root / "events.jsonl"),
        "scrubbed": _read_json(record.root / "scrubbed.json", {}),
        "proposal": _read_json(record.root / "proposal.json", {}),
    }


def requests_data(ctx: RunContext, run_id: str) -> dict:
    record = load_run(ctx.runs_dir, run_id)
    return {
        "run": record,
        "requests": _read_jsonl(record.root / "gateway-requests.jsonl"),
        "probe_result": _read_json(record.root / "probe-result.json", {}),
    }


def approvals_data(ctx: RunContext) -> dict:
    """Các lần chạy đang chờ người duyệt."""
    pending = []
    for run_id in list_runs(ctx.runs_dir):
        try:
            record = load_run(ctx.runs_dir, run_id)
        except Exception:
            continue
        if record.state.value != "AWAITING_APPROVAL":
            continue
        request = _read_json(record.root / "approval-request.json", None)
        if isinstance(request, dict):
            pending.append({"run_id": run_id, "request": request})
    return {"pending": pending}


def run_status(ctx: RunContext, run_id: str) -> dict:
    """Dữ liệu thời gian thực phục vụ polling / live updates."""
    record: RunRecord = load_run(ctx.runs_dir, run_id)
    logs = read_log(record.root)[-100:]
    log_text = "\n".join(
        f"[{entry.get('level', 'info').upper()}] {entry.get('step', 'system')}: {entry.get('message', '')}"
        for entry in logs
    )
    metrics = collect_metrics(record)
    return {
        "run_id": record.run_id,
        "state": record.state.value,
        "error": record.error,
        "terminal": record.state.is_terminal(),
        "awaiting_approval": record.state.value == "AWAITING_APPROVAL",
        "steps": [
            {"index": s.index, "name": s.name, "status": s.status, "elapsed_ms": s.elapsed_ms}
            for s in record.steps
        ],
        "log": log_text,
        "metrics": {
            "findings_total": metrics["findings_total"],
            "requests_total": metrics["requests_total"],
            "approvals_approved": metrics["approvals"]["approved"],
            "approvals_rejected": metrics["approvals"]["rejected"],
            "total_elapsed_ms": metrics["total_elapsed_ms"],
        },
    }
