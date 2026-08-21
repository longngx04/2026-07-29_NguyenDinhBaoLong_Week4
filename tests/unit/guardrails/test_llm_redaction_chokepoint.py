"""Mọi prompt rời khỏi hệ thống đều phải đi qua bộ che.

Test dùng một provider ghi lại (recorder) — đây KHÔNG phải mock của phụ thuộc
ngoài, mà là một provider thật ghi lại đầu vào để khẳng định bất biến.
"""

from dataclasses import dataclass, field, fields
from pathlib import Path


from project_sentinel.llm.base import AnalysisPacket, LLMResult
from project_sentinel.llm.redacting import RedactingProvider, _UNREDACTED_FIELDS


@dataclass
class RecordingProvider:
    """Provider thật, ghi lại đúng những gì nó nhận được."""

    seen_packets: list[AnalysisPacket] = field(default_factory=list)
    seen_prompts: list[tuple[str, str]] = field(default_factory=list)

    def analyze(self, packet: AnalysisPacket, system_prompt: str | None = None) -> LLMResult:
        self.seen_packets.append(packet)
        return LLMResult(raw_response="{}", parsed_response={})

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        self.seen_prompts.append((system_prompt, user_prompt))
        return LLMResult(raw_response="{}", parsed_response={})


def test_analyze_redacts_email_inside_the_packet():
    inner = RecordingProvider()
    RedactingProvider(inner).analyze(
        AnalysisPacket(
            group_key="g",
            finding_group={"note": "bao cao boi nguyen.van.a@example.com"},
        )
    )
    delivered = inner.seen_packets[0]
    assert "nguyen.van.a@example.com" not in str(delivered.finding_group)
    assert "[REDACTED_EMAIL]" in str(delivered.finding_group)


def test_analyze_redacts_nested_source_evidence():
    inner = RecordingProvider()
    RedactingProvider(inner).analyze(
        AnalysisPacket(
            group_key="g",
            source_evidence=[{"path": "a.java", "content": "pass=SieuBiMat123"}],
        )
    )
    assert "SieuBiMat123" not in str(inner.seen_packets[0].source_evidence)


def test_analyze_leaves_clean_content_untouched():
    inner = RecordingProvider()
    RedactingProvider(inner).analyze(
        AnalysisPacket(group_key="g", finding_group={"title": "SQL Injection"})
    )
    assert inner.seen_packets[0].finding_group == {"title": "SQL Injection"}


def test_analyze_preserves_group_key_provenance():
    inner = RecordingProvider()
    RedactingProvider(inner).analyze(AnalysisPacket(group_key="a" * 64))
    assert inner.seen_packets[0].group_key == "a" * 64


def test_generate_redacts_both_prompts():
    inner = RecordingProvider()
    RedactingProvider(inner).generate(
        system_prompt="Ban la agent. Lien he admin@example.com",
        user_prompt="So dien thoai 0912345678",
    )
    system_seen, user_seen = inner.seen_prompts[0]
    assert "admin@example.com" not in system_seen
    assert "0912345678" not in user_seen


def test_factory_returns_a_redacting_provider(monkeypatch):
    """build_llm là nơi duy nhất provider được tạo, nên nó là nút thắt."""
    from project_sentinel.config import AppConfig
    from project_sentinel.llm.factory import build_llm

    monkeypatch.setenv("LLM_API_KEY", "sk-test-khong-dung-that-0123456789")
    config = AppConfig()
    provider = build_llm(config)
    assert isinstance(provider, RedactingProvider), (
        "build_llm phải bọc provider bằng RedactingProvider, nếu không prompt sẽ rò dữ liệu nhạy cảm"
    )


# ── Tests bổ sung cho 3 điểm cải tiến ─────────────────────────────────────

def test_every_packet_field_is_either_redacted_or_explicitly_exempt():
    """Thêm trường mới vào AnalysisPacket phải là một quyết định có ý thức."""
    names = {f.name for f in fields(AnalysisPacket)}
    assert names >= _UNREDACTED_FIELDS, "có tên trường miễn trừ không còn tồn tại"


def test_every_non_exempt_packet_field_is_actually_redacted():
    """Mọi trường không nằm trong _UNREDACTED_FIELDS đều phải được che khi chứa email."""
    inner = RecordingProvider()
    provider = RedactingProvider(inner)

    test_packet = AnalysisPacket(
        group_key="group_key_provenance",
        finding_group={"email": "fg@example.com"},
        source_evidence=[{"email": "se@example.com"}],
        knowledge_hits=[{"email": "kh@example.com"}],
    )
    provider.analyze(test_packet)
    delivered = inner.seen_packets[0]

    for f in fields(AnalysisPacket):
        if f.name in _UNREDACTED_FIELDS:
            continue
        val_str = str(getattr(delivered, f.name))
        assert "@example.com" not in val_str, f"Trường {f.name} bị sót email: {val_str}"


def test_no_production_module_constructs_the_raw_provider():
    """build_llm là nơi DUY NHẤT được tạo OpenRouterClient — nếu không,
    prompt sẽ rời khỏi hệ thống mà không qua bộ che."""
    root = Path(__file__).resolve().parents[3] / "src" / "project_sentinel"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name in {"factory.py", "openrouter.py"}:
            continue
        if "OpenRouterClient(" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(root)))
    assert not offenders, "phải dùng build_llm(config): " + ", ".join(offenders)


def test_last_redaction_events_merges_same_kind_events():
    """last_redaction_events phải gộp các sự kiện cùng kind thành 1 phần tử với count tổng."""
    inner = RecordingProvider()
    provider = RedactingProvider(inner)

    packet = AnalysisPacket(
        group_key="g",
        finding_group={"a": "a@x.com"},
        source_evidence=[{"b": "b@y.com"}],
        knowledge_hits=[{"c": "c@z.com"}],
    )
    provider.analyze(packet)
    email_events = [e for e in provider.last_redaction_events if e.kind == "email"]
    assert len(email_events) == 1
    assert email_events[0].count == 3


def test_redacting_provider_appends_event_to_events_path(tmp_path):
    from project_sentinel.guardrails.events import count_by_kind, read_events

    events_path = tmp_path / "events.jsonl"
    inner = RecordingProvider()
    provider = RedactingProvider(inner, events_path=str(events_path))

    packet = AnalysisPacket(
        group_key="test-run-123",
        finding_group={"email": "nguyen.van.a@example.com"},
    )
    provider.analyze(packet)

    events = read_events(events_path)
    assert len(events) == 1
    assert events[0]["kind"] == "redaction"
    assert events[0]["run_id"] == "test-run-123"
    assert events[0]["detail"]["counts"]["email"] == 1
    assert count_by_kind(events) == {"redaction": 1}
