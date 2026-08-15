"""Deny-by-default validation of the fully resolved candidate tuple."""

from typing import Optional, Tuple

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.templates import ProbeTemplateRegistry


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
    if not allowlist.is_allowed(
        candidate.method or "",
        candidate.path or "",
        endpoint_id=candidate.endpoint_id,
        template_id=candidate.template_id,
    ):
        return False, "Candidate denied by endpoint allowlist"
    return True, None
