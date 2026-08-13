"""
Deterministic Verification Candidate Planner for Project Sentinel.
Maps analyzed finding records to explicit inventory endpoints & templates.
Never invents endpoint paths.
"""

import hashlib
from typing import Dict, List, Optional, Tuple, Any

from project_sentinel.models import SecurityAnalysisRecord
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision

# Static Endpoint & Template Inventory
ENDPOINT_INVENTORY: Dict[str, Dict[str, Any]] = {
    "ep_health": {
        "endpoint_id": "ep_health",
        "path": "/WebGoat/actuator/health",
        "allowed_methods": ["GET"],
        "default_template": "tmpl_health_get",
    },
    "ep_attack": {
        "endpoint_id": "ep_attack",
        "path": "/WebGoat/attack",
        "allowed_methods": ["GET", "POST"],
        "default_template": "tmpl_attack_get",
    },
}

TEMPLATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "tmpl_health_get": {
        "template_id": "tmpl_health_get",
        "endpoint_id": "ep_health",
        "method": "GET",
        "target_field": None,
        "payload_type": None,
    },
    "tmpl_attack_get": {
        "template_id": "tmpl_attack_get",
        "endpoint_id": "ep_attack",
        "method": "GET",
        "target_field": None,
        "payload_type": None,
    },
    "tmpl_attack_post": {
        "template_id": "tmpl_attack_post",
        "endpoint_id": "ep_attack",
        "method": "POST",
        "target_field": "input",
        "payload_type": "special_chars",
    },
}


def _generate_candidate_id(group_key: str, cwe: str) -> str:
    seed = f"candidate-{group_key}-{cwe}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"plan-{digest}"


def map_finding_to_inventory(record: SecurityAnalysisRecord) -> Tuple[VerificationDecision, str, str, Optional[str]]:
    """Map finding location & CWE to inventory endpoint_id and template_id.
    
    Returns (decision, endpoint_id, template_id, reason).
    """
    cwe_str = record.cwe[0] if record.cwe else "CWE-UNKNOWN"
    
    # 1. Healthcheck mappings for general reachability
    if not record.locations:
        return (
            VerificationDecision.PLANNED,
            "ep_health",
            "tmpl_health_get",
            "General healthcheck probe planned for record without specific location",
        )

    loc_path = record.locations[0].file.lower()

    # 2. Check for supported attack lesson paths or CWEs
    if "attack" in loc_path or "sqli" in loc_path or cwe_str in ("CWE-89", "CWE-79", "CWE-502"):
        return (
            VerificationDecision.PLANNED,
            "ep_attack",
            "tmpl_attack_post" if cwe_str == "CWE-89" else "tmpl_attack_get",
            f"Mapped {cwe_str} at {record.locations[0].file} to endpoint ep_attack",
        )

    # 3. Default to healthcheck for other known locations
    return (
        VerificationDecision.PLANNED,
        "ep_health",
        "tmpl_health_get",
        f"Mapped {cwe_str} at {record.locations[0].file} to endpoint ep_health",
    )


def build_verification_plan(
    record: SecurityAnalysisRecord,
    target_base_url: Optional[str] = None
) -> VerificationCandidate:
    """Build a deterministic VerificationCandidate from a single SecurityAnalysisRecord."""
    cwe_str = record.cwe[0] if record.cwe else "CWE-UNKNOWN"
    group_id = record.analysis_id or record.group_key or "group-unknown"
    candidate_id = _generate_candidate_id(group_id, cwe_str)

    decision, ep_id, tmpl_id, reason = map_finding_to_inventory(record)
    
    ep_info = ENDPOINT_INVENTORY.get(ep_id, ENDPOINT_INVENTORY["ep_health"])
    tmpl_info = TEMPLATE_REGISTRY.get(tmpl_id, TEMPLATE_REGISTRY["tmpl_health_get"])

    return VerificationCandidate(
        candidate_id=candidate_id,
        analysis_record_id=record.analysis_id,
        group_id=group_id,
        cwe=cwe_str,
        decision=decision,
        endpoint_id=ep_id,
        template_id=tmpl_id,
        method=tmpl_info["method"],
        path=ep_info["path"],
        target_field=tmpl_info.get("target_field"),
        payload_type=tmpl_info.get("payload_type"),
        reason=reason,
    )


def build_verification_plans(
    records: List[SecurityAnalysisRecord],
    target_base_url: Optional[str] = None
) -> List[VerificationCandidate]:
    """Build deterministic VerificationCandidate objects for a list of SecurityAnalysisRecords."""
    return [build_verification_plan(record, target_base_url=target_base_url) for record in records]
