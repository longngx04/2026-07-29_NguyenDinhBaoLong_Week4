from dataclasses import replace

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.policy import validate_candidate_policy
from project_sentinel.verification.templates import ProbeTemplateRegistry


def _configs():
    return Allowlist.from_json("configs/gateway/endpoint-allowlist.json"), ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")


def _candidate():
    return VerificationCandidate(
        "cand-1", "obj-1", "prop-1",
        VerificationDecision.PLANNED, "ep_health", "tmpl_health_get", "GET",
        "/WebGoat/actuator/health",
    )


def test_policy_allows_exact_reviewed_tuple():
    assert validate_candidate_policy(_candidate(), *_configs()) == (True, None)


def test_policy_rejects_not_plannable_without_transport():
    allowed, reason = validate_candidate_policy(replace(_candidate(), decision=VerificationDecision.NOT_PLANNABLE), *_configs())
    assert not allowed
    assert "not marked PLANNED" in reason


def test_policy_rejects_endpoint_template_swap():
    allowed, reason = validate_candidate_policy(replace(_candidate(), endpoint_id="ep_attack", path="/WebGoat/attack"), *_configs())
    assert not allowed
    assert "exactly match" in reason
