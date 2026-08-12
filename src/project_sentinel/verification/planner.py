"""
Deterministic Verification Candidate Planner for Project Sentinel.
Converts analyzed finding records into safe, non-destructive probe plans.
"""

import hashlib
from typing import List
from project_sentinel.models import SecurityAnalysisRecord
from project_sentinel.verification.models import VerificationPlan, VerificationProbe

DEFAULT_TARGET_BASE = "http://127.0.0.1:8080/WebGoat"


def _generate_plan_id(group_key: str, cwe: str) -> str:
    seed = f"plan-{group_key}-{cwe}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"plan-{digest}"


def build_verification_plan(
    record: SecurityAnalysisRecord,
    target_base_url: str = DEFAULT_TARGET_BASE
) -> VerificationPlan:
    """
    Build a deterministic VerificationPlan from a single SecurityAnalysisRecord.
    """
    if not target_base_url.startswith("http://127.0.0.1:8080/") and not target_base_url.startswith("http://localhost:8080/"):
        target_base_url = DEFAULT_TARGET_BASE

    target_base = target_base_url.rstrip("/")
    cwe_str = record.cwe[0] if record.cwe else "CWE-UNKNOWN"
    group_id = record.analysis_id or record.group_key or "group-unknown"
    plan_id = _generate_plan_id(group_id, cwe_str)

    probe_path = "/start.mvc"
    if record.locations:
        loc_path = record.locations[0].file.lower()
        if "session" in loc_path:
            probe_path = "/session/status"
        elif "sqli" in loc_path or "sql" in loc_path or cwe_str == "CWE-89":
            probe_path = "/SqlInjection/attack"
        elif "deserialization" in loc_path or cwe_str == "CWE-502":
            probe_path = "/deserialization/status"
        elif "command" in loc_path or cwe_str == "CWE-78":
            probe_path = "/commandexec/status"

    probe = VerificationProbe(
        probe_id=f"probe-1-{group_id[:8]}",
        method="GET",
        path=probe_path,
        headers={"User-Agent": "ProjectSentinel-SafeProbe/1.0", "Accept": "application/json, text/html"},
        params={"inspect": "reachability"},
        expected_status=200,
        expected_indicator="WebGoat"
    )

    return VerificationPlan(
        plan_id=plan_id,
        analysis_record_id=record.analysis_id,
        group_id=group_id,
        cwe=cwe_str,
        target_url=f"{target_base}{probe_path}",
        probes=[probe]
    )


def build_verification_plans(
    records: List[SecurityAnalysisRecord],
    target_base_url: str = DEFAULT_TARGET_BASE
) -> List[VerificationPlan]:
    """
    Build deterministic VerificationPlan objects for a list of SecurityAnalysisRecords.
    """
    return [build_verification_plan(record, target_base_url=target_base_url) for record in records]
