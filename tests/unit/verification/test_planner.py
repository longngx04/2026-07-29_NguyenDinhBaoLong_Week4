from project_sentinel.models import AnalysisLocation, SecurityAnalysisRecord
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision
from project_sentinel.verification.planner import (
    build_verification_plan,
    build_verification_plans,
)


def test_build_verification_plan_single_record():
    record = SecurityAnalysisRecord(
        schema_version="1.0",
        analysis_id="rec-001",
        group_key="gk-001",
        source_finding_ids=["f-1"],
        title="SQL Injection in attack lesson",
        severity="HIGH",
        scanner_severities={"opengrep": "HIGH"},
        confidence="HIGH",
        confidence_rationale="Verified SQLi flaw",
        locations=[AnalysisLocation(file="src/main/java/org/owasp/webgoat/plugin/SqlInjectionLesson.java", line=42)],
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        evidence="SELECT * FROM users",
        explanation="SQL injection flaw",
        preconditions=["User login"],
        verification_steps=["Send SQLi probe to /WebGoat/attack"],
        remediation="Use PreparedStatements",
        knowledge_refs=[],
        limitations=[],
    )

    cand = build_verification_plan(record)

    assert isinstance(cand, VerificationCandidate)
    assert cand.analysis_record_id == "rec-001"
    assert cand.group_id == "rec-001"
    assert cand.cwe == "CWE-89"
    assert cand.decision == VerificationDecision.PLANNED
    assert cand.endpoint_id == "ep_attack"
    assert cand.template_id == "tmpl_attack_post"
    assert cand.method == "POST"
    assert cand.path == "/WebGoat/attack"


def test_build_verification_plans_multi_record():
    r1 = SecurityAnalysisRecord(
        schema_version="1.0",
        analysis_id="rec-001",
        group_key="gk-001",
        source_finding_ids=["f-1"],
        title="XSS flaw",
        severity="MEDIUM",
        scanner_severities={"opengrep": "MEDIUM"},
        confidence="HIGH",
        confidence_rationale="Verified XSS",
        locations=[AnalysisLocation(file="src/main/java/org/owasp/webgoat/plugin/XssLesson.java", line=10)],
        cwe=["CWE-79"],
        owasp=["A03:2021"],
        evidence="<script>",
        explanation="XSS flaw",
        preconditions=[],
        verification_steps=[],
        remediation="",
        knowledge_refs=[],
        limitations=[],
    )
    r2 = SecurityAnalysisRecord(
        schema_version="1.0",
        analysis_id="rec-002",
        group_key="gk-002",
        source_finding_ids=["f-2"],
        title="General configuration issue",
        severity="LOW",
        scanner_severities={"opengrep": "LOW"},
        confidence="MEDIUM",
        confidence_rationale="General flaw",
        locations=[],
        cwe=["CWE-200"],
        owasp=[],
        evidence="",
        explanation="",
        preconditions=[],
        verification_steps=[],
        remediation="",
        knowledge_refs=[],
        limitations=[],
    )

    candidates = build_verification_plans([r1, r2])

    assert len(candidates) == 2
    assert candidates[0].endpoint_id == "ep_attack"
    assert candidates[1].endpoint_id == "ep_health"
