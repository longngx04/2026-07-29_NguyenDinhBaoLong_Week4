"""Tests for strict Phase 3 probe proposal generation."""

import json
import os
from pathlib import Path

import pytest

from project_sentinel.llm.openrouter import OpenRouterClient
from project_sentinel.verification.proposer import (
    ProposalOutcomeStatus,
    generate_probe_proposal,
    parse_proposal_response,
    render_proposer_prompt,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = _REPO_ROOT / "configs" / "verification" / "endpoint-catalog.json"


@pytest.fixture
def sample_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def sample_objective():
    return {
        "objective_id": "obj-health-check",
        "description": "Verify WebGoat reachability via health endpoint",
        "finding_context": "System health check target",
        "target_endpoint_hint": "ep_health",
    }


def _valid_proposal(**overrides):
    proposal = {
        "objective_id": "obj-health-check",
        "proposal_id": "prop-12345",
        "endpoint_id": "ep_health",
        "reason": "Health endpoint selected for reachability check",
        "method": "GET",
        "template_id": "tmpl_health_get",
        "payload_type": None,
        "headers": {"Accept": "application/json"},
        "parameters": {},
    }
    proposal.update(overrides)
    return proposal


def test_render_proposer_prompt(sample_catalog, sample_objective):
    system_prompt, user_prompt = render_proposer_prompt(sample_catalog, sample_objective)
    assert "Probe Proposal Generator" in system_prompt
    assert "obj-health-check" in user_prompt
    assert "ep_health" in user_prompt
    assert "/WebGoat/actuator/health" in user_prompt


def test_parse_proposal_response_valid():
    outcome = parse_proposal_response(json.dumps(_valid_proposal()), "obj-health-check")
    assert outcome.status is ProposalOutcomeStatus.PROPOSED
    assert outcome.proposal == _valid_proposal()
    assert outcome.error_reason is None


@pytest.mark.parametrize(
    "raw_text",
    [
        "not json",
        "[]",
        "```json\n{}\n```",
    ],
)
def test_parse_proposal_response_rejects_non_contract_output(raw_text):
    outcome = parse_proposal_response(raw_text, "obj-health-check")
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID
    assert outcome.proposal is None
    assert outcome.error_reason


def test_parse_proposal_response_rejects_missing_proposal_id():
    proposal = _valid_proposal()
    proposal.pop("proposal_id")
    outcome = parse_proposal_response(json.dumps(proposal), "obj-health-check")
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID


def test_parse_proposal_response_rejects_objective_mismatch():
    outcome = parse_proposal_response(
        json.dumps(_valid_proposal(objective_id="obj-untrusted")),
        "obj-health-check",
    )
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID
    assert "objective_id" in (outcome.error_reason or "")


def test_parse_proposal_response_rejects_additional_property():
    outcome = parse_proposal_response(
        json.dumps(_valid_proposal(path="http://untrusted.invalid/")),
        "obj-health-check",
    )
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID


def test_parse_proposal_response_rejects_markdown_fences():
    valid_json = json.dumps(_valid_proposal())
    fenced_text = f"```json\n{valid_json}\n```"
    outcome = parse_proposal_response(fenced_text, "obj-health-check")
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID
    assert "JSON" in (outcome.error_reason or "")


def test_parse_proposal_response_rejects_surrounding_commentary():
    valid_json = json.dumps(_valid_proposal())
    commented = f"Here is your proposal:\n{valid_json}\nThank you!"
    outcome = parse_proposal_response(commented, "obj-health-check")
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID


def test_parse_proposal_response_declined():
    declined = {
        "objective_id": "obj-unmapped-finding",
        "proposal_id": "prop-declined",
        "endpoint_id": None,
        "reason": "No reviewed endpoint applies",
        "method": None,
        "template_id": None,
        "payload_type": None,
        "headers": None,
        "parameters": None,
    }
    outcome = parse_proposal_response(json.dumps(declined), "obj-unmapped-finding")
    assert outcome.status is ProposalOutcomeStatus.PROPOSED
    assert outcome.proposal == declined


def test_parse_proposal_response_rejects_decline_missing_null_fields():
    incomplete_decline = {
        "objective_id": "obj-unmapped-finding",
        "proposal_id": "prop-declined",
        "endpoint_id": None,
        "reason": "No reviewed endpoint applies",
    }
    outcome = parse_proposal_response(json.dumps(incomplete_decline), "obj-unmapped-finding")
    assert outcome.status is ProposalOutcomeStatus.PROPOSAL_INVALID


@pytest.mark.llm
def test_generate_probe_proposal_with_real_openrouter(sample_catalog, sample_objective):
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        pytest.fail("LLM_API_KEY is required for the live proposer test")
    client = OpenRouterClient(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash-0731"),
        timeout_seconds=30.0,
        max_retries=1,
    )
    outcome = generate_probe_proposal(client, sample_catalog, sample_objective)
    assert outcome.is_valid, outcome.error_reason
    assert outcome.proposal is not None
    endpoint_id = outcome.proposal["endpoint_id"]
    catalogued_ids = {endpoint["endpoint_id"] for endpoint in sample_catalog["endpoints"]}
    assert endpoint_id is None or endpoint_id in catalogued_ids
