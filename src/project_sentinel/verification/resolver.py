"""Deny-by-default IAM resolution for untrusted Week 4 probe proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import jsonschema

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.validators import (
    validate_probe_proposal_schema,
    validate_verification_plan_schema,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = _REPO_ROOT / "configs" / "verification" / "endpoint-catalog.json"
DEFAULT_OBJECTIVES_PATH = _REPO_ROOT / "configs" / "verification" / "probe-objectives.json"

RESTRICTED_HEADERS = {
    "host",
    "authorization",
    "x-sentinel-api-key",
    "cookie",
    "proxy-authorization",
    "connection",
    "upgrade",
    "keep-alive",
    "proxy-authenticate",
    "trailer",
    "transfer-encoding",
}

_PROPOSAL_PAYLOAD_BY_TEMPLATE_PAYLOAD = {
    None: None,
    "empty_value": "EMPTY",
    "long_string": "BOUNDED_LONG_STRING",
    "wrong_type": "WRONG_PRIMITIVE",
    "special_chars": "SPECIAL_CHARS",
}


@dataclass(frozen=True)
class ResolutionDenial:
    """A non-executable IAM decision that cannot be passed to the request executor."""

    reason_code: str
    reason: str
    objective_id: str | None = None
    proposal_id: str | None = None
    decision: VerificationDecision = VerificationDecision.NOT_PLANNABLE

    @property
    def candidate_id(self) -> str:
        return f"denial-{self.reason_code.lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "objective_id": self.objective_id or "unknown-objective",
            "proposal_id": self.proposal_id or "unknown-proposal",
            "decision": self.decision.value,
            "reason": f"{self.reason_code}: {self.reason}",
        }


ResolutionOutcome = VerificationCandidate | ResolutionDenial


def _deny(
    reason_code: str,
    reason: str,
    proposal: dict[str, Any],
) -> ResolutionDenial:
    objective_id = proposal.get("objective_id") if isinstance(proposal, dict) else None
    proposal_id = proposal.get("proposal_id") if isinstance(proposal, dict) else None
    return ResolutionDenial(
        reason_code=reason_code,
        reason=reason,
        objective_id=objective_id if isinstance(objective_id, str) and objective_id else None,
        proposal_id=proposal_id if isinstance(proposal_id, str) and proposal_id else None,
    )


def load_endpoint_catalog(catalog_path: Optional[str | Path] = None) -> dict[str, Any]:
    """Load and strictly validate the reviewed endpoint catalog."""
    path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Endpoint catalog root must be a JSON object")
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("Endpoint catalog requires a non-empty endpoints list")

    seen_ids = set()
    valid_methods = {"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"}
    for idx, ep in enumerate(endpoints):
        if not isinstance(ep, dict):
            raise ValueError(f"Endpoint entry #{idx} must be a JSON object")
        ep_id = ep.get("endpoint_id")
        if not isinstance(ep_id, str) or not ep_id:
            raise ValueError(f"Endpoint entry #{idx} missing valid endpoint_id")
        if ep_id in seen_ids:
            raise ValueError(f"Duplicate endpoint_id '{ep_id}' in catalog")
        seen_ids.add(ep_id)

        path_val = ep.get("path")
        if not isinstance(path_val, str) or not path_val.startswith("/"):
            raise ValueError(f"Endpoint '{ep_id}' has invalid path: {path_val}")

        allowed_methods = ep.get("allowed_methods")
        if not isinstance(allowed_methods, list) or not allowed_methods:
            raise ValueError(f"Endpoint '{ep_id}' has invalid allowed_methods")
        for m in allowed_methods:
            if not isinstance(m, str) or m not in valid_methods:
                raise ValueError(f"Endpoint '{ep_id}' contains invalid method: {m}")

        allowed_templates = ep.get("allowed_template_ids")
        if not isinstance(allowed_templates, list) or not allowed_templates:
            raise ValueError(f"Endpoint '{ep_id}' has invalid allowed_template_ids")
        for t in allowed_templates:
            if not isinstance(t, str) or not t:
                raise ValueError(f"Endpoint '{ep_id}' contains invalid template_id: {t}")

        headers_policy = ep.get("allowed_request_headers")
        if headers_policy is not None:
            if not isinstance(headers_policy, dict):
                raise ValueError(f"Endpoint '{ep_id}' allowed_request_headers must be a dict")
            for h_name, h_vals in headers_policy.items():
                if not isinstance(h_name, str) or not isinstance(h_vals, list):
                    raise ValueError(f"Endpoint '{ep_id}' header '{h_name}' has invalid allowed values list")
                for v in h_vals:
                    if not isinstance(v, str):
                        raise ValueError(f"Endpoint '{ep_id}' header '{h_name}' value must be a string: {v}")

    return data


def load_probe_objectives(objectives_path: Optional[str | Path] = None) -> list[dict[str, Any]]:
    """Load reviewed operator objectives and reject malformed configuration."""
    path = Path(objectives_path) if objectives_path else DEFAULT_OBJECTIVES_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    objectives = data.get("objectives") if isinstance(data, dict) else None
    if not isinstance(objectives, list) or not objectives:
        raise ValueError("Probe objectives require a non-empty objectives list")
    for objective in objectives:
        if not isinstance(objective, dict) or not all(
            isinstance(objective.get(field), str) and objective[field]
            for field in ("objective_id", "description", "finding_context")
        ):
            raise ValueError("Each probe objective requires objective_id, description, and finding_context")
    return objectives


def resolve_proposal(
    proposal: dict[str, Any],
    catalog: dict[str, Any],
    allowlist: Allowlist,
    templates: ProbeTemplateRegistry,
) -> ResolutionOutcome:
    """Resolve every executable field from reviewed configuration or return a typed denial."""
    if not isinstance(proposal, dict):
        return ResolutionDenial("PROPOSAL_SCHEMA_INVALID", "Proposal must be a JSON object")
    try:
        validate_probe_proposal_schema(proposal)
    except jsonschema.ValidationError as exc:
        return _deny(
            "PROPOSAL_SCHEMA_INVALID",
            f"Proposal failed schema validation ({exc.validator})",
            proposal,
        )

    objective_id = proposal["objective_id"]
    proposal_id = proposal["proposal_id"]
    endpoint_id = proposal["endpoint_id"]
    if endpoint_id is None:
        candidate = VerificationCandidate(
            candidate_id=f"cand-{uuid4().hex[:8]}",
            objective_id=objective_id,
            proposal_id=proposal_id,
            decision=VerificationDecision.NOT_APPLICABLE,
            reason=proposal["reason"],
        )
        validate_verification_plan_schema(candidate.to_dict())
        return candidate

    endpoints = catalog.get("endpoints") if isinstance(catalog, dict) else None
    if not isinstance(endpoints, list):
        return _deny("CATALOG_INVALID", "Endpoint catalog is malformed", proposal)
    matched_endpoint = next(
        (
            endpoint
            for endpoint in endpoints
            if isinstance(endpoint, dict) and endpoint.get("endpoint_id") == endpoint_id
        ),
        None,
    )
    if matched_endpoint is None:
        return _deny("ENDPOINT_NOT_CATALOGUED", "Endpoint is not in the reviewed catalog", proposal)

    method = proposal["method"]
    if method not in matched_endpoint.get("allowed_methods", []):
        return _deny("METHOD_NOT_ALLOWED", "Method is not allowed for the catalog endpoint", proposal)

    template_id = proposal["template_id"]
    if template_id not in matched_endpoint.get("allowed_template_ids", []):
        return _deny("TEMPLATE_NOT_ALLOWED", "Template is not allowed for the catalog endpoint", proposal)
    template = templates.get(template_id)
    if template is None:
        return _deny("TEMPLATE_NOT_FOUND", "Template is not in the reviewed registry", proposal)
    if template.endpoint_id != endpoint_id or template.method != method:
        return _deny("TEMPLATE_TUPLE_MISMATCH", "Template does not match endpoint and method", proposal)

    expected_proposal_payload = _PROPOSAL_PAYLOAD_BY_TEMPLATE_PAYLOAD.get(template.payload_type)
    if template.payload_type not in _PROPOSAL_PAYLOAD_BY_TEMPLATE_PAYLOAD:
        return _deny("TEMPLATE_PAYLOAD_UNSUPPORTED", "Template payload type is unsupported", proposal)
    if proposal["payload_type"] != expected_proposal_payload:
        return _deny("PAYLOAD_TYPE_MISMATCH", "Payload type does not match the reviewed template", proposal)

    parameters = proposal.get("parameters")
    if parameters not in (None, {}):
        return _deny("PARAMETERS_NOT_ALLOWED", "Literal proposal parameters are not allowed", proposal)

    headers = proposal.get("headers") or {}
    allowed_headers = matched_endpoint.get("allowed_request_headers", {})
    if not isinstance(allowed_headers, dict):
        return _deny("CATALOG_INVALID", "Catalog header policy is malformed", proposal)
    for header_name, header_value in headers.items():
        if header_name.casefold() in RESTRICTED_HEADERS:
            return _deny("RESTRICTED_HEADER", "A restricted header was proposed", proposal)
        allowed_values = allowed_headers.get(header_name)
        if not isinstance(allowed_values, list):
            return _deny("HEADER_NOT_ALLOWED", "Header name is not in the reviewed catalog", proposal)
        if header_value not in allowed_values:
            return _deny("HEADER_VALUE_NOT_ALLOWED", "Header value is not in the reviewed catalog", proposal)

    path = matched_endpoint.get("path")
    if not isinstance(path, str) or not allowlist.is_allowed(
        method,
        path,
        endpoint_id=endpoint_id,
        template_id=template_id,
    ):
        return _deny("GATEWAY_ALLOWLIST_DENIAL", "Candidate is denied by the Gateway allowlist", proposal)

    candidate = VerificationCandidate(
        candidate_id=f"cand-{uuid4().hex[:8]}",
        objective_id=objective_id,
        proposal_id=proposal_id,
        decision=VerificationDecision.PLANNED,
        endpoint_id=endpoint_id,
        template_id=template_id,
        method=method,
        path=path,
        target_field=template.target_field,
        payload_type=template.payload_type,
        headers=headers if headers else None,
        reason="Resolved exactly from the reviewed endpoint catalog and probe template",
    )
    validate_verification_plan_schema(candidate.to_dict())
    return candidate
