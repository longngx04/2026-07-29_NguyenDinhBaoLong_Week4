import json
from pathlib import Path
import pytest

from project_sentinel.cli import main


def test_cli_exit_code_2_nonexistent_input():
    argv = ["analyze", "--input", "/nonexistent_findings.json"]
    exit_code = main(argv)
    assert exit_code == 2


def test_cli_exit_code_2_invalid_findings(tmp_path):
    invalid_file = tmp_path / "invalid-findings.json"
    invalid_file.write_text("{malformed json}", encoding="utf-8")
    output_jsonl = tmp_path / "output.jsonl"
    summary_file = tmp_path / "summary.json"

    argv = [
        "analyze",
        "--input", str(invalid_file),
        "--output", str(output_jsonl),
        "--summary", str(summary_file),
    ]
    exit_code = main(argv)
    assert exit_code == 2
    assert not output_jsonl.exists()


def test_cli_exit_code_3_openrouter_missing_key(monkeypatch, tmp_path):
    input_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings" / "valid.json"
    monkeypatch.setenv("LLM_API_KEY", "")

    argv = [
        "analyze",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.jsonl"),
        "--summary", str(tmp_path / "sum.json")
    ]
    exit_code = main(argv)
    assert exit_code == 3


def test_cli_exit_code_3_unsupported_provider(monkeypatch, tmp_path):
    input_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings" / "valid.json"
    monkeypatch.setenv("LLM_PROVIDER", "unsupported_provider")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    argv = [
        "analyze",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.jsonl"),
        "--summary", str(tmp_path / "sum.json")
    ]
    exit_code = main(argv)
    assert exit_code == 3


def test_cli_validate_command_success(tmp_path):
    # Test validate command on valid jsonl record
    schema_file = Path(__file__).parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    sample_jsonl = tmp_path / "valid.jsonl"
    sample_record = (
        '{"schema_version":"1.0","analysis_id":"analysis-12345","group_key":"grp-1",'
        '"source_finding_ids":["f-1"],"title":"SQL Injection in Test.java","severity":"high",'
        '"disposition":"likely","attacker_control":"proven","reachability":"proven",'
        '"scanner_severities":["high"],"confidence":"high","confidence_rationale":"Direct concatenation",'
        '"locations":[{"file":"test.java","line":1}],"cwe":["CWE-89"],"owasp":["A03:2021-Injection"],'
        '"evidence":[{"type":"scanner","finding_id":"f-1","content":"sink"}],"explanation":"Explanation",'
        '"preconditions":["pre"],'
        '"verification_steps":[{"action":"review_source","detail":"doc lai"}],'
        '"remediation":["rem"],'
        '"knowledge_refs":[{"path":"k.md","score":0.9}],"limitations":["lim"]}\n'
    )
    sample_jsonl.write_text(sample_record, encoding="utf-8")

    val_exit_code = main(["validate", "--input", str(sample_jsonl), "--schema", str(schema_file)])
    assert val_exit_code == 0


@pytest.mark.llm
def test_cli_analyze_live(tmp_path, llm_ready):

    fixture_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings" / "valid.json"
    fixture_data = json.loads(fixture_file.read_text(encoding="utf-8"))
    input_file = tmp_path / "single-finding.json"
    input_file.write_text(
        json.dumps(
            {
                **fixture_data,
                "count": 1,
                "findings": fixture_data["findings"][:1],
            }
        ),
        encoding="utf-8",
    )
    output_jsonl = tmp_path / "output.jsonl"
    summary_file = tmp_path / "summary.json"

    argv = [
        "analyze",
        "--input", str(input_file),
        "--output", str(output_jsonl),
        "--summary", str(summary_file),
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert output_jsonl.exists()
    assert summary_file.exists()


def test_cli_probe_exit_code_2_missing_gateway_key(monkeypatch):
    monkeypatch.delenv("SENTINEL_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    exit_code = main(["probe", "--method", "GET", "--path", "/WebGoat/actuator/health"])
    assert exit_code == 2


def test_cli_probe_denied_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    log_path = tmp_path / "requests.jsonl"
    exit_code = main(["probe", "--method", "GET", "--path", "/WebGoat/admin", "--log", str(log_path)])
    assert exit_code == 1
    assert '"policy_decision": "DENIED"' in log_path.read_text(encoding="utf-8")


def test_cli_probe_invalid_allowlist_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    exit_code = main(["probe", "--allowlist", str(tmp_path / "nonexistent.json")])
    assert exit_code == 2

