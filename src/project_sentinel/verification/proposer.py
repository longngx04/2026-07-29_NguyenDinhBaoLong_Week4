"""Strict external-LLM probe proposal generation for Week 4."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import jsonschema

from project_sentinel.llm import LLMProvider, LLMResult
from project_sentinel.verification.validators import validate_probe_proposal_schema

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SYSTEM_PROMPT_PATH = _REPO_ROOT / "configs" / "prompts" / "probe-proposal-system.md"


class ProposalOutcomeStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PROPOSAL_INVALID = "PROPOSAL_INVALID"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True)
class ProbeProposalOutcome:
    """A valid proposal or a structured non-executable model-output failure."""

    status: ProposalOutcomeStatus
    objective_id: str
    proposal: dict[str, Any] | None = None
    error_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status is ProposalOutcomeStatus.PROPOSED and self.proposal is not None


def _invalid_outcome(objective_id: str, reason: str) -> ProbeProposalOutcome:
    return ProbeProposalOutcome(
        status=ProposalOutcomeStatus.PROPOSAL_INVALID,
        objective_id=objective_id,
        error_reason=reason,
    )


def render_proposer_prompt(
    catalog: dict[str, Any],
    objective: dict[str, Any],
    system_prompt_path: Optional[str | Path] = None,
) -> tuple[str, str]:
    """Render the reviewed objective and endpoint catalog for the proposer."""
    prompt_path = Path(system_prompt_path) if system_prompt_path else DEFAULT_SYSTEM_PROMPT_PATH
    system_prompt = prompt_path.read_text(encoding="utf-8")

    if not isinstance(objective, dict):
        raise ValueError("Probe objective must be a JSON object")
    objective_id = objective.get("objective_id")
    description = objective.get("description")
    finding_context = objective.get("finding_context")
    if not all(isinstance(value, str) and value for value in (objective_id, description, finding_context)):
        raise ValueError("Probe objective requires non-empty objective_id, description, and finding_context")
    if not isinstance(catalog, dict):
        raise ValueError("Endpoint catalog must be a JSON object")
    endpoints = catalog.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("Endpoint catalog requires a non-empty endpoints list")

    catalog_json = json.dumps(catalog, indent=2, ensure_ascii=False)
    user_prompt = (
        "Operator Objective:\n"
        f"- Objective ID: {objective_id}\n"
        f"- Description: {description}\n"
        f"- Context: {finding_context}\n\n"
        "Target Endpoint Catalog:\n"
        f"{catalog_json}\n\n"
        "Evaluate the objective against the catalog. Return ONLY a single raw JSON object "
        "matching probe-proposal.schema.json."
    )
    return system_prompt, user_prompt


def parse_proposal_response(raw_text: str, objective_id: str) -> ProbeProposalOutcome:
    """Strictly parse and validate an untrusted model response without repairing or extracting from fences."""
    if not isinstance(raw_text, str):
        return _invalid_outcome(objective_id, "LLM response is not text")
    text = raw_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _invalid_outcome(objective_id, f"Failed to parse LLM JSON response: {exc}")
    return _validate_proposal_data(data, objective_id)


def _validate_proposal_data(data: Any, objective_id: str) -> ProbeProposalOutcome:
    """Validate already-parsed provider output as an untrusted proposal."""
    if not isinstance(data, dict):
        return _invalid_outcome(objective_id, "LLM response root is not a JSON object")

    try:
        validate_probe_proposal_schema(data)
    except jsonschema.ValidationError as exc:
        return _invalid_outcome(objective_id, f"Proposal schema validation failed: {exc.message}")

    if data.get("objective_id") != objective_id:
        return _invalid_outcome(objective_id, "Proposal objective_id does not match the selected objective")

    return ProbeProposalOutcome(
        status=ProposalOutcomeStatus.PROPOSED,
        objective_id=objective_id,
        proposal=data,
    )


def _proposal_outcome_from_result(
    llm_result: LLMResult,
    objective_id: str,
) -> ProbeProposalOutcome:
    """Convert a provider result without reparsing its raw audit response."""
    if llm_result.error:
        return ProbeProposalOutcome(
            status=ProposalOutcomeStatus.PROVIDER_FAILURE,
            objective_id=objective_id,
            error_reason=f"LLM provider failed: {llm_result.error}",
        )
    return _validate_proposal_data(llm_result.parsed_response, objective_id)


def generate_probe_proposal(
    llm: LLMProvider,
    catalog: dict[str, Any],
    objective: dict[str, Any],
    system_prompt_path: Optional[str | Path] = None,
) -> ProbeProposalOutcome:
    """Call the real provider and return a schema-validated proposal outcome."""
    system_prompt, user_prompt = render_proposer_prompt(catalog, objective, system_prompt_path)
    objective_id = objective["objective_id"]
    llm_result = llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    return _proposal_outcome_from_result(llm_result, objective_id)
