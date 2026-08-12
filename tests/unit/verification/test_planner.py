import json
from pathlib import Path
from jsonschema import validate
from project_sentinel.models import SecurityAnalysisRecord, Severity, Confidence, AnalysisLocation, EvidenceItem, KnowledgeRef
from project_sentinel.verification.planner import build_verification_plan, build_verification_plans

SCHEMA_PATH = Path("schemas/verification-plan.schema.json")


def _load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_dummy_record(id_num: int = 1) -> SecurityAnalysisRecord:
    return SecurityAnalysisRecord(
        schema_version="1.0.0",
        analysis_id=f"analysis-{id_num}",
        group_key=f"group-{id_num}",
        source_finding_ids=[f"finding-{id_num}"],
        title=f"SQL Injection {id_num}",
        severity=Severity.HIGH,
        scanner_severities=["high"],
        confidence=Confidence.MEDIUM,
        confidence_rationale="Sink present",
        locations=[AnalysisLocation(file="webgoat-container/src/main/java/org/owasp/webgoat/session/LessonTracker.java", line=40)],
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        evidence=[EvidenceItem(type="scanner", finding_id=f"finding-{id_num}", content="SQL Query execution")],
        explanation="Explanation text",
        preconditions=["User input reachable"],
        verification_steps=["Send GET probe"],
        remediation=["Use PreparedStatement"],
        knowledge_refs=[KnowledgeRef(path="OWASP_SQL_Injection.md", score=0.9)],
        limitations=[]
    )


def test_build_verification_plan_single():
    record = _make_dummy_record(1)
    plan = build_verification_plan(record)
    assert plan.analysis_record_id == "analysis-1"
    assert plan.group_id == "analysis-1"
    assert plan.cwe == "CWE-89"
    assert plan.target_url.startswith("http://127.0.0.1:8080/WebGoat")
    assert len(plan.probes) >= 1

    # Validate against JSON schema
    schema = _load_schema()
    validate(instance=plan.to_dict(), schema=schema)


def test_build_verification_plans_batch():
    records = [_make_dummy_record(i) for i in range(1, 4)]
    plans = build_verification_plans(records)
    assert len(plans) == 3
    schema = _load_schema()
    for plan in plans:
        validate(instance=plan.to_dict(), schema=schema)
