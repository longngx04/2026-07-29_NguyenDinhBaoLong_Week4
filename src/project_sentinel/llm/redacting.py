"""Nút thắt cổ chai: mọi prompt rời khỏi hệ thống đều bị che trước.

Bọc quanh một LLMProvider bất kỳ và giữ nguyên giao diện, nên chỗ gọi không
cần biết nó tồn tại — và cũng không thể quên gọi nó.
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, Optional

from project_sentinel.guardrails.events import append_event
from project_sentinel.guardrails.redaction import _merge, redact, redact_structure
from project_sentinel.llm.base import AnalysisPacket, LLMProvider, LLMResult

# Các trường không che: hằng số cấu hình và provenance.
_UNREDACTED_FIELDS: frozenset[str] = frozenset({
    "group_key",        # provenance, phải giữ nguyên
    "task",             # chuỗi hằng do packet_builder đặt
    "output_language",  # "vi"
    "output_schema",    # đọc từ file schema
    "allowed_endpoints", # đọc từ configs/gateway/endpoint-allowlist.json
})


class RedactingProvider:
    """LLMProvider bọc ngoài, che dữ liệu nhạy cảm trước khi chuyển tiếp."""

    def __init__(
        self,
        inner: LLMProvider,
        events_path: str | None = "artifacts/guardrails/events.jsonl",
    ):
        self._inner = inner
        self.events_path = events_path
        self.last_redaction_events: list = []

    @property
    def inner(self) -> LLMProvider:
        return self._inner

    def analyze(
        self, packet: AnalysisPacket, system_prompt: Optional[str] = None
    ) -> LLMResult:
        cleaned_fields: dict[str, Any] = {}
        all_events = []

        for f in fields(packet):
            val = getattr(packet, f.name)
            if f.name in _UNREDACTED_FIELDS:
                cleaned_fields[f.name] = val
            else:
                cleaned_val, ev = redact_structure(val)
                cleaned_fields[f.name] = cleaned_val
                all_events.extend(ev)

        cleaned_prompt, prompt_events = (
            redact(system_prompt) if system_prompt else (system_prompt, [])
        )
        all_events.extend(prompt_events)

        self.last_redaction_events = _merge(all_events)

        if self.events_path and self.last_redaction_events:
            counts = {e.kind: e.count for e in self.last_redaction_events}
            append_event(
                self.events_path,
                run_id=packet.group_key,
                kind="redaction",
                detail={
                    "counts": counts,
                    "total_redacted": sum(e.count for e in self.last_redaction_events),
                },
            )

        safe_packet = replace(packet, **cleaned_fields)
        return self._inner.analyze(safe_packet, cleaned_prompt)

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        cleaned_system, events_a = redact(system_prompt)
        cleaned_user, events_b = redact(user_prompt)
        self.last_redaction_events = _merge(events_a + events_b)

        if self.events_path and self.last_redaction_events:
            counts = {e.kind: e.count for e in self.last_redaction_events}
            append_event(
                self.events_path,
                run_id="generate",
                kind="redaction",
                detail={
                    "counts": counts,
                    "total_redacted": sum(e.count for e in self.last_redaction_events),
                },
            )

        return self._inner.generate(
            system_prompt=cleaned_system, user_prompt=cleaned_user
        )
