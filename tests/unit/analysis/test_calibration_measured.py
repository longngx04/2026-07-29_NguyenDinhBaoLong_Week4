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


def test_confirmed_cannot_survive_because_attacker_control_is_unverifiable():
    after, calibration = calibrate_record(_record(), measured_reachability="proven")
    assert after["disposition"] != "confirmed"
    assert "attacker_control_unverifiable" in calibration.rules


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


def test_extract_measured_reachability_empty_source_ids_returns_none():
    from types import SimpleNamespace
    from project_sentinel.analysis.pipeline import _extract_measured_reachability

    group = SimpleNamespace(findings=[{"id": "f1", "runtime_evidence": {"strength": "reachable"}}])

    # Empty source_finding_ids must return None (fail closed)
    result = _extract_measured_reachability(group, {"source_finding_ids": []})
    assert result is None

    result_none = _extract_measured_reachability(group, {})
    assert result_none is None


def test_extract_measured_reachability_matching_source_id():
    from types import SimpleNamespace
    from project_sentinel.analysis.pipeline import _extract_measured_reachability

    group = SimpleNamespace(
        findings=[
            {"id": "f1", "runtime_evidence": {"strength": "reachable"}},
            {"id": "f2", "runtime_evidence": {"strength": "route_known_not_reached"}},
        ]
    )

    # Only f1 selected
    res1 = _extract_measured_reachability(group, {"source_finding_ids": ["f1"]})
    assert res1 == "proven"

    # Only f2 selected
    res2 = _extract_measured_reachability(group, {"source_finding_ids": ["f2"]})
    assert res2 == "not_proven"

    # Non-matching f3
    res3 = _extract_measured_reachability(group, {"source_finding_ids": ["f3"]})
    assert res3 is None


