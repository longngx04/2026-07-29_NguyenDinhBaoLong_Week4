"""Cổng phê duyệt của con người trước khi gửi request rủi ro."""

import json

import pytest

from project_sentinel.guardrails.approval import (
    ApprovalDecision,
    build_request,
    prompt_cli,
    read_decision,
    requires_approval,
    write_decision,
)
from project_sentinel.probe.proposal import SafeProbe


def test_plain_get_does_not_require_approval():
    assert requires_approval(SafeProbe("GET", "/WebGoat/actuator/health", None)) is False


def test_post_always_requires_approval():
    assert requires_approval(SafeProbe("POST", "/WebGoat/attack", None)) is True


def test_get_with_special_payload_requires_approval():
    assert requires_approval(SafeProbe("GET", "/WebGoat/attack", "long_string")) is True


@pytest.mark.parametrize(
    "kind", ["long_string", "special_chars", "empty_value", "wrong_type"]
)
def test_every_payload_kind_requires_approval(kind):
    assert requires_approval(SafeProbe("GET", "/WebGoat/attack", kind)) is True


def test_request_shows_the_four_things_the_operator_must_see():
    """Đề bài đòi: endpoint, payload, mục đích, và hai lựa chọn."""
    request = build_request(
        "run-1",
        SafeProbe("POST", "/WebGoat/attack", "long_string"),
        purpose="Xac nhan handler co gioi han do dai dau vao khong",
    )
    data = request.to_dict()
    assert data["endpoint"] == "/WebGoat/attack"
    assert data["method"] == "POST"
    assert data["payload"] is not None and data["payload"] != ""
    assert "gioi han do dai" in data["purpose"]
    assert data["risk_reason"]


def test_payload_shown_is_the_real_safe_payload():
    request = build_request("run-1", SafeProbe("POST", "/WebGoat/attack", "long_string"), purpose="x")
    assert "A" * 20 in request.payload, "Người duyệt phải thấy payload thật sẽ được gửi"


def test_decision_round_trips_through_disk(tmp_path):
    path = tmp_path / "decision.json"
    write_decision(path, ApprovalDecision(approved=True, decided_at="2026-08-17T10:00:00Z", decided_by="operator"))
    loaded = read_decision(path)
    assert loaded.approved is True
    assert loaded.decided_by == "operator"


def test_missing_decision_file_reads_as_none(tmp_path):
    assert read_decision(tmp_path / "khong-ton-tai.json") is None


def test_cli_approve_returns_approved():
    request = build_request("run-1", SafeProbe("POST", "/WebGoat/attack", "empty_value"), purpose="x")
    lines = []
    decision = prompt_cli(request, input_fn=lambda _: "approve", output_fn=lines.append)
    assert decision.approved is True
    assert any("/WebGoat/attack" in line for line in lines)
    assert any("POST" in line for line in lines)


def test_cli_reject_returns_rejected():
    request = build_request("run-1", SafeProbe("POST", "/WebGoat/attack", "empty_value"), purpose="x")
    decision = prompt_cli(request, input_fn=lambda _: "reject", output_fn=lambda _: None)
    assert decision.approved is False


def test_cli_treats_anything_that_is_not_approve_as_reject():
    """Mặc định phải là từ chối. Gõ nhầm không được biến thành đồng ý."""
    request = build_request("run-1", SafeProbe("POST", "/WebGoat/attack", "empty_value"), purpose="x")
    for answer in ["", "y", "yes", "co", "\n", "APPROVE!"]:
        decision = prompt_cli(request, input_fn=lambda _: answer, output_fn=lambda _: None)
        assert decision.approved is False, f"Câu trả lời {answer!r} không được tính là đồng ý"


def test_cli_accepts_approve_case_insensitively():
    request = build_request("run-1", SafeProbe("POST", "/WebGoat/attack", "empty_value"), purpose="x")
    for answer in ["approve", "APPROVE", "  Approve  "]:
        decision = prompt_cli(request, input_fn=lambda _: answer, output_fn=lambda _: None)
        assert decision.approved is True
