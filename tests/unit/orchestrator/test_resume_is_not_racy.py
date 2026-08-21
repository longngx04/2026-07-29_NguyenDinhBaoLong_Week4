"""Hai lệnh resume đồng thời chỉ được gửi ĐÚNG MỘT request kiểm chứng.

Trước khi sửa, `resume_run` là ba bước rời nhau: nạp state → kiểm
`AWAITING_APPROVAL` → chạy phase hai. Ép hai luồng cùng nạp state trước khi bất
kỳ luồng nào kịp ghi lại trạng thái thì cả hai đều thấy `AWAITING_APPROVAL` và
cả hai đều probe::

    concurrent_resume_probe_calls=2

UI làm chuyện này thành thường ngày chứ không còn là hiếm gặp: double-click,
retry của trình duyệt, hai tab, hoặc hai worker cùng phục vụ một nút Resume.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.orchestrator import runner as runner_module
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_lock import CLAIM_NAME, idempotency_key
from project_sentinel.orchestrator.runner import resume_run
from project_sentinel.orchestrator.state import (
    RunRecord,
    RunState,
    load_run,
    new_run,
    save_run,
)
from project_sentinel.orchestrator.steps import probe as probe_step
from project_sentinel.probe.tool import ProbeOutcome


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(
        runs_dir=tmp_path / "runs",
        gateway_api_key="khoa-thu-nghiem",
        scan_command=[sys.executable, "-c", "import sys; sys.exit(9)"],
    )


def _run_awaiting_an_approved_probe(ctx) -> RunRecord:
    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "reason": "ok",
                "probe": {
                    "method": "POST",
                    "path": "/WebGoat/attack",
                    "payload_kind": "empty_value",
                },
                "source_analysis_id": "analysis-a",
                "objective": None,
            }
        ),
        encoding="utf-8",
    )
    record.state = RunState.AWAITING_APPROVAL
    record.mark_step("approval", "running")
    save_run(record)
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=True,
            decided_at="2026-08-21T10:00:00Z",
            decided_by="test",
            request_fingerprint="khong-khop-nhung-send_probe-da-bi-thay",
        ),
    )
    return record


class _CountingProbe:
    """Đếm số lần *thật sự* gọi tới transport, và giữ cửa sổ đua mở đủ lâu."""

    def __init__(self, hold_seconds: float = 0.25):
        self.calls = 0
        self._hold = hold_seconds
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs) -> ProbeOutcome:
        with self._lock:
            self.calls += 1
        time.sleep(self._hold)
        return ProbeOutcome(sent=False, denied_reason="transport bị thay trong test")


def _resume_twice_at_once(ctx, run_id: str) -> None:
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            resume_run(ctx, run_id)
        except BaseException as exc:  # noqa: BLE001 — báo lại ở luồng chính
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors


def test_two_concurrent_resumes_probe_exactly_once(ctx, monkeypatch):
    record = _run_awaiting_an_approved_probe(ctx)
    counter = _CountingProbe()
    monkeypatch.setattr(probe_step, "send_probe", counter)

    _resume_twice_at_once(ctx, record.run_id)

    assert counter.calls == 1, (
        f"concurrent_resume_probe_calls={counter.calls} — khoá không giữ được "
        "toàn bộ giao dịch nạp → kiểm → chiếm"
    )


def test_the_loser_of_the_race_says_so_in_the_run_log(ctx, monkeypatch):
    """Người vận hành phải phân biệt được 'đã chạy' với 'bị bỏ qua im lặng'."""
    record = _run_awaiting_an_approved_probe(ctx)
    monkeypatch.setattr(probe_step, "send_probe", _CountingProbe())

    _resume_twice_at_once(ctx, record.run_id)

    log = (record.root / "run.log.jsonl").read_text(encoding="utf-8")
    assert "Bỏ qua resume" in log


def test_a_second_resume_after_the_first_finished_does_not_probe_again(ctx, monkeypatch):
    """Khoá flock nhả khi tiến trình chết; khoá chiếm trên đĩa thì không."""
    record = _run_awaiting_an_approved_probe(ctx)
    counter = _CountingProbe(hold_seconds=0.0)
    monkeypatch.setattr(probe_step, "send_probe", counter)

    resume_run(ctx, record.run_id)
    assert counter.calls == 1

    # Giả lập một tiến trình chết giữa chừng: state bị đặt lại về chờ duyệt,
    # nhưng khoá chiếm vẫn còn trên đĩa.
    reloaded = load_run(ctx.runs_dir, record.run_id)
    reloaded.state = RunState.AWAITING_APPROVAL
    save_run(reloaded)

    resume_run(ctx, record.run_id)

    assert counter.calls == 1


def test_the_claim_is_written_before_any_network_call(ctx, monkeypatch):
    record = _run_awaiting_an_approved_probe(ctx)
    seen: list[bool] = []

    def probe_checking_the_claim(*args, **kwargs) -> ProbeOutcome:
        seen.append((record.root / CLAIM_NAME).exists())
        return ProbeOutcome(sent=False, denied_reason="test")

    monkeypatch.setattr(probe_step, "send_probe", probe_checking_the_claim)

    resume_run(ctx, record.run_id)

    assert seen == [True]


def test_the_claim_key_is_bound_to_the_decision_not_just_the_run(ctx):
    """Một quyết định khác là một lượt kiểm chứng khác."""
    record = _run_awaiting_an_approved_probe(ctx)
    first = idempotency_key(record.run_id, record.root)

    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=False,
            decided_at="2026-08-21T11:00:00Z",
            decided_by="test",
        ),
    )
    second = idempotency_key(record.run_id, record.root)

    assert first != second
    assert first.startswith(f"{record.run_id}:")


def test_the_lock_lives_inside_the_run_directory(ctx, monkeypatch):
    """Khoá đi theo lần chạy, nên hai lần chạy khác nhau không chặn nhau."""
    monkeypatch.setattr(probe_step, "send_probe", _CountingProbe(hold_seconds=0.0))
    first = _run_awaiting_an_approved_probe(ctx)
    second = _run_awaiting_an_approved_probe(ctx)

    resume_run(ctx, first.run_id)
    resume_run(ctx, second.run_id)

    assert (first.root / CLAIM_NAME).exists()
    assert (second.root / CLAIM_NAME).exists()
    assert runner_module.resume_run is resume_run
