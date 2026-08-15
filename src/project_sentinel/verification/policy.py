"""Deny-by-default validation of the fully resolved candidate tuple."""

from typing import Optional, Tuple

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.templates import ProbeTemplateRegistry

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
    "x-forwarded-host",
    "x-forwarded-for",
    "x-forwarded-proto",
}


def validate_candidate_policy(
    candidate: VerificationCandidate,
    allowlist: Allowlist,
    templates: ProbeTemplateRegistry,
) -> Tuple[bool, Optional[str]]:
    decision = candidate.decision.value if hasattr(candidate.decision, "value") else str(candidate.decision)
    if decision != VerificationDecision.PLANNED.value:
        return False, f"Candidate not marked PLANNED (decision={decision})"

    if not candidate.template_id:
        return False, "Missing template_id"
    template = templates.get(candidate.template_id)
    if template is None:
        return False, f"template_id '{candidate.template_id}' not in reviewed registry"

    rule = allowlist.get_rule(candidate.endpoint_id or "", candidate.method or "")
    if rule is None:
        return False, f"Unknown endpoint/method tuple: {candidate.endpoint_id}/{candidate.method}"

    resolved = (
        candidate.endpoint_id,
        candidate.method,
        candidate.path,
        candidate.target_field,
        candidate.payload_type,
    )
    expected = (
        template.endpoint_id,
        template.method,
        rule.path,
        template.target_field,
        template.payload_type,
    )
    if resolved != expected:
        return False, "Candidate fields do not exactly match the reviewed template"

    if candidate.headers:
        if not isinstance(candidate.headers, dict):
            return False, "Candidate headers must be a dictionary"
        allowed_map = rule.allowed_request_headers
        for header_name, header_value in candidate.headers.items():
            if not isinstance(header_name, str) or not isinstance(header_value, str):
                return False, f"Invalid non-string header pair: {header_name}={header_value}"
            if "\r" in header_name or "\n" in header_name or "\r" in header_value or "\n" in header_value:
                return False, f"Header name or value contains newline character: {header_name}"
            h_folded = header_name.casefold()
            if h_folded in RESTRICTED_HEADERS:
                return False, f"Restricted header '{header_name}' cannot be specified in candidate"
            if h_folded not in allowed_map:
                return False, f"Header '{header_name}' is not in reviewed allowed_request_headers for endpoint '{candidate.endpoint_id}'"
            if header_value not in allowed_map[h_folded]:
                return False, f"Header value '{header_value}' for header '{header_name}' is not in reviewed allowed values"

    if not allowlist.is_allowed(
        candidate.method or "",
        candidate.path or "",
        endpoint_id=candidate.endpoint_id,
        template_id=candidate.template_id,
    ):
        return False, "Candidate denied by endpoint allowlist"
    return True, None
