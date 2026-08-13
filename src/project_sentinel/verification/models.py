"""
Data models for verification candidates, HTTP transport abstractions, policy decisions, and execution results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class VerificationStatus(str, Enum):
    VERIFIED_REACHABLE = "VERIFIED_REACHABLE"
    REACHABLE = "REACHABLE"
    OBSERVED = "OBSERVED"
    UNREACHABLE = "UNREACHABLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    DENIED = "DENIED"


class VerificationDecision(str, Enum):
    PLANNED = "PLANNED"
    NOT_PLANNABLE = "NOT_PLANNABLE"


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
    analysis_record_id: str
    group_id: str
    cwe: str
    decision: Union[VerificationDecision, str] = VerificationDecision.PLANNED
    endpoint_id: str = "ep_health"
    template_id: str = "tmpl_health_get"
    method: str = "GET"
    path: str = "/WebGoat/actuator/health"
    target_field: Optional[str] = None
    payload_type: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        decision_val = (
            self.decision.value
            if isinstance(self.decision, Enum)
            else str(self.decision)
        )
        data: Dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "analysis_record_id": self.analysis_record_id,
            "group_id": self.group_id,
            "cwe": self.cwe,
            "decision": decision_val,
            "endpoint_id": self.endpoint_id,
            "template_id": self.template_id,
            "method": self.method,
            "path": self.path,
        }
        if self.target_field is not None:
            data["target_field"] = self.target_field
        if self.payload_type is not None:
            data["payload_type"] = self.payload_type
        if self.reason is not None:
            data["reason"] = self.reason
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationCandidate":
        decision_raw = data.get("decision", "PLANNED")
        try:
            decision_val: Union[VerificationDecision, str] = VerificationDecision(decision_raw)
        except ValueError:
            decision_val = str(decision_raw)

        return cls(
            candidate_id=str(data.get("candidate_id", "")),
            analysis_record_id=str(data.get("analysis_record_id", "")),
            group_id=str(data.get("group_id", "")),
            cwe=str(data.get("cwe", "")),
            decision=decision_val,
            endpoint_id=str(data.get("endpoint_id", "ep_health")),
            template_id=str(data.get("template_id", "tmpl_health_get")),
            method=str(data.get("method", "GET")),
            path=str(data.get("path", "/WebGoat/actuator/health")),
            target_field=data.get("target_field"),
            payload_type=data.get("payload_type"),
            reason=data.get("reason"),
        )


# Backward compatibility alias for VerificationPlan
VerificationPlan = VerificationCandidate


@dataclass
class VerificationResult:
    """Structured execution result of a verification candidate."""
    result_id: str
    plan_id: str
    group_id: str
    status: Union[VerificationStatus, str]
    status_code: Optional[int] = None
    evidence: str = ""
    execution_time_ms: float = 0.0
    response_bytes_observed: int = 0
    truncated: bool = False
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
            "group_id": self.group_id,
            "status": status_val,
            "status_code": self.status_code,
            "evidence": self.evidence,
            "execution_time_ms": self.execution_time_ms,
            "response_bytes_observed": self.response_bytes_observed,
            "truncated": self.truncated,
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
            group_id=str(data.get("group_id", "")),
            status=status_val,
            status_code=data.get("status_code"),
            evidence=str(data.get("evidence", "")),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            response_bytes_observed=int(data.get("response_bytes_observed", 0)),
            truncated=bool(data.get("truncated", False)),
            error_class=data.get("error_class"),
            error_reason=data.get("error_reason"),
        )
