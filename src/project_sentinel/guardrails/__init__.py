"""Guardrails: che dữ liệu nhạy cảm, chống prompt injection, cổng phê duyệt."""

from project_sentinel.guardrails.events import (
    EVENT_KINDS,
    append_event,
    count_by_kind,
    read_events,
)
from project_sentinel.guardrails.injection import (
    UNTRUSTED_CLOSE,
    UNTRUSTED_OPEN,
    InjectionMatch,
    InjectionVerdict,
    scan,
    wrap_untrusted,
)
from project_sentinel.guardrails.redaction import (
    RedactionEvent,
    redact,
    redact_structure,
)

__all__ = [
    "RedactionEvent",
    "redact",
    "redact_structure",
    "InjectionMatch",
    "InjectionVerdict",
    "scan",
    "wrap_untrusted",
    "UNTRUSTED_OPEN",
    "UNTRUSTED_CLOSE",
    "EVENT_KINDS",
    "append_event",
    "read_events",
    "count_by_kind",
]
