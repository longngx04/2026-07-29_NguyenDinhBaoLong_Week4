"""`decision.json` là cổng HITL. Nó phải fail closed trước mọi kiểu sai.

`bool("false")` trong Python là `True`. Nghĩa là một UI, một script, hay một người
vận hành ghi `{"approved": "false"}` — ý định TỪ CHỐI — sẽ được cổng hiểu là ĐỒNG Ý
và request thật sự được gửi đi. Đây là bypass ngay tại ranh giới người-máy, không
phải lỗi định dạng.

Mọi test dưới đây đi qua **file trên đĩa**, không gọi constructor trực tiếp, vì đó
là đúng đường mà một UI hay một quyết định do người khác ghi sẽ đi vào.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.guardrails.approval import (
    ApprovalDecision,
    read_decision,
    write_decision,
)

TRUTHY_LOOKING_BUT_NOT_TRUE = ["false", "0", "no", "reject", "False", "null", "[]"]


def _write_raw(path: Path, approved) -> Path:
    path.write_text(
        json.dumps(
            {
                "approved": approved,
                "decided_at": "2026-08-21T10:00:00Z",
                "decided_by": "test",
                "request_fingerprint": "abc123",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("approved", TRUTHY_LOOKING_BUT_NOT_TRUE)
def test_a_string_is_never_accepted_as_a_decision(tmp_path, approved):
    """Chuỗi 'false' không được thành True, và cũng không được thành False.

    Fail closed nghĩa là TỪ CHỐI CẢ FILE, không phải đoán ý người viết.
    """
    path = _write_raw(tmp_path / "decision.json", approved)
    with pytest.raises(ValueError, match="approved"):
        read_decision(path)


@pytest.mark.parametrize("approved", [0, 1, 1.0, [], [True], {}, None])
def test_non_boolean_types_are_refused(tmp_path, approved):
    path = _write_raw(tmp_path / "decision.json", approved)
    with pytest.raises(ValueError, match="approved"):
        read_decision(path)


@pytest.mark.parametrize("approved", [True, False])
def test_real_json_booleans_are_accepted(tmp_path, approved):
    path = _write_raw(tmp_path / "decision.json", approved)
    decision = read_decision(path)
    assert decision is not None
    assert decision.approved is approved


def test_a_missing_approved_field_is_refused(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(
        json.dumps({"decided_at": "t", "decided_by": "x"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="approved"):
        read_decision(path)


def test_a_decision_file_that_is_not_an_object_is_refused(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        read_decision(path)


def test_round_trip_through_disk_preserves_the_decision(tmp_path):
    path = tmp_path / "decision.json"
    for approved in (True, False):
        write_decision(
            path,
            ApprovalDecision(
                approved=approved,
                decided_at="2026-08-21T10:00:00Z",
                decided_by="cli-operator",
                request_fingerprint="fp",
            ),
        )
        assert read_decision(path).approved is approved


def test_a_missing_file_is_still_just_no_decision(tmp_path):
    assert read_decision(tmp_path / "khong-ton-tai.json") is None
