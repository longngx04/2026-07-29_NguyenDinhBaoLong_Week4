from project_sentinel.models import (
    AnalysisLocation,
    Confidence,
    EvidenceItem,
    KnowledgeRef,
    NormalizedFinding,
    SecurityAnalysisRecord,
    Severity,
)


def test_normalized_finding_from_dict_location_dict():
    data = {
        "id": "f-01",
        "rule_id": "rule-sqli",
        "title": "SQL Injection",
        "severity": "high",
        "confidence": "MEDIUM",
        "location": {"file": "app/db.py", "line": 42},
        "cwe": ["CWE-89"],
        "owasp": "A03:2021-Injection",
        "message": "Potential SQLi"
    }
    finding = NormalizedFinding.from_dict(data)
    assert finding.id == "f-01"
    assert finding.location.file == "app/db.py"
    assert finding.location.line == 42
    assert finding.cwe == ["CWE-89"]
    assert finding.owasp == ["A03:2021-Injection"]


def test_normalized_finding_from_dict_file_or_url():
    data = {
        "id": "f-02",
        "rule_id": "rule-cmdi",
        "title": "Command Injection",
        "severity": "high",
        "confidence": "HIGH",
        "file_or_url": "app/exec.py",
        "line": 100,
        "cwe": "CWE-78",
        "message": "Potential CmdI"
    }
    finding = NormalizedFinding.from_dict(data)
    assert finding.location.file == "app/exec.py"
    assert finding.location.line == 100
    assert finding.cwe == ["CWE-78"]
    assert finding.owasp == []


def test_security_analysis_record_to_dict():
    rec = SecurityAnalysisRecord(
        schema_version="1.0",
        analysis_id="analysis-a1b2c3d4e5f6",
        group_key="group-1",
        source_finding_ids=["f-01"],
        title="SQL Injection Finding",
        severity=Severity.HIGH,
        scanner_severities=["high"],
        confidence=Confidence.MEDIUM,
        confidence_rationale="Query parameter string concatenation detected.",
        locations=[AnalysisLocation(file="app/db.py", line=42)],
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        evidence=[
            EvidenceItem(type="scanner", finding_id="f-01", content="Scanner finding message"),
            EvidenceItem(type="source", path="app/db.py", start_line=40, end_line=45, content="db.execute(query)")
        ],
        explanation="Untrusted input is passed to SQL query.",
        preconditions=["User reaches search endpoint."],
        verification_steps=["Check query parameterization."],
        remediation=["Use PreparedStatement."],
        knowledge_refs=[KnowledgeRef(path="knowledge/cwe-89.md", score=10.0)],
        limitations=["Data flow not traced interprocedurally."]
    )
    
    d = rec.to_dict()
    assert d["schema_version"] == "1.0"
    assert d["severity"] == "high"
    assert d["confidence"] == "medium"
    assert len(d["locations"]) == 1
    assert d["locations"][0] == {"file": "app/db.py", "line": 42}
    assert len(d["evidence"]) == 2
    assert d["evidence"][0]["type"] == "scanner"
    assert d["evidence"][1]["type"] == "source"
