"""Số liệu phải nói đúng cái đã xảy ra, không phải cái còn sót lại.

Vòng review 82/100 chỉ ra ba chỗ số liệu nói sai:

1. Retry thành công thì code đặt `invalid_output_count = 0`, nên một nhóm
   hỏng-rồi-sửa-được trông hệt như một nhóm chưa bao giờ hỏng.
2. Token của lần thử lại không được cộng, nên chi phí báo về thấp hơn thực tế
   đúng bằng phần đắt nhất.
3. Không nạp được allowlist thì bỏ qua luôn việc kiểm objective, và
   `invalid_objective_count = 0` — không phải vì Agent làm đúng mà vì không có
   gì để so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_sentinel.analysis.pipeline import (
    _allowed_endpoints_hint,
    _GroupOutcome,
    _load_allowlist,
    _ResponseErrors,
    _settle,
)
from project_sentinel.config import AppConfig
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.llm.base import LLMResult

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_JSON = REPO_ROOT / "configs/gateway/endpoint-allowlist.json"


@pytest.fixture
def allowlist() -> Allowlist:
    return Allowlist.from_json(ALLOWLIST_JSON)


def _record(objective=None) -> dict:
    return {
        "analysis_id": "analysis-a",
        "title": "A",
        "severity": "medium",
        "disposition": "needs_review",
        "verification_objective": objective,
    }


# --- M-2: đếm phản hồi hỏng tách khỏi đếm nhóm hỏng ------------------------


def test_tokens_from_every_attempt_are_counted():
    outcome = _GroupOutcome(record=None, prompt_sha256="")

    outcome.add_tokens(LLMResult(raw_response="", prompt_tokens=100, completion_tokens=20, total_tokens=120))
    outcome.add_tokens(LLMResult(raw_response="", prompt_tokens=110, completion_tokens=25, total_tokens=135))

    assert (outcome.prompt_tokens, outcome.completion_tokens, outcome.total_tokens) == (
        210,
        45,
        255,
    )


def test_a_provider_that_reports_no_tokens_does_not_become_a_zero():
    """`None` nghĩa là "không biết", không phải "bằng không"."""
    outcome = _GroupOutcome(record=None, prompt_sha256="")

    outcome.add_tokens(LLMResult(raw_response=""))

    assert outcome.total_tokens is None


def test_a_schema_error_still_loses_the_record():
    outcome = _settle(
        _GroupOutcome(record=None, prompt_sha256=""),
        _record(),
        _ResponseErrors(schema="thiếu field bắt buộc"),
        None,
    )

    assert outcome.record is None
    assert outcome.invalid_output_count == 1


# --- H-3: objective sai không được làm mất record, nhưng phải đếm ---------


def test_a_bad_objective_nulls_itself_instead_of_dropping_the_analysis():
    record = _record({"endpoint_hint": "GET /khong-co-that", "payload_kind": "empty_value"})

    outcome = _settle(
        _GroupOutcome(record=None, prompt_sha256=""),
        record,
        _ResponseErrors(objective="verification_objective bị allowlist từ chối"),
        None,
    )

    assert outcome.record is not None
    assert outcome.record["verification_objective"] is None
    assert outcome.invalid_objective_count == 1
    assert outcome.valid_objective_count == 0


def test_a_good_objective_is_counted_so_the_rate_can_be_reported():
    """Lần chạy thật có 18 record và 0 objective dùng được — phải đo được."""
    record = _record({"endpoint_hint": "GET /WebGoat/login", "payload_kind": None})

    outcome = _settle(
        _GroupOutcome(record=None, prompt_sha256=""), record, _ResponseErrors(), None
    )

    assert outcome.valid_objective_count == 1
    assert outcome.invalid_objective_count == 0


def test_retry_feedback_names_the_endpoints_that_would_have_been_valid(allowlist):
    """"Bị allowlist từ chối" là đúng nhưng vô dụng: Agent không biết chọn gì."""
    errors = _ResponseErrors(objective="verification_objective bị allowlist từ chối")

    feedback = errors.feedback(allowlist)

    assert "GET /WebGoat/login" in feedback
    assert "POST /WebGoat/attack" in feedback
    assert "empty_value" in feedback


def test_the_hint_only_lists_combinations_that_really_exist(allowlist):
    """Gợi ý một tổ hợp chưa được review sẽ dạy Agent làm sai lần sau."""
    hint = _allowed_endpoints_hint(allowlist)

    assert "special_chars" not in hint
    assert "wrong_type" not in hint
    for line in hint.split(";"):
        if "endpoint_hint" not in line:
            continue
        assert "/WebGoat/" in line


def test_there_is_no_hint_when_there_is_no_allowlist():
    assert _allowed_endpoints_hint(None) == ""


# --- M-3: không nạp được allowlist phải nói ra, không im lặng --------------


def test_an_unreadable_allowlist_reports_why_instead_of_returning_none(tmp_path):
    config = AppConfig(
        project_root=tmp_path,
        api_key="test-key",
        allowlist_path=tmp_path / "khong-ton-tai.json",
    )

    loaded, problem = _load_allowlist(config)

    assert loaded is None
    assert problem is not None
    assert "khong-ton-tai.json" in problem
    assert "KHÔNG được kiểm" in problem


def test_the_committed_allowlist_loads_without_degrading_the_run(tmp_path):
    config = AppConfig(
        project_root=tmp_path, api_key="test-key", allowlist_path=ALLOWLIST_JSON
    )

    loaded, problem = _load_allowlist(config)

    assert loaded is not None
    assert problem is None
