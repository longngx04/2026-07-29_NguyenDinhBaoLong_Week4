from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import API_KEY_HEADER, GATEWAY_ORIGIN, execute_candidate
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision, VerificationStatus
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import FakeTransport


def _configs():
    return Allowlist.from_json("configs/gateway/endpoint-allowlist.json"), ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")


def _candidate():
    return VerificationCandidate(
        "cand-1", "obj-1", "prop-1",
        VerificationDecision.PLANNED, "ep_health", "tmpl_health_get", "GET",
        "/WebGoat/actuator/health",
    )


def test_executor_uses_fixed_gateway_origin_and_one_key_header(tmp_path):
    transport = FakeTransport(status_code=200)
    result = execute_candidate(_candidate(), transport, *_configs(), "secret", log_path=str(tmp_path / "audit.jsonl"))
    assert result.status is VerificationStatus.OBSERVED
    assert transport.last_request.url == GATEWAY_ORIGIN + "/WebGoat/actuator/health"
    assert transport.last_request.headers == {API_KEY_HEADER: "secret"}


def test_rate_limited_is_not_observed(tmp_path):
    transport = FakeTransport(status_code=429, headers={"X-Sentinel-Gateway": "true"})
    result = execute_candidate(_candidate(), transport, *_configs(), "secret", log_path=str(tmp_path / "audit.jsonl"))
    assert result.status is VerificationStatus.RATE_LIMITED


def test_untagged_503_is_inconclusive_not_rate_limited(tmp_path):
    transport = FakeTransport(status_code=503)
    result = execute_candidate(_candidate(), transport, *_configs(), "secret", log_path=str(tmp_path / "audit.jsonl"))
    assert result.status is VerificationStatus.INCONCLUSIVE


def test_policy_denial_never_invokes_transport(tmp_path):
    candidate = _candidate()
    candidate.path = "/WebGoat/disallowed"
    transport = FakeTransport()
    result = execute_candidate(candidate, transport, *_configs(), "secret", log_path=str(tmp_path / "audit.jsonl"))
    assert result.status is VerificationStatus.DENIED
    assert transport.last_request is None
