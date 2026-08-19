import io
import os
import time

import pytest

from project_sentinel.config import AppConfig
from project_sentinel.llm.base import AnalysisPacket
from project_sentinel.llm.factory import build_llm
from project_sentinel.llm.openrouter import (
    OpenRouterClient,
    _read_response_bytes,
    _sanitize_error,
    _unwrap_json_envelope,
)


def test_read_response_bytes_returns_bounded_content():
    content = b'{"status":"ok"}'

    assert _read_response_bytes(io.BytesIO(content), deadline=time.monotonic() + 1) == content


def test_read_response_bytes_rejects_oversized_content():
    with pytest.raises(ValueError, match="exceeds the configured byte limit"):
        _read_response_bytes(io.BytesIO(b"12345"), deadline=time.monotonic() + 1, max_response_bytes=4)


def test_read_response_bytes_enforces_absolute_deadline():
    with pytest.raises(TimeoutError, match="total request deadline"):
        _read_response_bytes(io.BytesIO(b"{}"), deadline=time.monotonic() - 1)


def test_unwrap_json_envelope_with_type():
    record = {"schema_version": "1.0", "title": "SQL injection"}

    assert _unwrap_json_envelope({"type": "json_object", "data": record}) is record


def test_unwrap_json_envelope_with_data_only():
    proposal = {
        "objective_id": "objective-1",
        "proposal_id": "proposal-1",
        "endpoint_id": "health",
        "reason": "Confirm the endpoint is reachable.",
    }

    assert _unwrap_json_envelope({"data": proposal}) is proposal


def test_unwrap_json_envelope_preserves_flat_analysis_record():
    record = {
        "schema_version": "1.0",
        "analysis_id": "analysis-1234abcd",
        "group_key": "group-1",
        "source_finding_ids": ["finding-1"],
        "title": "SQL injection",
        "severity": "high",
        "scanner_severities": ["ERROR"],
        "confidence": "high",
        "confidence_rationale": "The scanner evidence shows string concatenation.",
        "locations": [{"file": "Example.java", "line": 10}],
        "cwe": ["CWE-89"],
        "owasp": ["A03:2021-Injection"],
        "evidence": [
            {
                "type": "scanner",
                "finding_id": "finding-1",
                "content": "Untrusted input reaches a SQL query.",
            }
        ],
        "explanation": "Untrusted input is concatenated into a SQL query.",
        "preconditions": ["The input is attacker-controlled."],
        "verification_steps": ["Review the query construction."],
        "remediation": ["Use parameterized queries."],
        "knowledge_refs": [],
        "limitations": [],
    }

    assert _unwrap_json_envelope(record) is record


def test_unwrap_json_envelope_preserves_flat_probe_proposal():
    proposal = {
        "objective_id": "objective-1",
        "proposal_id": "proposal-1",
        "endpoint_id": "health",
        "reason": "Confirm the endpoint is reachable.",
    }

    assert _unwrap_json_envelope(proposal) is proposal


def test_unwrap_json_envelope_preserves_data_dict_with_extra_key():
    parsed = {
        "type": "json_object",
        "data": {"title": "SQL injection"},
        "metadata": {"provider": "openrouter"},
    }

    assert _unwrap_json_envelope(parsed) is parsed


@pytest.mark.parametrize("data", ["record", ["record"], None])
def test_unwrap_json_envelope_preserves_non_dict_data(data):
    parsed = {"type": "json_object", "data": data}

    assert _unwrap_json_envelope(parsed) is parsed


def test_missing_api_key_does_not_call_network():
    client = OpenRouterClient(
        api_key="",
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/deepseek-v4-flash-0731",
        timeout_seconds=5.0,
        max_retries=1
    )
    with pytest.raises(ValueError, match="LLM_API_KEY is required"):
        client.analyze(AnalysisPacket(group_key="g1"), system_prompt="SYS")
    with pytest.raises(ValueError, match="LLM_API_KEY is required"):
        client.generate(system_prompt="SYS", user_prompt="Return JSON")


def test_provider_factory_openrouter(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-secret")
    config = AppConfig.from_env()
    llm = build_llm(config)
    assert isinstance(llm.inner, OpenRouterClient)


def test_provider_factory_rejects_unsupported(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unsupported_provider")
    config = AppConfig.from_env()
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        build_llm(config)


def test_sanitize_error_redacts_api_key():
    key = "sk-openrouter-secret-key"
    msg = f"Failed connecting with Auth Bearer {key} to server"
    sanitized = _sanitize_error(msg, key)
    assert key not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized


@pytest.mark.llm
def test_real_openrouter_live_call(llm_ready):
    api_key = llm_ready
    client = OpenRouterClient(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash-0731"),
        timeout_seconds=30.0,
        max_retries=1,
    )
    packet = AnalysisPacket(
        group_key="grp-live-test",
        finding_group={
            "source_finding_ids": ["f-live-1"],
            "locations": [{"file": "Test.java", "line": 10}],
            "rule_id": "java.lang.security.audit.sql-injection",
        },
        knowledge_hits=[],
    )
    result = client.analyze(packet, system_prompt="You are a security analyzer. Respond in JSON.")
    assert result.error is None
    assert result.parsed_response is not None
