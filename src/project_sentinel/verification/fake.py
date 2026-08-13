"""
Offline FakeProber implementation for deterministic offline testing.
"""

from typing import Dict, Optional
from project_sentinel.verification.models import (
    VerificationCandidate,
    VerificationResult,
    VerificationStatus,
)


class FakeProber:
    """
    Deterministic offline prober returning fixture-driven VerificationResult objects without network calls.
    """

    def __init__(
        self,
        default_status: VerificationStatus = VerificationStatus.VERIFIED_REACHABLE,
        responses: Optional[Dict[str, VerificationResult]] = None,
    ):
        self.default_status = default_status
        self.responses = responses or {}

    def execute_plan(self, plan: VerificationCandidate) -> VerificationResult:
        plan_id = getattr(plan, "plan_id", getattr(plan, "candidate_id", "cand-unknown"))
        if plan_id in self.responses:
            return self.responses[plan_id]
        if plan.group_id in self.responses:
            return self.responses[plan.group_id]

        status = self.default_status
        status_code = 200 if status in (VerificationStatus.VERIFIED_REACHABLE, VerificationStatus.REACHABLE) else None
        path_str = getattr(plan, "path", getattr(plan, "target_url", ""))
        evidence = f"Offline FakeProber simulated reachable endpoint for candidate {plan_id} (path: {path_str})"

        return VerificationResult(
            result_id=f"res-{plan_id}",
            plan_id=plan_id,
            group_id=plan.group_id,
            status=status,
            status_code=status_code,
            evidence=evidence,
            execution_time_ms=0.5,
            response_bytes_observed=15,
            truncated=False,
            error_class=None,
            error_reason=None,
        )
