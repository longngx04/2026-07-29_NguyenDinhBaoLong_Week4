"""Tests for exact, deny-by-default Phase 4 proposal resolution."""

import json
from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.policy import validate_candidate_policy
from project_sentinel.verification.resolver import ResolutionDenial, resolve_proposal
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.validators import validate_verification_plan_schema

_REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = _REPO_ROOT / "configs" / "verification" / "endpoint-catalog.json"
ALLOWLIST_PATH = _REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"
TEMPLATES_PATH = _REPO_ROOT / "configs" / "verification" / "probe-templates.json"


@pytest.fixture
def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def allowlist():
    return Allowlist.from_json(ALLOWLIST_PATH)


@pytest.fixture
def templates():
    return ProbeTemplateRegistry.from_json(TEMPLATES_PATH)


def _proposal(**overrides):
    proposal = {
        "objective_id": "obj-health-check",
        "proposal_id": "prop-001",
        "endpoint_id": "ep_health",
        "reason": "Health endpoint selected",
        "method": "GET",
        "template_id": "tmpl_health_get",
        "payload_type": None,
        "headers": {"Accept": "application/json"},
        "parameters": {},
    }
    proposal.update(overrides)
    return proposal


def _resolve(proposal, catalog, allowlist, templates):
    return resolve_proposal(proposal, catalog, allowlist, templates)


def test_health_get_resolves_to_final_policy_valid_candidate(catalog, allowlist, templates):
    outcome = _resolve(_proposal(), catalog, allowlist, templates)
    assert isinstance(outcome, VerificationCandidate)
    assert outcome.decision is VerificationDecision.PLANNED
    assert outcome.path == "/WebGoat/actuator/health"
    assert outcome.target_field is None
    assert outcome.payload_type is None
    assert validate_candidate_policy(outcome, allowlist, templates) == (True, None)
    validate_verification_plan_schema(outcome.to_dict())


def test_safe_post_resolves_internal_payload_from_template(catalog, allowlist, templates):
    outcome = _resolve(
        _proposal(
            objective_id="obj-attack-safe-post",
            proposal_id="prop-002",
            endpoint_id="ep_attack",
            method="POST",
            template_id="tmpl_attack_post_empty",
            payload_type="EMPTY",
            headers={"Accept": "application/json"},
        ),
        catalog,
        allowlist,
        templates,
    )
    assert isinstance(outcome, VerificationCandidate)
    assert outcome.target_field == "input"
    assert outcome.payload_type == "empty_value"
    assert validate_candidate_policy(outcome, allowlist, templates) == (True, None)


def test_schema_valid_decline_is_not_applicable(catalog, allowlist, templates):
    outcome = _resolve(
        _proposal(
            objective_id="obj-unmapped-finding",
            proposal_id="prop-declined",
            endpoint_id=None,
            method=None,
            template_id=None,
            payload_type=None,
            headers=None,
            parameters=None,
        ),
        catalog,
        allowlist,
        templates,
    )
    assert isinstance(outcome, VerificationCandidate)
    assert outcome.decision is VerificationDecision.NOT_APPLICABLE
    validate_verification_plan_schema(outcome.to_dict())


@pytest.mark.parametrize(
    ("proposal", "reason_code"),
    [
        (_proposal(endpoint_id="ep_invented"), "ENDPOINT_NOT_CATALOGUED"),
        (_proposal(method="DELETE"), "PROPOSAL_SCHEMA_INVALID"),
        (_proposal(template_id=None), "PROPOSAL_SCHEMA_INVALID"),
        (_proposal(path="http://untrusted.invalid/"), "PROPOSAL_SCHEMA_INVALID"),
        (_proposal(parameters={"cmd": "literal-unreviewed-value"}), "PARAMETERS_NOT_ALLOWED"),
        (_proposal(headers={"Host": "untrusted.invalid"}), "RESTRICTED_HEADER"),
        (_proposal(headers={"Accept": "application/xml"}), "HEADER_VALUE_NOT_ALLOWED"),
        (
            _proposal(
                objective_id="obj-attack-safe-post",
                endpoint_id="ep_attack",
                method="POST",
                template_id="tmpl_attack_get",
            ),
            "TEMPLATE_TUPLE_MISMATCH",
        ),
        (_proposal(payload_type="EMPTY"), "PAYLOAD_TYPE_MISMATCH"),
    ],
)
def test_adversarial_proposals_are_typed_denials(
    proposal,
    reason_code,
    catalog,
    allowlist,
    templates,
):
    outcome = _resolve(proposal, catalog, allowlist, templates)
    assert isinstance(outcome, ResolutionDenial)
    assert outcome.decision is VerificationDecision.NOT_PLANNABLE
    assert outcome.reason_code == reason_code


@pytest.mark.parametrize(
    "proposal",
    [
        _proposal(endpoint_id="ep_invented"),
        _proposal(method="DELETE"),
        _proposal(path="http://untrusted.invalid/"),
        _proposal(parameters={"cmd": "literal-unreviewed-value"}),
        _proposal(headers={"Authorization": "untrusted"}),
    ],
)
def test_adversarial_resolution_never_reaches_gateway_boundary(
    proposal,
    catalog,
    allowlist,
    templates,
    gateway_ready,
    gateway_access_log_tracker,
):
    assert gateway_ready
    logs_before = gateway_access_log_tracker()
    outcome = _resolve(proposal, catalog, allowlist, templates)
    logs_after = gateway_access_log_tracker()
    assert isinstance(outcome, ResolutionDenial)
    assert logs_after == logs_before


def test_load_endpoint_catalog_rejects_malformed(tmp_path):
    from project_sentinel.verification.resolver import load_endpoint_catalog

    # 1. Non-dict root
    p1 = tmp_path / "c1.json"
    p1.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_endpoint_catalog(p1)

    # 2. Empty endpoints list
    p2 = tmp_path / "c2.json"
    p2.write_text('{"endpoints": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        load_endpoint_catalog(p2)

    # 3. Duplicate endpoint_id
    p3 = tmp_path / "c3.json"
    p3.write_text(json.dumps({
        "endpoints": [
            {"endpoint_id": "ep_1", "path": "/p1", "allowed_methods": ["GET"], "allowed_template_ids": ["t1"]},
            {"endpoint_id": "ep_1", "path": "/p2", "allowed_methods": ["GET"], "allowed_template_ids": ["t2"]},
        ]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate endpoint_id"):
        load_endpoint_catalog(p3)

    # 4. Invalid method
    p4 = tmp_path / "c4.json"
    p4.write_text(json.dumps({
        "endpoints": [
            {"endpoint_id": "ep_1", "path": "/p1", "allowed_methods": ["INVALID_METHOD"], "allowed_template_ids": ["t1"]},
        ]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid method"):
        load_endpoint_catalog(p4)
