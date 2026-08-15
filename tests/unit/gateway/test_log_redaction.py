from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import execute_candidate
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import RealTransport


def test_audit_contains_provenance_but_not_secret(tmp_path, gateway_ready):
    allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
    templates = ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")
    candidate = VerificationCandidate(
        "cand-1", "obj-1", "prop-1",
        VerificationDecision.PLANNED, "ep_health", "tmpl_health_get", "GET",
        "/WebGoat/actuator/health",
    )
    secret = gateway_ready
    log_path = tmp_path / "audit.jsonl"
    result = execute_candidate(candidate, RealTransport(), allowlist, templates, secret, log_path=str(log_path))
    assert result.status_code in {200, 429}
    content = log_path.read_text(encoding="utf-8")
    assert secret not in content
    assert '"objective_id": "obj-1"' in content
    assert '"proposal_id": "prop-1"' in content
    assert '"policy_decision": "ALLOWED"' in content
