"""Vi tri dang URL cho finding DAST, cung ky luat provenance nhu file:line."""

import json
from pathlib import Path

SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "schemas" / "security-analysis-record.schema.json"
)


def test_schema_allows_both_location_shapes():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    location = schema["properties"]["locations"]["items"]
    assert "oneOf" in location
    required = [set(branch["required"]) for branch in location["oneOf"]]
    assert {"file", "line"} in required
    assert {"url"} in required


def test_a_url_the_agent_invented_is_rejected():
    from project_sentinel.analysis.validators import validate_provenance

    is_valid, errors = validate_provenance(
        record_dict={
            "analysis_id": "a1",
            "group_key": "grp-1",
            "source_finding_ids": ["zap-1"],
            "locations": [{"url": "http://gateway-dast:8081/WebGoat/KHONG-CO-THAT"}],
        },
        input_group_finding_ids=["zap-1"],
        input_locations=[{"url": "http://gateway-dast:8081/WebGoat/login"}],
        input_knowledge_paths=[],
    )
    assert not is_valid
    assert any("KHONG-CO-THAT" in e for e in errors)


def test_a_url_present_in_the_input_is_accepted():
    from project_sentinel.analysis.validators import validate_provenance

    is_valid, errors = validate_provenance(
        record_dict={
            "analysis_id": "a1",
            "group_key": "grp-1",
            "source_finding_ids": ["zap-1"],
            "locations": [{"url": "http://gateway-dast:8081/WebGoat/login"}],
        },
        input_group_finding_ids=["zap-1"],
        input_locations=[{"url": "http://gateway-dast:8081/WebGoat/login"}],
        input_knowledge_paths=[],
    )
    assert is_valid, f"Expected valid, got errors: {errors}"


def test_a_url_from_an_instance_is_accepted():
    from project_sentinel.analysis.validators import validate_provenance

    is_valid, errors = validate_provenance(
        record_dict={
            "analysis_id": "a1",
            "group_key": "grp-1",
            "source_finding_ids": ["zap-1"],
            "locations": [{"url": "http://gateway-dast:8081/WebGoat/b"}],
        },
        input_group_finding_ids=["zap-1"],
        input_locations=[{"url": "http://gateway-dast:8081/WebGoat/b"}],
        input_knowledge_paths=[],
    )
    assert is_valid, f"Expected valid, got errors: {errors}"
