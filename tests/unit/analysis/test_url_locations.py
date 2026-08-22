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


def test_end_to_end_zap_group_packet_url_provenance_valid(tmp_path):
    from project_sentinel.analysis.grouping import group_findings
    from project_sentinel.analysis.packet_builder import build_analysis_packet
    from project_sentinel.analysis.validators import validate_provenance
    from project_sentinel.config import AppConfig
    from project_sentinel.models import NormalizedFinding, NormalizedLocation

    url = "http://gateway-dast:8081/WebGoat/login"
    f = NormalizedFinding(
        id="zap-10020-abc",
        rule_id="10020",
        title="Missing Anti-clickjacking Header",
        severity="medium",
        confidence="medium",
        location=NormalizedLocation(file=url, line=0),
        tool="zap",
        instances=[{"url": url, "method": "GET", "param": ""}],
        instances_total=1,
    )
    groups = group_findings([f])
    assert len(groups) == 1
    group = groups[0]

    # 1. FindingGroup to_packet_group_dict produces {"url": ...}
    group_dict = group.to_packet_group_dict()
    assert group_dict["locations"] == [{"url": url}]

    # 2. build_analysis_packet produces finding_group with {"url": ...}
    config = AppConfig(project_root=tmp_path)
    packet = build_analysis_packet(group=group, config=config)
    assert packet.finding_group["locations"] == [{"url": url}]

    # 3. Agent returns the exact URL location
    agent_record = {
        "analysis_id": "a-zap-1",
        "group_key": group.group_key,
        "source_finding_ids": ["zap-10020-abc"],
        "locations": [{"url": url}],
        "cwe": [],
        "owasp": [],
    }

    # 4. validate_provenance with group's input_locations (same rule as pipeline.py)
    input_locations = [
        {"url": location.file}
        if (location.file.startswith("http://") or location.file.startswith("https://"))
        else {"file": location.file, "line": location.line}
        for location in group.locations
    ]
    is_valid, errors = validate_provenance(
        record_dict=agent_record,
        input_group_finding_ids=group.source_finding_ids,
        input_locations=input_locations,
        input_knowledge_paths=[],
    )
    assert is_valid, f"Expected valid provenance for URL location, got: {errors}"


def test_mixed_sast_and_zap_group_preserves_both_location_types():
    from project_sentinel.models import NormalizedFinding, NormalizedLocation, AnalysisLocation
    from project_sentinel.analysis.grouping import FindingGroup

    java_file = "benchmarks/targets/webgoat/src/main/java/A.java"
    url = "http://gateway-dast:8081/WebGoat/login"

    f_sast = NormalizedFinding(
        id="sast-1",
        rule_id="java-sql-injection",
        title="SQL Injection",
        severity="high",
        confidence="high",
        location=NormalizedLocation(file=java_file, line=47),
        tool="opengrep",
    )
    f_zap = NormalizedFinding(
        id="zap-1",
        rule_id="10020",
        title="Anti-CSRF Header Missing",
        severity="medium",
        confidence="medium",
        location=NormalizedLocation(file=url, line=0),
        tool="zap",
    )

    group = FindingGroup(
        group_key="group-mixed",
        rule_id="mixed-rule",
        title="Mixed Group",
        severity="high",
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        source_finding_ids=["sast-1", "zap-1"],
        locations=[
            AnalysisLocation(file=java_file, line=47),
            AnalysisLocation(file=url, line=0),
        ],
        scanner_severities=["high", "medium"],
        findings=[f_sast, f_zap],
    )

    group_dict = group.to_packet_group_dict()
    assert {"file": java_file, "line": 47} in group_dict["locations"], "Finding SAST phải giữ file và line, không bị ép thành url"
    assert {"url": url} in group_dict["locations"], "Finding ZAP phải phát ra url"
    assert len(group_dict["locations"]) == 2


