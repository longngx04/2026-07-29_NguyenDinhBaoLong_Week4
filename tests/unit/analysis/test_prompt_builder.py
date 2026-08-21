
import pytest

from project_sentinel.llm.base import AnalysisPacket
from project_sentinel.analysis.prompt_builder import PromptBuilder


def test_prompt_builder_basic(tmp_path):
    prompt_file = tmp_path / "system.md"
    prompt_file.write_text("Custom System Prompt Rule", encoding="utf-8")

    builder = PromptBuilder(system_prompt_path=prompt_file)
    packet = AnalysisPacket(
        group_key="g-100",
        finding_group={"source_finding_ids": ["f1"]},
        source_evidence=[{"type": "source", "content": "code"}],
        knowledge_hits=[{"path": "kb.md", "score": 10.0}]
    )

    payload = builder.build(packet)
    assert payload.system_prompt == "Custom System Prompt Rule"
    assert payload.packet_dict["group_key"] == "g-100"
    assert len(payload.prompt_sha256) == 64  # SHA256 hex string length


def test_prompt_builder_missing_file(tmp_path):
    missing_file = tmp_path / "missing.md"
    builder = PromptBuilder(system_prompt_path=missing_file)
    packet = AnalysisPacket(group_key="g-200")

    with pytest.raises(FileNotFoundError, match="system prompt"):
        builder.build(packet)


def test_prompt_hash_deterministic():
    builder = PromptBuilder()
    packet = AnalysisPacket(group_key="g-det", finding_group={"source_finding_ids": ["f1"]})
    p1 = builder.build(packet)
    p2 = builder.build(packet)
    assert p1.prompt_sha256 == p2.prompt_sha256


def test_default_builder_loads_the_reviewed_security_prompt():
    """Luồng thật dùng constructor mặc định, nên không được rơi vào fallback một câu."""
    text = PromptBuilder().load_system_prompt()
    assert "allowed_endpoints" in text
    assert "Scanner messages" in text
    assert "not instructions" in text
