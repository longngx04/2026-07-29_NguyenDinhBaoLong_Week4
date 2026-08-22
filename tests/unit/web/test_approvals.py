"""Màn hình phê duyệt — nơi con người thật sự bấm nút."""

import json

import pytest
from fastapi.testclient import TestClient

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, load_run, new_run, save_run
from project_sentinel.web import main as web_main


@pytest.fixture
def client(tmp_path):
    ctx = RunContext.default().replace(
        runs_dir=tmp_path / "runs", gateway_api_key="khoa-thu-nghiem"
    )
    web_main.app.dependency_overrides[web_main.get_context] = lambda: ctx
    yield TestClient(web_main.app), ctx
    web_main.app.dependency_overrides.clear()


@pytest.fixture
def pending(client):
    _, ctx = client
    rec = new_run(ctx.runs_dir)
    (rec.root / "proposal.json").write_text(json.dumps({
        "accepted": True, "reason": "ok",
        "probe": {"method": "POST", "path": "/WebGoat/attack", "payload_kind": "long_string"},
        "source_analysis_id": "analysis-aaaa", "objective": None,
    }), encoding="utf-8")
    (rec.root / "approval-request.json").write_text(json.dumps({
        "run_id": rec.run_id, "method": "POST", "endpoint": "/WebGoat/attack",
        "payload": '{"value": "AAAA"}', "purpose": "Kiem tra gioi han do dai",
        "risk_reason": "Request POST co the thay doi trang thai",
    }), encoding="utf-8")
    rec.state = RunState.AWAITING_APPROVAL
    rec.mark_step("approval", "running")
    save_run(rec)
    return rec


def test_empty_queue_says_so(client):
    http, _ = client
    assert "Không có request nào chờ" in http.get("/approvals").text


def test_queue_shows_the_four_required_details(client, pending):
    """Đề bài đòi: endpoint, payload, mục đích, và hai lựa chọn."""
    http, _ = client
    body = http.get("/approvals").text
    assert "/WebGoat/attack" in body
    assert "AAAA" in body
    assert "Kiem tra gioi han do dai" in body
    assert "Approve" in body and "Reject" in body


def test_reject_marks_the_run_rejected(client, pending):
    http, ctx = client
    response = http.post(f"/approvals/{pending.run_id}", data={"decision": "reject"},
                         follow_redirects=False)
    assert response.status_code == 303

    record = load_run(ctx.runs_dir, pending.run_id)
    assert record.state is RunState.REJECTED


def test_reject_sends_no_request_at_all(client, pending):
    http, ctx = client
    http.post(f"/approvals/{pending.run_id}", data={"decision": "reject"},
              follow_redirects=False)

    gateway_log = pending.root / "gateway-requests.jsonl"
    if gateway_log.exists():
        assert '"status": "SENT"' not in gateway_log.read_text(encoding="utf-8")

    result = json.loads((pending.root / "probe-result.json").read_text(encoding="utf-8"))
    assert result["sent"] is False


def test_reject_writes_the_decision_file(client, pending):
    http, _ = client
    http.post(f"/approvals/{pending.run_id}", data={"decision": "reject"},
              follow_redirects=False)
    decision = json.loads((pending.root / "decision.json").read_text(encoding="utf-8"))
    assert decision["approved"] is False
    assert decision["decided_by"]


def test_decided_run_leaves_the_queue(client, pending):
    http, _ = client
    http.post(f"/approvals/{pending.run_id}", data={"decision": "reject"},
              follow_redirects=False)
    assert pending.run_id not in http.get("/approvals").text


def test_invalid_decision_value_is_rejected(client, pending):
    http, _ = client
    response = http.post(f"/approvals/{pending.run_id}", data={"decision": "co-le-vay"},
                         follow_redirects=False)
    assert response.status_code == 400


def test_approving_an_unknown_run_returns_404(client):
    http, _ = client
    response = http.post("/approvals/20200101T000000Z", data={"decision": "approve"},
                         follow_redirects=False)
    assert response.status_code == 404
