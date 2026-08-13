"""
Policy validator enforcing deny-by-default checks on verification candidates.
"""

from typing import Optional, Tuple
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision

KNOWN_ENDPOINT_IDS = {"ep_health", "ep_attack"}
KNOWN_TEMPLATE_IDS = {"tmpl_health_get", "tmpl_attack_get", "tmpl_attack_post"}


def validate_candidate_policy(
    candidate: VerificationCandidate,
    allowlist: Allowlist
) -> Tuple[bool, Optional[str]]:
    """Validate verification candidate against strict deny-by-default policy rules.
    
    Returns (True, None) if candidate is allowed, or (False, failure_reason) if denied.
    """
    decision_str = (
        candidate.decision.value
        if hasattr(candidate.decision, "value")
        else str(candidate.decision)
    )

    if decision_str != VerificationDecision.PLANNED.value:
        return False, f"Candidate not marked PLANNED (decision={decision_str})"

    if not candidate.endpoint_id or candidate.endpoint_id == "ep_unknown":
        return False, f"Unknown or invalid endpoint_id: {candidate.endpoint_id}"

    if not candidate.template_id or candidate.template_id == "tmpl_none":
        return False, f"Unknown or invalid template_id: {candidate.template_id}"

    if candidate.endpoint_id not in KNOWN_ENDPOINT_IDS:
        return False, f"endpoint_id '{candidate.endpoint_id}' not in allowed inventory"

    if candidate.template_id not in KNOWN_TEMPLATE_IDS:
        return False, f"template_id '{candidate.template_id}' not in allowed template registry"

    if not allowlist.is_allowed(candidate.method, candidate.path):
        return False, f"Method '{candidate.method}' and path '{candidate.path}' denied by allowlist"

    return True, None
