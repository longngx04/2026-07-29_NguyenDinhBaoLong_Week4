"""Che dữ liệu nhạy cảm trước khi gửi tới LLM hoặc ghi vào log.

Thứ tự các mẫu có ý nghĩa: mẫu hẹp chạy trước mẫu rộng, để một JWT không bị
mẫu hex bắt mất trước.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Các khoá là bằng chứng provenance (pipeline analysis & gateway audit), không bao giờ che.
SKIP_KEYS: frozenset[str] = frozenset({
    # Pipeline & Analysis provenance
    "prompt_sha256",
    "analysis_id",
    "run_id",
    "group_key",
    # Gateway audit log provenance
    "request_id",
    "candidate_id",
    "objective_id",
    "proposal_id",
    "endpoint_id",
    "template_id",
})

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "password",
        re.compile(
            r"""(?i)(\"?\b(?:password|passwd|pwd|pass)\"?\s*:\s*)(?!\[REDACTED_)("[^"]*"|'[^']*'|[^\s&,};)]+)"""
        ),
        r"\1[REDACTED_PASSWORD]",
    ),
    (
        "password",
        re.compile(
            r"""(?i)(\"?\b(?:password|passwd|pwd|pass)\"?\s*=\s*)(?!\[REDACTED_)("[^"]*"|'[^']*'|[^\r\n&,};)]+)"""
        ),
        r"\1[REDACTED_PASSWORD]",
    ),
    (
        "token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}"),
        "[REDACTED_TOKEN]",
    ),
    (
        "api_key",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,})\b"
        ),
        "[REDACTED_API_KEY]",
    ),
    (
        "api_key",
        re.compile(
            r"""(?i)(\b(?:api[_-]?key|secret|token|passwd|SENTINEL_GATEWAY_API_KEY|key)\b\s*[:= ]\s*["']?)[A-Fa-f0-9]{32,}(["']?)"""
        ),
        r"\1[REDACTED_API_KEY]\2",
    ),
    (
        "email",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        "pii",
        re.compile(r"\b(?:\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}|0\d{11})\b"),
        "[REDACTED_PII]",
    ),
    (
        "phone",
        re.compile(r"(?:\+84|(?:\b84)|\b0)(?:[\s-]?\d){9}\b"),
        "[REDACTED_PHONE]",
    ),
]


@dataclass(frozen=True)
class RedactionEvent:
    kind: str
    count: int


def redact(text: str) -> tuple[str, list[RedactionEvent]]:
    """Che mọi dữ liệu nhạy cảm trong một chuỗi."""
    if not isinstance(text, str) or not text:
        return text, []

    result = text
    events: list[RedactionEvent] = []
    for kind, pattern, replacement in _PATTERNS:
        result, count = pattern.subn(replacement, result)
        if count:
            events.append(RedactionEvent(kind=kind, count=count))
    return result, _merge(events)


def redact_structure(
    value: Any, skip_keys: frozenset[str] = SKIP_KEYS
) -> tuple[Any, list[RedactionEvent]]:
    """Che đệ quy mọi chuỗi trong một cấu trúc dict/list/tuple/set lồng nhau."""
    events: list[RedactionEvent] = []
    seen: set[int] = set()

    def walk(node: Any, key: str | None = None) -> Any:
        if (
            key is not None
            and key in skip_keys
            and not isinstance(node, (dict, list, tuple, set))
        ):
            return node

        if isinstance(node, str):
            cleaned, found = redact(node)
            events.extend(found)
            return cleaned

        if isinstance(node, (dict, list, tuple, set)):
            node_id = id(node)
            if node_id in seen:
                return "[CYCLE]"
            seen.add(node_id)
            try:
                if isinstance(node, dict):
                    return {name: walk(item, name) for name, item in node.items()}
                if isinstance(node, list):
                    return [walk(item) for item in node]
                if isinstance(node, tuple):
                    return tuple(walk(item) for item in node)
                if isinstance(node, set):
                    return {walk(item) for item in node}
            finally:
                seen.remove(node_id)

        return node

    return walk(value), _merge(events)


def merge_events(events: list[RedactionEvent]) -> list[RedactionEvent]:
    """Gộp các sự kiện cùng loại thành một dòng tổng.

    Công khai vì redaction xảy ra ở cửa ra (`send_probe`) nhưng bằng chứng lại
    được ghi ở bước scrub — bước đó phải cộng được số liệu của cả hai chặng.
    """
    totals: dict[str, int] = {}
    for event in events:
        totals[event.kind] = totals.get(event.kind, 0) + event.count
    return [RedactionEvent(kind=kind, count=count) for kind, count in totals.items()]


_merge = merge_events
