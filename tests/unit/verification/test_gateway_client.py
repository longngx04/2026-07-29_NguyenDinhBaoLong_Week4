from project_sentinel.gateway.allowlist import Allowlist, AllowlistRule
from project_sentinel.verification.gateway_client import execute_candidate
from project_sentinel.verification.models import (
    VerificationCandidate,
    VerificationDecision,
    VerificationStatus,
)
from project_sentinel.verification.transport import FakeTransport


def _get_allowlist():
    return Allowlist([
        AllowlistRule(method="GET", path="/WebGoat/actuator/health", match="exact"),
        AllowlistRule(method="POST", path="/WebGoat/attack", match="prefix"),
    ])


def test_execute_candidate_valid_200_ok(tmp_path):
    allowlist = _get_allowlist()
    transport = FakeTransport(status_code=200, body='{"status":"UP"}')
    candidate = VerificationCandidate(
        candidate_id="cand-101",
        analysis_record_id="rec-101",
        group_id="group-101",
        cwe="CWE-200",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )

    log_file = str(tmp_path / "requests.log.jsonl")
    result = execute_candidate(
        candidate=candidate,
        transport=transport,
        allowlist=allowlist,
        api_key="test-api-key",
        log_path=log_file,
    )

    assert result.status == VerificationStatus.VERIFIED_REACHABLE
    assert result.status_code == 200
    assert result.response_bytes_observed == len('{"status":"UP"}')
    assert result.truncated is False
    assert result.error_class is None


def test_execute_candidate_policy_denial(tmp_path):
    allowlist = _get_allowlist()
    transport = FakeTransport(status_code=200)
    candidate = VerificationCandidate(
        candidate_id="cand-102",
        analysis_record_id="rec-102",
        group_id="group-102",
        cwe="CWE-89",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/disallowed_endpoint",
    )

    result = execute_candidate(
        candidate=candidate,
        transport=transport,
        allowlist=allowlist,
        api_key="test-api-key",
        log_path=str(tmp_path / "requests.log.jsonl"),
    )

    assert result.status == VerificationStatus.DENIED
    assert result.status_code is None
    assert result.error_class == "PolicyViolation"
    assert transport.last_request is None  # Transport was NOT invoked


def test_execute_candidate_timeout_handling(tmp_path):
    allowlist = _get_allowlist()
    transport = FakeTransport(should_timeout=True)
    candidate = VerificationCandidate(
        candidate_id="cand-103",
        analysis_record_id="rec-103",
        group_id="group-103",
        cwe="CWE-200",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )

    result = execute_candidate(
        candidate=candidate,
        transport=transport,
        allowlist=allowlist,
        api_key="test-api-key",
        log_path=str(tmp_path / "requests.log.jsonl"),
    )

    assert result.status == VerificationStatus.UNREACHABLE
    assert result.status_code is None
    assert result.error_class == "TimeoutException"
