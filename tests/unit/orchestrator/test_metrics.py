"""Đúng năm số liệu đề bài liệt kê ở tuần 6."""

import json

import pytest

from project_sentinel.guardrails.events import append_event
from project_sentinel.orchestrator.metrics import collect_metrics
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import new_run


@pytest.fixture
def record(tmp_path):
    return new_run(tmp_path)


def test_all_five_metric_groups_are_present(record):
    metrics = collect_metrics(record)
    for key in (
        "total_elapsed_ms",
        "step_elapsed_ms",
        "requests_total",
        "findings_total",
        "approvals",
        "errors",
    ):
        assert key in metrics, f"Thiếu số liệu {key}"


def test_step_and_total_elapsed_are_summed(record):
    record.mark_step("scan", "running")
    record.mark_step("scan", "done")
    record.mark_step("normalize", "running")
    record.mark_step("normalize", "done")

    metrics = collect_metrics(record)
    assert metrics["step_elapsed_ms"]["scan"] >= 0.0
    assert metrics["total_elapsed_ms"] == pytest.approx(
        sum(metrics["step_elapsed_ms"].values()), rel=1e-6
    )


def test_requests_total_counts_sent_gateway_log_lines(record):
    (record.root / "gateway-requests.jsonl").write_text(
        '{"status": "SENT", "method": "GET", "path": "/a"}\n'
        '{"status": "SENT", "method": "GET", "path": "/b"}\n',
        encoding="utf-8",
    )
    assert collect_metrics(record)["requests_total"] == 2


def test_requests_total_counts_only_requests_that_were_sent(tmp_path):
    """Request bị guardrail chặn không bao giờ rời khỏi máy — không được đếm."""
    record = new_run(tmp_path)
    (record.root / "gateway-requests.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {"status": "DENIED", "policy_decision": "DENIED"}
                ),
                json.dumps(
                    {"status": "DENIED", "policy_decision": "DENIED"}
                ),
                json.dumps({"status": "SENT", "status_code": 200}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = collect_metrics(record)
    assert metrics["requests_total"] == 1
    assert metrics["requests_denied"] == 2


def test_corrupt_gateway_log_line_is_ignored(tmp_path):
    record = new_run(tmp_path)
    (record.root / "gateway-requests.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"status": "SENT"}),
                "{ hong",
                json.dumps({"status": "DENIED"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = collect_metrics(record)
    assert metrics["requests_total"] == 1
    assert metrics["requests_denied"] == 1


def test_requests_total_is_zero_without_a_gateway_log(record):
    assert collect_metrics(record)["requests_total"] == 0


def test_findings_total_comes_from_findings_json(record):
    (record.root / "findings.json").write_text(
        json.dumps({"findings": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}),
        encoding="utf-8",
    )
    assert collect_metrics(record)["findings_total"] == 3


def test_approve_and_reject_counts_come_from_events(record):
    events_path = record.root / "events.jsonl"
    append_event(
        events_path,
        run_id=record.run_id,
        kind="approval",
        detail={"approved": True},
    )
    append_event(
        events_path,
        run_id=record.run_id,
        kind="approval",
        detail={"approved": False},
    )
    append_event(
        events_path,
        run_id=record.run_id,
        kind="approval",
        detail={"approved": False},
    )

    approvals = collect_metrics(record)["approvals"]
    assert approvals == {"approved": 1, "rejected": 2, "decided_by": []}


def test_approval_metrics_name_the_automatic_approver(record):
    append_event(
        record.root / "events.jsonl",
        run_id=record.run_id,
        kind="approval",
        detail={"approved": True, "decided_by": "cli-auto"},
    )

    approvals = collect_metrics(record)["approvals"]
    assert approvals["decided_by"] == ["cli-auto"]


def test_approval_with_null_detail_is_counted_as_rejected(tmp_path):
    record = new_run(tmp_path)
    (record.root / "events.jsonl").write_text(
        json.dumps({"kind": "approval", "detail": None}) + "\n",
        encoding="utf-8",
    )

    approvals = collect_metrics(record)["approvals"]
    assert approvals == {"approved": 0, "rejected": 1, "decided_by": []}


def test_llm_metrics_come_from_analysis_summary(record):
    (record.root / "analysis-summary.json").write_text(
        json.dumps({"llm_call_count": 22, "invalid_output_count": 1}),
        encoding="utf-8",
    )

    assert collect_metrics(record)["llm"] == {
        "calls": 22,
        "invalid_outputs": 1,
    }


def test_llm_metrics_are_zero_without_an_analysis_summary(record):
    assert collect_metrics(record)["llm"] == {"calls": 0, "invalid_outputs": 0}


def test_corrupt_analysis_summary_does_not_break_metrics(record):
    (record.root / "analysis-summary.json").write_text(
        "{ hong", encoding="utf-8"
    )

    assert collect_metrics(record)["llm"] == {"calls": 0, "invalid_outputs": 0}


def test_llm_and_app_errors_are_counted_separately(record):
    append_log(record.root, step="analyze", level="error", message="LLM timeout")
    append_log(
        record.root, step="probe", level="error", message="Gateway unreachable"
    )
    append_log(record.root, step="scan", level="info", message="binh thuong")

    errors = collect_metrics(record)["errors"]
    assert errors["llm"] == 1
    assert errors["app"] == 1
    assert errors["total"] == 2


def test_errors_total_counts_every_error_line(tmp_path):
    """total phải là TỔNG, kể cả bước không thuộc nhóm llm/app."""
    record = new_run(tmp_path)
    for step in ["analyze", "probe", "report", "propose", "finalize"]:
        append_log(
            record.root,
            step=step,
            level="error",
            message=f"loi o {step}",
        )

    errors = collect_metrics(record)["errors"]
    assert errors["total"] == 5
    assert errors["llm"] == 1
    assert errors["app"] == 1
    assert errors["other"] == 3


def test_metrics_on_a_fresh_run_are_all_zero(record):
    metrics = collect_metrics(record)
    assert metrics["total_elapsed_ms"] == 0.0
    assert metrics["requests_total"] == 0
    assert metrics["requests_denied"] == 0
    assert metrics["findings_total"] == 0
    assert metrics["approvals"] == {
        "approved": 0,
        "rejected": 0,
        "decided_by": [],
    }
    assert metrics["llm"] == {"calls": 0, "invalid_outputs": 0}
    assert metrics["errors"]["other"] == 0
    assert metrics["errors"]["total"] == 0
