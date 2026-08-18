"""Đầu ra của agent là dữ liệu không đáng tin; hàm này là chỗ nó bị kẹp lại."""

from pathlib import Path
import pytest
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.proposal import (
    PAYLOAD_KIND_TO_TYPE,
    validate_objective,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return Allowlist.from_json(ALLOWLIST_PATH)


def _objective(**overrides) -> dict:
    base = {
        "description": "Quan sát phản hồi khi gửi chuỗi dài",
        "endpoint_hint": "POST /WebGoat/attack",
        "payload_kind": "long_string",
        "rationale": "Finding nằm ở handler nhận tham số của lesson router.",
    }
    base.update(overrides)
    return base


def test_four_payload_kinds_are_mapped():
    assert set(PAYLOAD_KIND_TO_TYPE) == {
        "long_string",
        "special_chars",
        "empty_value",
        "wrong_type",
    }


def test_allowlisted_objective_is_accepted(allowlist):
    decision = validate_objective(_objective(), allowlist)
    assert decision.accepted, decision.reason
    assert decision.probe.method == "POST"
    assert decision.probe.path == "/WebGoat/attack"
    assert decision.probe.payload_kind == "long_string"


def test_null_objective_is_rejected_without_error(allowlist):
    decision = validate_objective(None, allowlist)
    assert not decision.accepted
    assert decision.probe is None
    assert "không đề xuất" in decision.reason


def test_endpoint_outside_allowlist_is_rejected(allowlist):
    decision = validate_objective(
        _objective(endpoint_hint="GET /WebGoat/admin"), allowlist
    )
    assert not decision.accepted
    assert "allowlist" in decision.reason


def test_absolute_url_is_rejected(allowlist):
    decision = validate_objective(
        _objective(endpoint_hint="GET https://external.invalid/admin"), allowlist
    )
    assert not decision.accepted


def test_method_not_allowed_for_that_path_is_rejected(allowlist):
    decision = validate_objective(
        _objective(endpoint_hint="POST /WebGoat/actuator/health"), allowlist
    )
    assert not decision.accepted, "health chỉ cho phép GET"


def test_unknown_payload_kind_is_rejected(allowlist):
    decision = validate_objective(_objective(payload_kind="drop_table"), allowlist)
    assert not decision.accepted
    assert "payload" in decision.reason


def test_malformed_hint_is_rejected(allowlist):
    for bad in ["", "/WebGoat/attack", "GET", "DELETE /WebGoat/attack", "GET  /a  /b"]:
        decision = validate_objective(_objective(endpoint_hint=bad), allowlist)
        assert not decision.accepted, f"Chuỗi hỏng vẫn được chấp nhận: {bad!r}"


def test_query_string_in_hint_is_rejected(allowlist):
    decision = validate_objective(
        _objective(endpoint_hint="GET /WebGoat/attack?admin=1"), allowlist
    )
    assert not decision.accepted


def test_missing_required_field_is_rejected(allowlist):
    broken = _objective()
    del broken["rationale"]
    decision = validate_objective(broken, allowlist)
    assert not decision.accepted


def test_non_string_payload_kind_is_rejected(allowlist):
    for bad_kind in [["long_string"], {"k": "v"}, 123]:
        decision = validate_objective(_objective(payload_kind=bad_kind), allowlist)
        assert not decision.accepted
        assert decision.probe is None


def test_non_dict_objective_is_rejected(allowlist):
    for bad_obj in ["POST /WebGoat/attack", ["list"], 123, True]:
        decision = validate_objective(bad_obj, allowlist)
        assert not decision.accepted
        assert decision.probe is None


def test_non_string_endpoint_hint_is_rejected(allowlist):
    for bad_hint in [123, ["GET", "/WebGoat/attack"], {"hint": "test"}]:
        decision = validate_objective(_objective(endpoint_hint=bad_hint), allowlist)
        assert not decision.accepted
        assert decision.probe is None
