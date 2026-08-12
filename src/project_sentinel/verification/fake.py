"""
Offline FakeProber implementation for deterministic offline testing.
"""

from typing import Dict, Optional
from project_sentinel.verification.models import (
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.prober import BaseProber


class FakeProber(BaseProber):
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

    def execute_plan(self, plan: VerificationPlan) -> VerificationResult:
        if plan.plan_id in self.responses:
            return self.responses[plan.plan_id]
        if plan.group_id in self.responses:
            return self.responses[plan.group_id]

        status = self.default_status
        status_code = 200 if status == VerificationStatus.VERIFIED_REACHABLE else None
        evidence = f"Offline FakeProber simulated reachable endpoint for plan {plan.plan_id} (target: {plan.target_url})"

        return VerificationResult(
            result_id=f"res-{plan.plan_id}",
            plan_id=plan.plan_id,
            group_id=plan.group_id,
            status=status,
            status_code=status_code,
            evidence=evidence,
            execution_time_ms=0.5,
        )
