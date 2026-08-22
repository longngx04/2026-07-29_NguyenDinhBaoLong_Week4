"""
Data models for input findings and output security analysis records.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from project_sentinel.pathutil import canonicalize_source_path


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class NormalizedLocation:
    file: str
    line: int


@dataclass
class NormalizedFinding:
    id: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    location: NormalizedLocation
    fingerprint: Optional[str] = None
    cwe: List[str] = field(default_factory=list)
    owasp: List[str] = field(default_factory=list)
    message: str = ""
    runtime_evidence: Optional[Dict[str, Any]] = None
    tool: str = ""
    instances: List[Dict[str, Any]] = field(default_factory=list)
    instances_total: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedFinding":
        loc_data = data.get("location")
        if isinstance(loc_data, dict):
            file_val = canonicalize_source_path(str(loc_data.get("file", "")))
            line_val = int(loc_data.get("line", 0))
        else:
            file_val = canonicalize_source_path(
                str(data.get("file_or_url", data.get("file", "")))
            )
            line_val = int(data.get("line", 0))
        loc = NormalizedLocation(file=file_val, line=line_val)

        def _to_list(val: Any) -> List[str]:
            if isinstance(val, list):
                return [str(x) for x in val if str(x).strip()]
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        return cls(
            id=str(data.get("id", "")),
            rule_id=str(data.get("rule_id", "")),
            title=str(data.get("title", "")),
            severity=str(data.get("severity", "medium")),
            confidence=str(data.get("confidence", "medium")),
            location=loc,
            fingerprint=data.get("fingerprint"),
            cwe=_to_list(data.get("cwe")),
            owasp=_to_list(data.get("owasp")),
            message=str(data.get("message", "")),
            runtime_evidence=data.get("runtime_evidence"),
            tool=str(data.get("tool", "")),
            instances=list(data.get("instances") or []),
            instances_total=int(data.get("instances_total") or len(data.get("instances") or [])),
        )



@dataclass
class NormalizedFindingFile:
    count: int
    findings: List[NormalizedFinding]


@dataclass
class AnalysisLocation:
    file: str
    line: int


@dataclass
class EvidenceItem:
    type: str  # "scanner" or "source"
    content: str
    finding_id: Optional[str] = None
    path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.type == "scanner":
            return {
                "type": "scanner",
                "finding_id": self.finding_id or "",
                "content": self.content
            }
        return {
            "type": "source",
            "path": self.path or "",
            "start_line": self.start_line if self.start_line is not None else 0,
            "end_line": self.end_line if self.end_line is not None else 0,
            "content": self.content
        }


@dataclass
class KnowledgeRef:
    path: str
    score: float


@dataclass
class SecurityAnalysisRecord:
    schema_version: str
    analysis_id: str
    group_key: str
    source_finding_ids: List[str]
    title: str
    severity: Severity
    scanner_severities: List[str]
    confidence: Confidence
    confidence_rationale: str
    locations: List[AnalysisLocation]
    cwe: List[str]
    owasp: List[str]
    evidence: List[EvidenceItem]
    explanation: str
    preconditions: List[str]
    verification_steps: List[str]
    remediation: List[str]
    knowledge_refs: List[KnowledgeRef]
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "group_key": self.group_key,
            "source_finding_ids": self.source_finding_ids,
            "title": self.title,
            "severity": self.severity.value if isinstance(self.severity, Severity) else str(self.severity),
            "scanner_severities": self.scanner_severities,
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else str(self.confidence),
            "confidence_rationale": self.confidence_rationale,
            "locations": [
                {"url": loc.file} if (loc.file.startswith("http://") or loc.file.startswith("https://"))
                else {"file": loc.file, "line": loc.line}
                for loc in self.locations
            ],
            "cwe": self.cwe,
            "owasp": self.owasp,
            "evidence": [ev.to_dict() for ev in self.evidence],
            "explanation": self.explanation,
            "preconditions": self.preconditions,
            "verification_steps": self.verification_steps,
            "remediation": self.remediation,
            "knowledge_refs": [{"path": k.path, "score": k.score} for k in self.knowledge_refs],
            "limitations": self.limitations
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityAnalysisRecord":
        locations = []
        for loc in data.get("locations", []):
            if isinstance(loc, dict):
                if "url" in loc:
                    locations.append(AnalysisLocation(file=str(loc.get("url", "")), line=0))
                else:
                    locations.append(AnalysisLocation(file=str(loc.get("file", "")), line=int(loc.get("line", 0))))
            else:
                locations.append(loc)
        evidence = [

            EvidenceItem(
                type=str(ev.get("type", "scanner")),
                content=str(ev.get("content", "")),
                finding_id=ev.get("finding_id"),
                path=ev.get("path"),
                start_line=ev.get("start_line"),
                end_line=ev.get("end_line"),
            )
            if isinstance(ev, dict) else ev
            for ev in data.get("evidence", [])
        ]
        knowledge_refs = [
            KnowledgeRef(
                path=str(k.get("path", "")),
                score=float(k.get("score", 0.0))
            )
            if isinstance(k, dict) else k
            for k in data.get("knowledge_refs", [])
        ]

        sev_raw = data.get("severity", "medium")
        try:
            sev_val: Union[Severity, str] = Severity(sev_raw)
        except ValueError:
            sev_val = str(sev_raw)

        conf_raw = data.get("confidence", "medium")
        try:
            conf_val: Union[Confidence, str] = Confidence(conf_raw)
        except ValueError:
            conf_val = str(conf_raw)

        return cls(
            schema_version=str(data.get("schema_version", "1.0")),
            analysis_id=str(data.get("analysis_id", "")),
            group_key=str(data.get("group_key", "")),
            source_finding_ids=list(data.get("source_finding_ids", [])),
            title=str(data.get("title", "")),
            severity=sev_val,  # type: ignore[arg-type]
            scanner_severities=list(data.get("scanner_severities", [])),
            confidence=conf_val,  # type: ignore[arg-type]
            confidence_rationale=str(data.get("confidence_rationale", "")),
            locations=locations,
            cwe=list(data.get("cwe", [])),
            owasp=list(data.get("owasp", [])),
            evidence=evidence,
            explanation=str(data.get("explanation", "")),
            preconditions=list(data.get("preconditions", [])),
            verification_steps=list(data.get("verification_steps", [])),
            remediation=list(data.get("remediation", [])),
            knowledge_refs=knowledge_refs,
            limitations=list(data.get("limitations", [])),
        )

