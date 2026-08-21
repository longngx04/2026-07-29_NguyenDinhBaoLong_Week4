"""Schema record phải chấp nhận verification_objective và chặn dạng sai."""

import copy
from pathlib import Path
import pytest
from project_sentinel.analysis.validators import validate_record_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "schemas" / "security-analysis-record.schema.json"


@pytest.fixture
def base_record() -> dict:
    return {
        "schema_version": "1.0",
        "analysis_id": "analysis-0000aaaa-1111-2222-3333-444455556666",
        "group_key": "sql-injection|Login.java",
        "source_finding_ids": ["finding-1"],
        "title": "SQL Injection qua nối chuỗi",
        "severity": "high",
        "disposition": "likely",
        "attacker_control": "proven",
        "reachability": "proven",
        "scanner_severities": ["ERROR"],
        "confidence": "high",
        "confidence_rationale": "Scanner báo trực tiếp trên câu lệnh nối chuỗi.",
        "locations": [{"file": "src/main/java/Login.java", "line": 42}],
        "cwe": [],
        "owasp": [],
        "evidence": [
            {"type": "scanner", "finding_id": "finding-1", "content": "String concat in SQL"}
        ],
        "explanation": "Truy vấn được ghép chuỗi trực tiếp từ dữ liệu người dùng.",
        "preconditions": [],
        "verification_steps": [],
        "remediation": ["Dùng PreparedStatement."],
        "knowledge_refs": [],
        "limitations": [],
    }


def test_record_without_verification_objective_is_still_valid(base_record):
    ok, err = validate_record_schema(base_record, SCHEMA_PATH)
    assert ok, err


def test_record_with_null_verification_objective_is_valid(base_record):
    record = copy.deepcopy(base_record)
    record["verification_objective"] = None
    ok, err = validate_record_schema(record, SCHEMA_PATH)
    assert ok, err


def test_record_with_full_verification_objective_is_valid(base_record):
    record = copy.deepcopy(base_record)
    record["verification_objective"] = {
        "description": "Kiểm tra endpoint bài học có nhận chuỗi dài không",
        "endpoint_hint": "POST /WebGoat/attack",
        "payload_kind": "long_string",
        "rationale": "Finding nằm ở handler xử lý tham số của lesson router.",
    }
    ok, err = validate_record_schema(record, SCHEMA_PATH)
    assert ok, err


def test_unknown_payload_kind_is_rejected(base_record):
    record = copy.deepcopy(base_record)
    record["verification_objective"] = {
        "description": "x",
        "endpoint_hint": "GET /WebGoat/attack",
        "payload_kind": "drop_table",
        "rationale": "y",
    }
    ok, err = validate_record_schema(record, SCHEMA_PATH)
    assert not ok, f"payload_kind ngoài 4 loại an toàn phải bị chặn (err={err})"


def test_missing_field_inside_objective_is_rejected(base_record):
    record = copy.deepcopy(base_record)
    record["verification_objective"] = {"description": "chỉ có mô tả"}
    ok, err = validate_record_schema(record, SCHEMA_PATH)
    assert not ok, f"verification_objective thiếu field bắt buộc phải bị chặn (err={err})"


def test_extra_field_inside_objective_is_rejected(base_record):
    record = copy.deepcopy(base_record)
    record["verification_objective"] = {
        "description": "x",
        "endpoint_hint": "GET /WebGoat/attack",
        "payload_kind": "empty_value",
        "rationale": "y",
        "raw_url": "https://external.invalid/admin",
    }
    ok, err = validate_record_schema(record, SCHEMA_PATH)
    assert not ok, f"Field lạ trong verification_objective phải bị chặn (err={err})"
