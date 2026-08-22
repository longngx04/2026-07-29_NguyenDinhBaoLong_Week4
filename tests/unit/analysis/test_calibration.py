"""Hiệu chỉnh mức nghiêm trọng theo bằng chứng, quyết định phía Python.

Agent có thể vừa viết "không có SQL Injection rõ ràng tại vị trí này" vừa xuất
`severity: high`. Tầng này không hỏi ý Agent: nó áp luật lên chính output đó.
Luật chỉ được phép HẠ, không bao giờ nâng.
"""

import pytest

from project_sentinel.analysis.calibration import (
    SEVERITY_CEILING,
    SEVERITY_ORDER,
    calibrate_record,
)


def _record(**overrides):
    base = {
        "schema_version": "1.0",
        "analysis_id": "analysis-12345",
        "title": "SQL Injection",
        "severity": "high",
        "disposition": "likely",
        "attacker_control": "not_proven",
        "reachability": "proven",
        "confidence": "high",
        "confidence_rationale": "Nối chuỗi trực tiếp vào truy vấn",
        "explanation": "Dữ liệu người dùng được nối thẳng vào câu lệnh SQL.",
    }
    base.update(overrides)
    return base


# --- Luật 1: confirmed đòi cả hai bằng chứng -------------------------------


def test_confirmed_without_proven_attacker_control_becomes_needs_review():
    record, calibration = calibrate_record(
        _record(disposition="confirmed", attacker_control="not_proven")
    )
    assert record["disposition"] == "needs_review"
    assert calibration.applied
    assert "confirmed_requires_proof" in calibration.rules


def test_confirmed_with_both_proven_cannot_stand_because_attacker_control_is_unverifiable():
    record, calibration = calibrate_record(
        _record(
            disposition="confirmed",
            attacker_control="proven",
            reachability="proven",
            severity="critical",
        ),
        measured_reachability="proven",
    )
    assert record["disposition"] != "confirmed"
    assert record["attacker_control"] == "not_proven"
    assert "attacker_control_unverifiable" in calibration.rules


# --- Luật 2: trần severity theo disposition --------------------------------


def test_needs_review_caps_severity_at_medium():
    record, calibration = calibrate_record(
        _record(disposition="needs_review", severity="high")
    )
    assert record["severity"] == "medium"
    assert calibration.severity_from == "high"
    assert calibration.severity_to == "medium"


def test_false_positive_is_forced_to_info():
    record, _ = calibrate_record(
        _record(disposition="false_positive", severity="high")
    )
    assert record["severity"] == "info"


def test_likely_caps_severity_at_high_and_attacker_control_caps_at_medium():
    record, _ = calibrate_record(
        _record(disposition="likely", severity="critical")
    )
    assert record["severity"] == "medium"
    assert SEVERITY_CEILING["likely"] == "high"


def test_cap_never_raises_a_low_severity():
    """Luật là trần, không phải sàn. low ở needs_review vẫn là low."""
    record, calibration = calibrate_record(
        _record(disposition="needs_review", severity="low")
    )
    assert record["severity"] == "low"
    assert not calibration.applied


# --- Luật 3: không chứng minh được attacker control ------------------------


def test_unproven_attacker_control_caps_severity_at_medium():
    record, calibration = calibrate_record(
        _record(disposition="likely", attacker_control="not_proven", severity="high")
    )
    assert record["severity"] == "medium"
    assert "attacker_control_not_proven" in calibration.rules


# --- Luật 4: văn xuôi mâu thuẫn với kết luận có cấu trúc -------------------


@pytest.mark.parametrize(
    "prose",
    [
        "Câu lệnh SQL được thực thi là một truy vấn tĩnh, không có tham số.",
        "Không có lỗ hổng SQL Injection rõ ràng tại vị trí này.",
        "Không có dữ liệu người dùng được nối vào truy vấn.",
        "The query is a static hardcoded string with no user input.",
    ],
)
def test_prose_denying_the_vulnerability_forces_needs_review(prose):
    """Agent tự phủ nhận trong văn xuôi thì kết luận không được là 'likely'."""
    record, calibration = calibrate_record(
        _record(disposition="likely", explanation=prose)
    )
    assert record["disposition"] == "needs_review"
    assert "prose_contradicts_disposition" in calibration.rules


def test_prose_contradiction_never_upgrades_a_false_positive():
    record, _ = calibrate_record(
        _record(disposition="false_positive", explanation="Truy vấn tĩnh, không có tham số")
    )
    assert record["disposition"] == "false_positive"


def test_affirmative_prose_is_not_flagged():
    record, calibration = calibrate_record(
        _record(
            disposition="likely",
            explanation="Tham số name lấy từ request được nối thẳng vào câu lệnh SQL.",
        )
    )
    assert record["disposition"] == "likely"
    assert "prose_contradicts_disposition" not in calibration.rules


# --- Ghi vết ---------------------------------------------------------------


def test_calibration_is_recorded_on_the_record():
    record, _ = calibrate_record(
        _record(disposition="needs_review", severity="high")
    )
    assert record["calibration"]["severity_from"] == "high"
    assert record["calibration"]["severity_to"] == "medium"
    assert record["calibration"]["rules"]


def test_untouched_record_carries_no_calibration_block():
    record, _ = calibrate_record(
        _record(
            disposition="needs_review",
            severity="low",
            attacker_control="not_proven",
            reachability="not_proven",
        )
    )
    assert record.get("calibration") is None


def test_llm_supplied_calibration_block_is_discarded():
    """Agent không được tự khai đã hiệu chỉnh — đó là kết luận của Python."""
    record, _ = calibrate_record(
        _record(
            disposition="needs_review",
            severity="high",
            calibration={"rules": ["bia dat"], "severity_from": "info"},
        )
    )
    assert "bia dat" not in record["calibration"]["rules"]
    assert record["calibration"]["severity_from"] == "high"


# --- Bền với dữ liệu hỏng --------------------------------------------------


def test_unknown_severity_is_left_untouched_rather_than_crashing():
    record, _ = calibrate_record(_record(severity="khong-biet"))
    assert record["severity"] == "khong-biet"


def test_missing_fields_do_not_crash():
    record, calibration = calibrate_record({"title": "X"})
    assert record["title"] == "X"
    assert not calibration.applied


def test_severity_order_is_low_to_high():
    assert SEVERITY_ORDER.index("info") < SEVERITY_ORDER.index("critical")
