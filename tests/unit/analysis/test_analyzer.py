from pathlib import Path
import pytest

from project_sentinel.analysis.analyzer import analyze_finding_group
from project_sentinel.analysis.grouping import group_findings
from project_sentinel.config import AppConfig
from project_sentinel.llm.openrouter import OpenRouterClient
from project_sentinel.models import NormalizedFinding, NormalizedLocation


@pytest.mark.llm
def test_analyze_finding_group_live(tmp_path, llm_ready):
    api_key = llm_ready

    rel_path = "benchmarks/targets/webgoat/src/Vulnerable.java"
    target_file = tmp_path / "benchmarks" / "targets" / "webgoat" / "src" / "Vulnerable.java"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("public class Vulnerable { void exec() {} }\n", encoding="utf-8")

    f1 = NormalizedFinding(
        id="f-01",
        rule_id="java-command-execution",
        title="Potential command injection",
        severity="high",
        confidence="MEDIUM",
        location=NormalizedLocation(file=rel_path, line=1),
        cwe=["CWE-78"],
        owasp=["A03:2021-Injection"]
    )

    groups = group_findings([f1])
    assert len(groups) == 1

    config = AppConfig(
        project_root=tmp_path,
        target_root=tmp_path / "benchmarks" / "targets" / "webgoat",
        api_key=api_key,
        knowledge_dir=Path(__file__).parent.parent.parent.parent / "data" / "knowledge-base",
        schema_path=Path(__file__).parent.parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    )

    client = OpenRouterClient(api_key=api_key, model=config.model_name)
    analysis_res = analyze_finding_group(groups[0], config, provider=client)

    assert analysis_res.group_key == groups[0].group_key
    assert len(analysis_res.prompt_payload.prompt_sha256) == 64
    assert analysis_res.llm_result.error is None
    parsed = analysis_res.llm_result.parsed_response
    assert isinstance(parsed, dict)
    assert analysis_res.llm_result.raw_response
    assert not (
        set(parsed).issubset({"type", "data"})
        and isinstance(parsed.get("data"), dict)
    ), "OpenRouter provider envelope was not normalized"
