"""reachability do duoc tu Python ghi de gia tri Agent tu khai."""

from project_sentinel.analysis.calibration import calibrate_record


def _record(**over):
    base = {
        "disposition": "confirmed", "severity": "high",
        "attacker_control": "proven", "reachability": "not_proven",
        "explanation": "", "confidence_rationale": "",
    }
    base.update(over)
    return base


def test_without_a_measurement_nothing_changes():
    after, calibration = calibrate_record(_record())
    assert after["reachability"] == "not_proven"
    assert "reachability_measured" not in calibration.rules


def test_a_measurement_overwrites_what_the_agent_claimed():
    after, calibration = calibrate_record(_record(), measured_reachability="proven")
    assert after["reachability"] == "proven"
    assert "reachability_measured" in calibration.rules


def test_measurement_can_contradict_the_agent_downward():
    after, _ = calibrate_record(
        _record(reachability="proven"), measured_reachability="not_proven"
    )
    assert after["reachability"] == "not_proven"


def test_confirmed_survives_when_both_proofs_hold():
    after, calibration = calibrate_record(_record(), measured_reachability="proven")
    assert after["disposition"] == "confirmed"
    assert "confirmed_requires_proof" not in calibration.rules


def test_confirmed_still_falls_when_attacker_control_is_missing():
    after, calibration = calibrate_record(
        _record(attacker_control="not_proven"), measured_reachability="proven"
    )
    assert after["disposition"] == "needs_review", (
        "DAST baseline chung minh reachability, KHONG chung minh attacker control"
    )
    assert "confirmed_requires_proof" in calibration.rules


def test_an_invalid_measurement_is_ignored():
    after, calibration = calibrate_record(_record(), measured_reachability="chac-chan")
    assert after["reachability"] == "not_proven"
    assert "reachability_measured" not in calibration.rules


def test_a_measurement_equal_to_the_claim_leaves_no_trace():
    after, calibration = calibrate_record(
        _record(reachability="proven"), measured_reachability="proven"
    )
    assert after["reachability"] == "proven"
    assert "reachability_measured" not in calibration.rules
