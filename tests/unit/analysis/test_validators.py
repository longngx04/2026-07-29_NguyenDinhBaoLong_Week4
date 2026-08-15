from pathlib import Path
from project_sentinel.analysis.validators import read_jsonl, validate_provenance, validate_record_schema, write_jsonl_atomic


def _sample_valid_record():
    return {
        "schema_version": "1.0",
        "analysis_id": "analysis-12345",
        "group_key": "grp-test-01",
        "source_finding_ids": ["f-01"],
        "title": "SQL Injection in Test.java",
        "severity": "high",
        "scanner_severities": ["high"],
        "confidence": "high",
        "confidence_rationale": "Direct concatenation to query",
        "locations": [{"file": "test.java", "line": 10}],
        "cwe": ["CWE-89"],
        "owasp": ["A03:2021-Injection"],
        "evidence": [
            {
                "type": "scanner",
                "finding_id": "f-01",
                "content": "Statement.executeQuery"
            }
        ],
        "explanation": "Untrusted input concatenated to SQL statement.",
        "preconditions": ["User input reachable"],
        "verification_steps": ["Check SQL parameters"],
        "remediation": ["Use PreparedStatement"],
        "knowledge_refs": [{"path": "knowledge/cwe-89.md", "score": 0.95}],
        "limitations": ["Static analysis only"]
    }


def test_write_and_read_jsonl_atomic(tmp_path):
    records = [
        {"id": "1", "data": "hello"},
        {"id": "2", "data": "world"}
    ]
    out_file = tmp_path / "test.jsonl"
    write_jsonl_atomic(records, out_file)
    
    assert out_file.exists()
    loaded = read_jsonl(out_file)
    assert len(loaded) == 2
    assert loaded[0]["data"] == "hello"


def test_validate_record_schema_valid():
    schema_file = Path(__file__).parent.parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    rec = _sample_valid_record()
    is_valid, error = validate_record_schema(rec, schema_file)
    assert is_valid, f"Schema validation failed: {error}"


def test_validate_provenance_valid():
    rec = _sample_valid_record()
    is_valid, errors = validate_provenance(
        record_dict=rec,
        input_group_finding_ids=["f-01"],
        input_locations=[{"file": "test.java", "line": 10}],
        input_knowledge_paths=["knowledge/cwe-89.md"],
        input_cwes=["CWE-89"],
        input_owasps=["A03:2021-Injection"]
    )
    assert is_valid, f"Provenance validation failed: {errors}"


def test_validate_provenance_hallucinated():
    rec = _sample_valid_record()
    rec["source_finding_ids"] = ["fake-hallucinated-id-999"]
    rec["locations"] = [{"file": "invented/path/Fake.java", "line": 999}]
    
    is_valid, errors = validate_provenance(
        record_dict=rec,
        input_group_finding_ids=["f-01"],
        input_locations=[{"file": "test.java", "line": 10}],
        input_knowledge_paths=[]
    )
    assert not is_valid
    assert any("fake-hallucinated-id-999" in e for e in errors)
    assert any("invented/path/Fake.java" in e for e in errors)


def test_validate_provenance_rejects_invented_when_input_empty():
    rec = {
        "source_finding_ids": ["f1"],
        "locations": [{"file": "a.java", "line": 1}],
        "cwe": ["CWE-999"],
        "owasp": [],
        "evidence": [],
        "knowledge_refs": []
    }
    ok, errs = validate_provenance(
        rec,
        ["f1"],
        [{"file": "a.java", "line": 1}],
        [],
        input_cwes=[],
        input_owasps=[],
        input_source_evidence=[]
    )
    assert not ok
    assert any("CWE" in e for e in errs)
