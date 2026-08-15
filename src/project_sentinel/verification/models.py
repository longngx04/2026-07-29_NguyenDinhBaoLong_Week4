"""
Data models for verification candidates, HTTP transport abstractions, policy decisions, and execution results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class VerificationStatus(str, Enum):
    REACHABLE = "REACHABLE"
    OBSERVED = "OBSERVED"
    UNREACHABLE = "UNREACHABLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    DENIED = "DENIED"
    RATE_LIMITED = "RATE_LIMITED"


class VerificationDecision(str, Enum):
    PLANNED = "PLANNED"
    NOT_PLANNABLE = "NOT_PLANNABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class HttpRequest:
    """HTTP Request abstraction for transport execution."""
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)


@dataclass
class HttpResponse:
    """HTTP Response abstraction with 64 KiB truncation and error metadata."""
    status_code: Optional[int]
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    response_bytes_observed: int = 0
    truncated: bool = False
    elapsed_ms: float = 0.0
    error_class: Optional[str] = None
    error_reason: Optional[str] = None


@dataclass
class VerificationCandidate:
    """Structured verification candidate targeting an explicit inventory endpoint & template."""
    candidate_id: str
    objective_id: str
    proposal_id: str
    decision: Union[VerificationDecision, str] = VerificationDecision.NOT_PLANNABLE
    endpoint_id: Optional[str] = None
    template_id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    target_field: Optional[str] = None
    payload_type: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        decision_val = (
            self.decision.value
            if isinstance(self.decision, Enum)
            else str(self.decision)
        )
        data: Dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "objective_id": self.objective_id,
            "proposal_id": self.proposal_id,
            "decision": decision_val,
        }
        if decision_val == VerificationDecision.PLANNED.value:
            for key in ("endpoint_id", "template_id", "method", "path"):
                value = getattr(self, key)
                if value is not None:
                    data[key] = value
            if self.target_field is not None:
                data["target_field"] = self.target_field
            if self.payload_type is not None:
                data["payload_type"] = self.payload_type
            if self.headers is not None:
                data["headers"] = self.headers
            if self.reason is not None:
                data["reason"] = self.reason
        else:
            data["reason"] = self.reason if self.reason is not None else "No reason provided"
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationCandidate":
        decision_raw = data.get("decision", "NOT_PLANNABLE")
        try:
            decision_val: Union[VerificationDecision, str] = VerificationDecision(decision_raw)
        except ValueError:
            decision_val = str(decision_raw)

        return cls(
            candidate_id=str(data.get("candidate_id", "")),
            objective_id=str(data.get("objective_id", "")),
            proposal_id=str(data.get("proposal_id", "")),
            decision=decision_val,
            endpoint_id=data.get("endpoint_id"),
            template_id=data.get("template_id"),
            method=data.get("method"),
            path=data.get("path"),
            target_field=data.get("target_field"),
            payload_type=data.get("payload_type"),
            headers=data.get("headers"),
            reason=data.get("reason"),
        )


# Backward compatibility alias for VerificationPlan
VerificationPlan = VerificationCandidate


@dataclass
class VerificationResult:
    """Structured execution result of a verification candidate."""
    result_id: str
    plan_id: str
    status: Union[VerificationStatus, str]
    status_code: Optional[int] = None
    evidence: str = ""
    execution_time_ms: float = 0.0
    response_bytes_observed: int = 0
    truncated: bool = False
    response_preview: Optional[str] = None
    error_class: Optional[str] = None
    error_reason: Optional[str] = None

    @property
    def candidate_id(self) -> str:
        return self.plan_id

    def to_dict(self) -> Dict[str, Any]:
        status_val = (
            self.status.value
            if isinstance(self.status, Enum)
            else str(self.status)
        )
        return {
            "result_id": self.result_id,
            "plan_id": self.plan_id,
            "status": status_val,
            "status_code": self.status_code,
            "evidence": self.evidence,
            "execution_time_ms": self.execution_time_ms,
            "response_bytes_observed": self.response_bytes_observed,
            "truncated": self.truncated,
            "response_preview": self.response_preview,
            "error_class": self.error_class,
            "error_reason": self.error_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        status_raw = data.get("status", "FAILED")
        try:
            status_val: Union[VerificationStatus, str] = VerificationStatus(status_raw)
        except ValueError:
            status_val = str(status_raw)

        plan_id = str(data.get("plan_id", data.get("candidate_id", "")))

        return cls(
            result_id=str(data.get("result_id", "")),
            plan_id=plan_id,
            status=status_val,
            status_code=data.get("status_code"),
            evidence=str(data.get("evidence", "")),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            response_bytes_observed=int(data.get("response_bytes_observed", 0)),
            truncated=bool(data.get("truncated", False)),
            response_preview=data.get("response_preview"),
            error_class=data.get("error_class"),
            error_reason=data.get("error_reason"),
        )
