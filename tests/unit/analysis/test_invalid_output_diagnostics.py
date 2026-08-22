"""Unit tests for invalid output diagnostics in the analysis pipeline."""

from pathlib import Path
from typing import Optional

from project_sentinel.analysis.grouping import FindingGroup
from project_sentinel.analysis.pipeline import (
    _ResponseErrors,
    _analyze_one_group,
    _normalize_reason,
    run_pipeline,
)
from project_sentinel.config import AppConfig
from project_sentinel.llm.base import AnalysisPacket, LLMProvider, LLMResult
from project_sentinel.models import AnalysisLocation, NormalizedFinding, NormalizedLocation

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "schemas" / "security-analysis-record.schema.json"
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


class ReplayProvider(LLMProvider):
    """Deterministic provider returning pre-configured responses."""

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.call_count = 0

    def analyze(
        self, packet: AnalysisPacket, system_prompt: Optional[str] = None
    ) -> LLMResult:
        idx = min(self.call_count, len(self.responses) - 1)
        resp = self.responses[idx]
        self.call_count += 1
        return LLMResult(
            raw_response=str(resp),
            parsed_response=resp,
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        return LLMResult(raw_response="{}", parsed_response={})


def _valid_record(group_key="grp-1", finding_id="f-01"):
    return {
        "schema_version": "1.0",
        "analysis_id": "analysis-123",
        "group_key": group_key,
        "source_finding_ids": [finding_id],
        "title": "SQL Injection",
        "severity": "high",
        "disposition": "likely",
        "attacker_control": "proven",
        "reachability": "proven",
        "scanner_severities": ["high"],
        "confidence": "high",
        "confidence_rationale": "Direct concatenation",
        "locations": [{"file": "App.java", "line": 10}],
        "cwe": ["CWE-89"],
        "owasp": ["A03:2021-Injection"],
        "evidence": [{"type": "scanner", "finding_id": finding_id, "content": "query"}],
        "explanation": "SQL Injection found.",
        "preconditions": ["Input reachable"],
        "verification_steps": [{"action": "review_source", "detail": "check"}],
        "remediation": ["Use prepared statements"],
        "knowledge_refs": [],
        "limitations": [],
    }


def _make_group(group_key="grp-1", finding_id="f-01"):
    return FindingGroup(
        group_key=group_key,
        rule_id="sql-injection",
        title="SQL Injection",
        severity="high",
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        source_finding_ids=[finding_id],
        locations=[AnalysisLocation(file="App.java", line=10)],
        scanner_severities=["high"],
        findings=[
            NormalizedFinding(
                id=finding_id,
                rule_id="sql-injection",
                title="SQL Injection",
                severity="high",
                confidence="high",
                location=NormalizedLocation(file="App.java", line=10),
                tool="opengrep",
            )
        ],
    )


def test_outcome_validation_errors_captures_provenance_failure(tmp_path):
    """A provenance error must populate outcome.validation_errors with prefix 'provenance:'."""
    config = AppConfig(
        project_root=tmp_path,
        schema_path=SCHEMA_PATH,
        allowlist_path=ALLOWLIST_PATH,
        validation_max_retries=0,
    )
    group = _make_group(group_key="grp-prov", finding_id="f-real")

    # Model returns record citing a fabricated finding ID
    bad_record = _valid_record(group_key="grp-prov", finding_id="f-invented-999")
    provider = ReplayProvider([bad_record])

    outcome = _analyze_one_group(group, config, provider)

    assert outcome.record is None
    assert len(outcome.validation_errors) > 0
    provenance_errors = [e for e in outcome.validation_errors if e.startswith("provenance:")]
    assert len(provenance_errors) > 0
    assert "f-invented-999" in provenance_errors[0]


def test_unresolved_group_reasons_records_failed_group_key(tmp_path):
    """A group failing all retries must appear in unresolved_group_reasons with its group_key."""
    input_file = tmp_path / "findings.json"
    input_file.write_text(
        '{"schema_version": "1.0", "findings": [{"id": "f-1", "rule_id": "r1", '
        '"title": "t", "severity": "high", "confidence": "high", '
        '"location": {"file": "A.java", "line": 10}}]}',
        encoding="utf-8",
    )
    output_jsonl = tmp_path / "analysis.jsonl"
    summary_file = tmp_path / "summary.json"

    config = AppConfig(
        project_root=tmp_path,
        input_findings_path=input_file,
        output_jsonl_path=output_jsonl,
        summary_path=summary_file,
        schema_path=SCHEMA_PATH,
        allowlist_path=ALLOWLIST_PATH,
        validation_max_retries=1,
    )

    # Provider returning schema-invalid output on both attempts
    invalid_record = {"invalid_key": "missing_required_fields"}
    provider = ReplayProvider([invalid_record, invalid_record])

    # We patch build_llm to return our ReplayProvider
    import project_sentinel.analysis.pipeline as pipeline_mod

    orig_build_llm = pipeline_mod.build_llm
    pipeline_mod.build_llm = lambda cfg: provider
    try:
        summary = run_pipeline(config)
    finally:
        pipeline_mod.build_llm = orig_build_llm

    assert summary["output_record_count"] == 0
    assert summary["invalid_output_count"] == 1
    assert len(summary["unresolved_group_reasons"]) == 1
    # Check that the group key is in unresolved_group_reasons
    grp_key = list(summary["unresolved_group_reasons"].keys())[0]
    assert len(summary["unresolved_group_reasons"][grp_key]) > 0
    assert any("schema:" in r for r in summary["unresolved_group_reasons"][grp_key])


def test_invalid_reasons_normalizes_and_aggregates_counts():
    """invalid_reasons merges errors of the same type with different values into 1 key with count 2."""
    raw1 = "provenance: Invented source_finding_id 'f-1' not present in input group at line 10"
    raw2 = "provenance: Invented source_finding_id 'f-2' not present in input group at line 20"

    norm1 = _normalize_reason(raw1)
    norm2 = _normalize_reason(raw2)

    assert norm1 == norm2
    assert "'<val>'" in norm1
    assert "<num>" in norm1

    # Test ResponseErrors as_reasons
    errors = _ResponseErrors(
        schema="missing field",
        provenance=["invented id 'f-100'"],
        unsafe=["contains token"],
        objective="bad endpoint",
    )
    reasons = errors.as_reasons()
    assert reasons == [
        "schema: missing field",
        "provenance: invented id 'f-100'",
        "unsafe: contains token",
        "objective: bad endpoint",
    ]


def test_clean_run_contains_empty_diagnostic_dicts(tmp_path):
    """A clean run without errors has invalid_reasons and unresolved_group_reasons as empty dicts."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text('{"schema_version": "1.0", "findings": []}', encoding="utf-8")
    output_jsonl = tmp_path / "analysis.jsonl"
    summary_file = tmp_path / "summary.json"

    config = AppConfig(
        project_root=tmp_path,
        input_findings_path=empty_file,
        output_jsonl_path=output_jsonl,
        summary_path=summary_file,
        schema_path=SCHEMA_PATH,
        allowlist_path=ALLOWLIST_PATH,
    )

    summary = run_pipeline(config)

    assert "invalid_reasons" in summary
    assert summary["invalid_reasons"] == {}
    assert "unresolved_group_reasons" in summary
    assert summary["unresolved_group_reasons"] == {}
