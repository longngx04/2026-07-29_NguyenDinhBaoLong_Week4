"""Runner nối chín bước, dừng đúng chỗ, và không làm thất lạc lỗi."""

import json
import sys
from pathlib import Path

import pytest

from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_log import read_log
from project_sentinel.orchestrator.runner import resume_run, start_run
from project_sentinel.orchestrator.state import RunState, load_run, new_run, save_run


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(
        runs_dir=tmp_path / "runs",
        gateway_api_key="khoa-thu-nghiem",
        scan_command=[sys.executable, "-c", "import sys; sys.exit(9)"],
    )


def test_failing_first_step_marks_the_run_failed(ctx):
    record = start_run(ctx)
    assert record.state is RunState.FAILED
    assert record.error
    assert record.step("scan").status == "failed"


def test_failure_is_persisted_to_disk(ctx):
    record = start_run(ctx)
    reloaded = load_run(ctx.runs_dir, record.run_id)
    assert reloaded.state is RunState.FAILED
    assert reloaded.error == record.error


def test_failure_is_redacted_before_state_and_log_are_written(ctx):
    canary = "a" * 40
    leaking_ctx = ctx.replace(
        scan_command=[
            sys.executable,
            "-c",
            f"import sys; sys.stderr.write('api_key={canary}'); sys.exit(9)",
        ]
    )

    record = start_run(leaking_ctx)

    assert canary not in (record.root / "state.json").read_text(encoding="utf-8")
    assert canary not in (record.root / "run.log.jsonl").read_text(encoding="utf-8")


def test_failure_does_not_raise_out_of_the_runner(ctx):
    """Web gọi runner nền; ngoại lệ thoát ra sẽ làm mất trạng thái lần chạy."""
    record = start_run(ctx)
    assert record is not None


def test_unexpected_step_error_is_also_persisted_as_failed(ctx):
    invalid_ctx = ctx.replace(scan_command=None)

    record = start_run(invalid_ctx)

    assert record.state is RunState.FAILED
    assert "Lỗi ngoài dự kiến ở bước scan" in record.error


def test_unexpected_error_message_names_the_exception_type(ctx):
    """Đây là thông tin duy nhất còn lại sau khi runner nuốt ngoại lệ."""
    key_error_iterator = iter(lambda: {}["foo"], None)
    invalid_ctx = ctx.replace(scan_command=key_error_iterator)

    record = start_run(invalid_ctx)

    assert "KeyError" in record.error


def test_later_steps_are_not_run_after_a_failure(ctx):
    record = start_run(ctx)
    for name in ("normalize", "analyze", "propose"):
        assert record.step(name).status == "pending"


def test_resume_on_unknown_run_id_raises(ctx):
    with pytest.raises(FileNotFoundError):
        resume_run(ctx, "20200101T000000Z")


def test_resume_rejects_a_run_id_that_escapes_the_runs_directory(ctx):
    outside = new_run(ctx.runs_dir.parent)
    save_run(outside)

    with pytest.raises(FileNotFoundError):
        resume_run(ctx, f"../{outside.run_id}")


def test_resume_without_a_decision_stays_awaiting_approval(ctx):
    record = new_run(ctx.runs_dir)
    record.state = RunState.AWAITING_APPROVAL
    record.mark_step("approval", "running")
    save_run(record)

    resumed = resume_run(ctx, record.run_id)

    assert resumed.state is RunState.AWAITING_APPROVAL
    assert resumed.step("probe").status == "pending"


def test_resume_does_not_run_a_terminal_record_again(ctx):
    record = new_run(ctx.runs_dir)
    record.state = RunState.DONE
    save_run(record)

    resumed = resume_run(ctx, record.run_id)

    assert resumed.state is RunState.DONE
    assert resumed.step("probe").status == "pending"


def test_resume_explains_itself_when_it_does_nothing(ctx):
    """Người vận hành phải biết vì sao không có gì xảy ra."""
    for state, needs_decision in [
        (RunState.AWAITING_APPROVAL, False),
        (RunState.DONE, True),
        (RunState.SCANNING, True),
    ]:
        record = new_run(ctx.runs_dir)
        record.state = state
        save_run(record)
        if needs_decision:
            (record.root / "decision.json").write_text("{}", encoding="utf-8")

        before = len(read_log(record.root))
        resume_run(ctx, record.run_id)
        after = read_log(record.root)

        assert len(after) > before, f"{state.value}: không có dòng log nào"
        assert "Bỏ qua resume" in after[-1]["message"], after[-1]


def test_resume_after_rejection_ends_in_rejected(ctx):
    """Từ chối probe vẫn phải dựng report/metrics nhưng giữ trạng thái REJECTED."""
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
            approved=False,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
        ),
    )

    resumed = resume_run(ctx, record.run_id)
    assert resumed.state is RunState.REJECTED
    assert (resumed.root / "report.md").exists()
    assert (resumed.root / "metrics.json").exists()
    report = json.loads((resumed.root / "report.json").read_text(encoding="utf-8"))
    assert report["state"] == "REJECTED"


def test_state_json_is_saved_after_every_step(ctx):
    record = start_run(ctx)
    assert (record.root / "state.json").exists()
    data = json.loads((record.root / "state.json").read_text(encoding="utf-8"))
    assert data["state"] == "FAILED"


def test_step_is_marked_running_on_disk_before_execution(ctx):
    """Khi bước chạy lâu, state.json trên đĩa phải mang status='running' ngay lúc đang chạy."""
    observed_status = None

    def slow_step(record, context):
        nonlocal observed_status
        on_disk = load_run(context.runs_dir, record.run_id)
        observed_status = on_disk.step("scan").status
        record.mark_step("scan", "done")
        return record

    custom_phase = (("scan", slow_step),)
    record = new_run(ctx.runs_dir)
    save_run(record)

    from project_sentinel.orchestrator.runner import _execute

    _execute(record, ctx, custom_phase)

    assert observed_status == "running"
