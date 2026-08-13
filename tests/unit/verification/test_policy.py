from project_sentinel.gateway.allowlist import Allowlist, AllowlistRule
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.policy import validate_candidate_policy


def _get_allowlist():
    return Allowlist([
        AllowlistRule(method="GET", path="/WebGoat/actuator/health", match="exact"),
        AllowlistRule(method="GET", path="/WebGoat/attack", match="prefix"),
        AllowlistRule(method="POST", path="/WebGoat/attack", match="prefix"),
    ])


def test_policy_valid_candidate_allowed():
    allowlist = _get_allowlist()
    candidate = VerificationCandidate(
        candidate_id="cand-001",
        analysis_record_id="rec-001",
        group_id="group-001",
        cwe="CWE-89",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )

    allowed, reason = validate_candidate_policy(candidate, allowlist)
    assert allowed is True
    assert reason is None


def test_policy_not_plannable_denied():
    allowlist = _get_allowlist()
    candidate = VerificationCandidate(
        candidate_id="cand-002",
        analysis_record_id="rec-002",
        group_id="group-002",
        cwe="CWE-999",
        decision=VerificationDecision.NOT_PLANNABLE,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )

    allowed, reason = validate_candidate_policy(candidate, allowlist)
    assert allowed is False
    assert "not marked PLANNED" in reason


def test_policy_unknown_endpoint_denied():
    allowlist = _get_allowlist()
    candidate = VerificationCandidate(
        candidate_id="cand-003",
        analysis_record_id="rec-003",
        group_id="group-003",
        cwe="CWE-89",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_arbitrary_unknown",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )

    allowed, reason = validate_candidate_policy(candidate, allowlist)
    assert allowed is False
    assert "not in allowed inventory" in reason


def test_policy_allowlist_denied_path():
    allowlist = _get_allowlist()
    candidate = VerificationCandidate(
        candidate_id="cand-004",
        analysis_record_id="rec-004",
        group_id="group-004",
        cwe="CWE-89",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/login",
    )

    allowed, reason = validate_candidate_policy(candidate, allowlist)
    assert allowed is False
    assert "denied by allowlist" in reason
