import json
from pathlib import Path
import pytest

from project_sentinel.config import AppConfig
from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.analysis.validators import read_jsonl, validate_record_schema


def test_pipeline_empty_input(tmp_path):
    input_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings" / "empty.json"
    output_jsonl = tmp_path / "security-analysis.jsonl"
    summary_file = tmp_path / "run-summary.json"

    config = AppConfig(
        project_root=tmp_path,
        input_findings_path=input_file,
        output_jsonl_path=output_jsonl,
        summary_path=summary_file,
        api_key="test-key",
        knowledge_dir=Path(__file__).parent.parent.parent / "data" / "knowledge-base",
        schema_path=Path(__file__).parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    )

    summary = run_pipeline(config)

    assert summary["input_finding_count"] == 0
    assert summary["group_count"] == 0
    assert summary["output_record_count"] == 0
    assert summary["llm_call_count"] == 0
    assert summary["retry_count"] == 0
    assert summary["invalid_output_count"] == 0
    assert summary["prompt_sha256"] == ""
    assert "last_prompt_sha256" not in summary

    assert output_jsonl.exists()
    records = read_jsonl(output_jsonl)
    assert len(records) == 0

    assert summary_file.exists()
    summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary_data["output_record_count"] == 0
    assert summary_data["prompt_sha256"] == ""
    assert "last_prompt_sha256" not in summary_data


@pytest.mark.llm
def test_pipeline_live_valid_findings(tmp_path, llm_ready):
    api_key = llm_ready

    input_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings" / "valid.json"
    output_jsonl = tmp_path / "security-analysis.jsonl"
    summary_file = tmp_path / "run-summary.json"

    config = AppConfig(
        project_root=tmp_path,
        input_findings_path=input_file,
        output_jsonl_path=output_jsonl,
        summary_path=summary_file,
        api_key=api_key,
        knowledge_dir=Path(__file__).parent.parent.parent / "data" / "knowledge-base",
        schema_path=Path(__file__).parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    )

    summary = run_pipeline(config)

    schema_file = Path(__file__).parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    assert summary["schema_version"] == "1.0"
    assert summary["input_finding_count"] == 2
    assert summary["group_count"] == 2
    assert summary["output_record_count"] == 2
    assert summary["invalid_output_count"] == 0
    assert summary["llm_call_count"] >= 2

    assert output_jsonl.exists()
    records = read_jsonl(output_jsonl)
    assert len(records) == 2
    for rec in records:
        is_valid, err = validate_record_schema(rec, schema_file)
        assert is_valid, f"Schema error: {err}"
