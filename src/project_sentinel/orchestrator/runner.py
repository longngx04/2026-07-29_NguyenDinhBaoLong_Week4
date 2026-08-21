"""Nối chín bước thành một luồng và lưu trạng thái sau mỗi bước.

Lỗi của một bước không thoát khỏi runner: lỗi được ghi vào ``state.json`` để
CLI và tiến trình nền của web cùng nhìn thấy một kết quả bền trên đĩa.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from project_sentinel.guardrails.redaction import redact
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_lock import (
    idempotency_key,
    read_claim,
    run_lock,
    write_claim,
)
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import (
    RunRecord,
    RunState,
    confined_run_root,
    load_run,
    new_run,
    save_run,
)
from project_sentinel.orchestrator.steps import (
    StepFailure,
    step_analyze,
    step_approval,
    step_finalize,
    step_normalize,
    step_probe,
    step_propose,
    step_report,
    step_scan,
    step_scrub,
)

StepFunction = Callable[[RunRecord, RunContext], RunRecord]
Phase = tuple[tuple[str, StepFunction], ...]
RUN_ID_PATTERN = re.compile(r"\A\d{8}T\d{6}(?:-\d+)?Z\Z")

PHASE_ONE: Phase = (
    ("scan", step_scan),
    ("normalize", step_normalize),
    ("analyze", step_analyze),
    ("propose", step_propose),
    ("approval", step_approval),
)

PHASE_TWO: Phase = (
    ("probe", step_probe),
    ("scrub", step_scrub),
    ("report", step_report),
    ("finalize", step_finalize),
)


def _record_failure(record: RunRecord, name: str, message: str) -> RunRecord:
    safe_message, _ = redact(message)
    record.mark_step(name, "failed", detail={"error": safe_message})
    record.state = RunState.FAILED
    record.error = safe_message
    append_log(record.root, step=name, level="error", message=safe_message)
    save_run(record)
    return record


def _execute(record: RunRecord, ctx: RunContext, phase: Phase) -> RunRecord:
    for name, function in phase:
        terminal_state = record.state if record.state.is_terminal() else None
        try:
            record = function(record, ctx)
        except StepFailure as exc:
            return _record_failure(record, name, str(exc))
        except Exception as exc:
            return _record_failure(
                record,
                name,
                f"Lỗi ngoài dự kiến ở bước {name}: {type(exc).__name__}: {exc}",
            )

        if terminal_state is not None:
            record.state = terminal_state
        save_run(record)
        if record.state is RunState.AWAITING_APPROVAL:
            return record

    return record


def start_run(ctx: RunContext) -> RunRecord:
    """Tạo run, chạy phase một, rồi dừng duyệt hoặc chạy tiếp phase hai."""
    record = new_run(ctx.runs_dir)
    save_run(record)
    append_log(record.root, step="scan", level="info", message="Khởi động lần chạy")

    record = _execute(record, ctx, PHASE_ONE)
    if record.state in (RunState.FAILED, RunState.AWAITING_APPROVAL):
        return record

    record = _execute(record, ctx, PHASE_TWO)
    save_run(record)
    return record


def resume_run(ctx: RunContext, run_id: str) -> RunRecord:
    """Nạp run từ đĩa và chạy phase hai sau quyết định của người vận hành.

    Toàn bộ "nạp → kiểm → chiếm" nằm trong MỘT khoá liên tiến trình. Không có
    khoá thì hai lệnh resume đồng thời cùng đọc `AWAITING_APPROVAL` và cùng gửi
    probe; đó là điều mentor đã ép chạy được hai lần.
    """
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise FileNotFoundError(f"Không tìm thấy lần chạy {run_id}")

    root = confined_run_root(ctx.runs_dir, run_id)
    if not (root / "state.json").exists():
        raise FileNotFoundError(f"Không tìm thấy lần chạy {run_id}")

    with run_lock(root) as acquired:
        if not acquired:
            # Một tiến trình khác đang chạy phase hai cho đúng lần chạy này.
            append_log(
                root,
                step="approval",
                level="warn",
                message=(
                    "Bỏ qua resume: một tiến trình khác đang giữ khoá của lần "
                    "chạy này"
                ),
            )
            return load_run(ctx.runs_dir, run_id)

        # Nạp LẠI dưới khoá. State đọc trước khi vào khoá có thể đã cũ.
        record = load_run(ctx.runs_dir, run_id)
        skip = _resume_refusal(record)
        if skip is not None:
            step, message, level = skip
            append_log(record.root, step=step, level=level, message=message)
            return record

        key = idempotency_key(run_id, record.root)
        claim = read_claim(record.root)
        if claim is not None and claim.get("idempotency_key") == key:
            # Khoá flock đã nhả khi tiến trình trước kết thúc, nhưng lượt kiểm
            # chứng đó đã được chiếm rồi. Không gửi lại probe lần thứ hai.
            append_log(
                record.root,
                step="probe",
                level="warn",
                message=(
                    "Bỏ qua resume: lượt kiểm chứng này đã được chiếm "
                    f"({key}) lúc {claim.get('claimed_at')}"
                ),
            )
            return record

        # Chiếm TRƯỚC mọi network I/O, và ghi cả hai dấu vết xuống đĩa trước khi
        # nhả khoá: trạng thái không còn là AWAITING_APPROVAL, và khoá chiếm mang
        # đúng idempotency key của quyết định này.
        write_claim(record.root, key)
        record.state = RunState.PROBING
        save_run(record)
        append_log(
            record.root,
            step="probe",
            level="info",
            message=f"Chiếm lượt kiểm chứng {key}",
        )

        record = _execute(record, ctx, PHASE_TWO)
        save_run(record)
        return record


def _resume_refusal(record: RunRecord) -> tuple[str, str, str] | None:
    """Lý do KHÔNG chạy phase hai, hoặc None nếu được phép chạy."""
    if record.state.is_terminal():
        return (
            "finalize",
            "Bỏ qua resume: lần chạy đã kết thúc ở trạng thái "
            f"{record.state.value}",
            "info",
        )
    if record.state is not RunState.AWAITING_APPROVAL:
        return (
            "approval",
            f"Bỏ qua resume: lần chạy đang ở trạng thái {record.state.value}, "
            "không phải AWAITING_APPROVAL",
            "warn",
        )
    if not (record.root / "decision.json").exists():
        return (
            "approval",
            "Bỏ qua resume: chưa có decision.json — người vận hành chưa quyết định",
            "info",
        )
    return None
