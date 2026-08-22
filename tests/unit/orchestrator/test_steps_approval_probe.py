"""Bước 5 và 6 — cổng phê duyệt rồi gửi request."""

import json
from pathlib import Path

import pytest

from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.guardrails.events import read_events
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run
from project_sentinel.orchestrator.steps import step_approval, step_probe
from project_sentinel.probe.http_models import HttpResponse


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(
        runs_dir=tmp_path / "runs", gateway_api_key="khoa-thu-nghiem"
    )


def _proposal(
    record, *, method="POST", path="/WebGoat/attack", kind="long_string", accepted=True
):
    payload = {
        "accepted": accepted,
        "reason": "test",
        "probe": (
            {"method": method, "path": path, "payload_kind": kind}
            if accepted
            else None
        ),
        "source_analysis_id": "analysis-aaaa",
        "objective": {
            "description": "kiem tra",
            "endpoint_hint": f"{method} {path}",
            "payload_kind": kind,
            "rationale": "r",
        },
    }
    (record.root / "proposal.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_decision_from_approval_request(record, *, approved):
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=approved,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
            request_fingerprint=request["request_fingerprint"],
        ),
    )


class ExplodingTransport:
    def send_request(self, request):
        raise AssertionError("Không request nào được phép rời khỏi hệ thống ở ca này")


class CountingTransport:
    def __init__(self):
        self.calls = 0

    def send_request(self, request):
        self.calls += 1
        return HttpResponse(
            status_code=200,
            headers={},
            body="xin chao",
            response_bytes_observed=8,
            truncated=False,
            elapsed_ms=3.0,
        )


def test_risky_probe_pauses_for_approval(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record)
    record = step_approval(record, ctx)

    assert record.state is RunState.AWAITING_APPROVAL
    assert record.step("approval").status == "running"

    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    assert request["endpoint"] == "/WebGoat/attack"
    assert request["method"] == "POST"
    assert request["payload"]
    assert request["purpose"]
    assert request["risk_reason"]
    assert request["request_fingerprint"]


def test_plain_get_skips_approval(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(
        record, method="GET", path="/WebGoat/actuator/health", kind=None
    )
    record = step_approval(record, ctx)

    assert record.state is not RunState.AWAITING_APPROVAL
    assert record.step("approval").status == "skipped"


def test_rejected_proposal_skips_straight_past_approval(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record, accepted=False)
    record = step_approval(record, ctx)
    assert record.step("approval").status == "skipped"


def test_probe_without_a_decision_sends_nothing(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record)
    record = step_approval(record, ctx)
    record = step_probe(record, ctx, transport=ExplodingTransport())

    result = json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )
    assert result["sent"] is False


def test_rejected_decision_marks_the_run_rejected(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record)
    record = step_approval(record, ctx)
    _write_decision_from_approval_request(record, approved=False)

    record = step_probe(record, ctx, transport=ExplodingTransport())
    assert record.state is RunState.REJECTED

    result = json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )
    assert result["sent"] is False


def test_rejection_writes_an_approval_event(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record)
    record = step_approval(record, ctx)
    _write_decision_from_approval_request(record, approved=False)
    record = step_probe(record, ctx, transport=ExplodingTransport())

    approvals = [
        event
        for event in read_events(record.root / "events.jsonl")
        if event["kind"] == "approval"
    ]
    assert approvals
    assert approvals[-1]["detail"]["approved"] is False


def test_approved_decision_sends_exactly_one_request(ctx):
    record = new_run(ctx.runs_dir)
    _proposal(record)
    record = step_approval(record, ctx)
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=True,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
            request_fingerprint=request["request_fingerprint"],
        ),
    )

    transport = CountingTransport()
    record = step_probe(record, ctx, transport=transport)

    assert transport.calls == 1
    result = json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )
    assert result["sent"] is True
    assert result["status_code"] == 200
    assert record.state is RunState.PROBING


def test_decision_from_a_different_request_sends_nothing(ctx):
    """Duyệt một probe rồi đổi probe — cổng phải chặn, không request nào đi ra.

    Cả `long_string` lẫn `empty_value` đều là payload ĐÃ ĐƯỢC DUYỆT cho endpoint
    này. Dùng một payload chưa duyệt sẽ bị chặn sớm hơn vì lý do khác, và test sẽ
    xanh mà không còn kiểm được ràng buộc dấu vân tay.
    """
    record = new_run(ctx.runs_dir)
    _proposal(record, kind="long_string")
    record = step_approval(record, ctx)
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )

    _proposal(record, kind="empty_value")
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=True,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
            request_fingerprint=request["request_fingerprint"],
        ),
    )

    transport = CountingTransport()
    record = step_probe(record, ctx, transport=transport)

    result = json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )
    assert result["sent"] is False
    assert transport.calls == 0
    request_log = (record.root / "gateway-requests.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"policy_decision": "DENIED"' in request_log


def test_fingerprint_mismatch_leaves_a_trace_in_the_event_log(ctx):
    """Chốt chặn được thì sổ sự kiện phải nói rõ request đã bị từ chối."""
    record = new_run(ctx.runs_dir)
    _proposal(record, kind="long_string")
    record = step_approval(record, ctx)
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=True,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="op",
            request_fingerprint=request["request_fingerprint"],
        ),
    )

    _proposal(record, kind="empty_value")
    transport = CountingTransport()
    step_probe(record, ctx, transport=transport)

    assert transport.calls == 0
    events = [
        (event["kind"], event["detail"])
        for event in read_events(record.root / "events.jsonl")
    ]
    assert any(
        kind == "approval" and detail.get("approved") is False
        for kind, detail in events
    )


def test_proposal_with_null_objective_does_not_crash(ctx):
    """proposal.json là file trên đĩa — Plan 4 có thể sửa nó."""
    record = new_run(ctx.runs_dir)
    _proposal(record)
    proposal_path = record.root / "proposal.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["objective"] = None
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    record = step_approval(record, ctx)

    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    assert request["purpose"] == "Kiểm chứng finding"
    assert record.state is RunState.AWAITING_APPROVAL


def test_all_events_in_run_record_the_actual_run_id(ctx):
    """Sau khi chạy probe, mọi dòng events.jsonl phải có run_id == record.run_id."""
    record = new_run(ctx.runs_dir)
    _proposal(record, kind="empty_value")
    record = step_approval(record, ctx)
    _write_decision_from_approval_request(record, approved=True)

    transport = CountingTransport()
    record = step_probe(record, ctx, transport=transport)

    events = read_events(record.root / "events.jsonl")
    assert len(events) > 0
    for event in events:
        assert event["run_id"] == record.run_id
        assert "request_id" in event["detail"]

