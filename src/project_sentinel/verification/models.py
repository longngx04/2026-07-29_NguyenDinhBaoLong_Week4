"""
Data models for verification candidates, probe plans, and execution results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class VerificationStatus(str, Enum):
    VERIFIED_REACHABLE = "VERIFIED_REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


@dataclass
class VerificationProbe:
    probe_id: str
    method: str = "GET"
    path: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    expected_status: int = 200
    expected_indicator: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "probe_id": self.probe_id,
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "params": self.params,
            "expected_status": self.expected_status,
        }
        if self.expected_indicator is not None:
            data["expected_indicator"] = self.expected_indicator
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationProbe":
        return cls(
            probe_id=str(data.get("probe_id", "")),
            method=str(data.get("method", "GET")),
            path=str(data.get("path", "")),
            headers=dict(data.get("headers", {})),
            params=dict(data.get("params", {})),
            expected_status=int(data.get("expected_status", 200)),
            expected_indicator=data.get("expected_indicator"),
        )


@dataclass
class VerificationPlan:
    plan_id: str
    analysis_record_id: str
    group_id: str
    cwe: str
    target_url: str
    probes: List[VerificationProbe] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "analysis_record_id": self.analysis_record_id,
            "group_id": self.group_id,
            "cwe": self.cwe,
            "target_url": self.target_url,
            "probes": [p.to_dict() for p in self.probes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationPlan":
        raw_probes = data.get("probes", [])
        probes = [
            VerificationProbe.from_dict(p) if isinstance(p, dict) else p
            for p in raw_probes
        ]
        return cls(
            plan_id=str(data.get("plan_id", "")),
            analysis_record_id=str(data.get("analysis_record_id", "")),
            group_id=str(data.get("group_id", "")),
            cwe=str(data.get("cwe", "")),
            target_url=str(data.get("target_url", "")),
            probes=probes,
        )


@dataclass
class VerificationResult:
    result_id: str
    plan_id: str
    group_id: str
    status: Union[VerificationStatus, str]
    status_code: Optional[int] = None
    evidence: str = ""
    execution_time_ms: float = 0.0

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        status_raw = data.get("status", "FAILED")
        try:
            status_val: Union[VerificationStatus, str] = VerificationStatus(status_raw)
        except ValueError:
            status_val = str(status_raw)

        return cls(
            result_id=str(data.get("result_id", "")),
            plan_id=str(data.get("plan_id", "")),
            group_id=str(data.get("group_id", "")),
            status=status_val,
            status_code=data.get("status_code"),
            evidence=str(data.get("evidence", "")),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
        )
