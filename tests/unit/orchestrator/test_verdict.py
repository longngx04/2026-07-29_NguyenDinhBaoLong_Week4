"""Probe kết luận được gì về finding — và phần lớn trường hợp là "chưa gì cả".

Lần chạy cuối gửi `GET /WebGoat/login`, nhận HTTP 200, rồi báo cáo in kết quả
đó ngay dưới danh sách finding SQL Injection. Một người đọc nhanh sẽ hiểu là
lỗ hổng đã được kiểm chứng. Nó không được kiểm chứng: endpoint đó không nằm
trong bằng chứng của bất kỳ finding nào.

Module verdict tồn tại để nói thẳng điều đó, bằng ba từ cố định.
"""

import pytest

from project_sentinel.orchestrator.verdict import decide_verdict


def _analysis(analysis_id="analysis-a", evidence_content="stmt.executeQuery(query)"):
    return {
        "analysis_id": analysis_id,
        "source_finding_ids": ["finding-1"],
        "title": "SQL Injection",
        "explanation": "Truy vấn chạy qua Statement.",
        "evidence": [
            {
                "type": "source",
                "path": "SqlInjectionLesson9.java",
                "start_line": 110,
                "end_line": 120,
                "content": evidence_content,
            }
        ],
    }


def _proposal(**overrides):
    base = {
        "accepted": True,
        "source_analysis_id": "analysis-a",
        "probe": {"method": "GET", "path": "/WebGoat/login", "payload_kind": None},
        "objective": {"endpoint_hint": "GET /WebGoat/login"},
        "operator_override": False,
    }
    base.update(overrides)
    return base


def _probe(**overrides):
    base = {"sent": True, "status_code": 200, "body_preview": "<html>Login</html>"}
    base.update(overrides)
    return base


# --- inconclusive ----------------------------------------------------------


def test_no_request_sent_is_inconclusive():
    verdict = decide_verdict(
        proposal=_proposal(accepted=False, probe=None),
        probe={"sent": False, "denied_reason": "không có probe"},
        analyses=[_analysis()],
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "none"


def test_operator_override_is_never_evidence_for_a_finding():
    """Người vận hành chỉ định request thì request đó không gắn với finding nào."""
    verdict = decide_verdict(
        proposal=_proposal(
            operator_override=True, source_analysis_id="operator-override"
        ),
        probe=_probe(),
        analyses=[_analysis()],
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "not_linked"
    assert verdict.analysis_id is None


def test_http_200_on_an_unrelated_endpoint_is_inconclusive():
    """Đây chính là ca của lần chạy cuối: 200 không nói gì về SQLi trong file Java."""
    verdict = decide_verdict(
        proposal=_proposal(), probe=_probe(status_code=200), analyses=[_analysis()]
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "unrelated_endpoint"
    assert "không nằm trong bằng chứng" in verdict.reason


def test_linked_endpoint_without_a_declared_signal_stays_inconclusive():
    """Endpoint có liên quan nhưng không khai trước dấu hiệu cần quan sát."""
    verdict = decide_verdict(
        proposal=_proposal(),
        probe=_probe(),
        analyses=[_analysis(evidence_content="mapping /WebGoat/login handler")],
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "no_declared_signal"


def test_analysis_id_pointing_at_nothing_is_inconclusive():
    verdict = decide_verdict(
        proposal=_proposal(source_analysis_id="analysis-khong-ton-tai"),
        probe=_probe(),
        analyses=[_analysis()],
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "not_linked"


# --- supports / refutes ----------------------------------------------------


def test_declared_signal_present_in_response_supports_the_finding():
    proposal = _proposal(
        objective={
            "endpoint_hint": "GET /WebGoat/login",
            "expected_signal": "SQLException",
        }
    )
    verdict = decide_verdict(
        proposal=proposal,
        probe=_probe(body_preview="java.sql.SQLException: syntax error near"),
        analyses=[_analysis(evidence_content="handler for /WebGoat/login")],
    )
    assert verdict.verdict == "supports"
    assert verdict.evidence_kind == "declared_signal"
    assert verdict.source_finding_ids == ("finding-1",)


def test_declared_signal_absent_from_response_refutes_the_finding():
    proposal = _proposal(
        objective={
            "endpoint_hint": "GET /WebGoat/login",
            "expected_signal": "SQLException",
        }
    )
    verdict = decide_verdict(
        proposal=proposal,
        probe=_probe(body_preview="<html>Login Page</html>"),
        analyses=[_analysis(evidence_content="handler for /WebGoat/login")],
    )
    assert verdict.verdict == "refutes"
    assert verdict.evidence_kind == "declared_signal"


def test_declared_signal_on_an_unrelated_endpoint_is_still_inconclusive():
    """Khai dấu hiệu không cứu được một endpoint không liên quan tới finding."""
    proposal = _proposal(
        objective={
            "endpoint_hint": "GET /WebGoat/login",
            "expected_signal": "Login",
        }
    )
    verdict = decide_verdict(
        proposal=proposal, probe=_probe(body_preview="Login"), analyses=[_analysis()]
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.evidence_kind == "unrelated_endpoint"


# --- bền với dữ liệu hỏng --------------------------------------------------


@pytest.mark.parametrize("bad", [None, [], "chuoi", 42])
def test_broken_artifacts_do_not_crash(bad):
    verdict = decide_verdict(proposal=bad, probe=bad, analyses=[])
    assert verdict.verdict == "inconclusive"


def test_finding_ids_are_carried_through():
    verdict = decide_verdict(
        proposal=_proposal(), probe=_probe(), analyses=[_analysis()]
    )
    assert verdict.analysis_id == "analysis-a"
    assert verdict.source_finding_ids == ("finding-1",)
