"""Coi mọi nội dung lấy từ ứng dụng là không đáng tin.

scan() là TÍN HIỆU cảnh báo, KHÔNG phải ranh giới an ninh. Ranh giới thật là
allowlist khớp chính xác trong probe/tool.py. Không được dùng verdict == "clean"
làm điều kiện cho phép gửi request.

Hai tầng:
  1. Cấu trúc  — bọc nội dung trong thẻ và gắn nhãn dữ liệu, không phải chỉ dẫn.
  2. Phát hiện — quét mẫu chỉ dẫn, cắt bỏ đoạn khớp trước khi vào prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

UNTRUSTED_OPEN = "<untrusted_app_response>"
UNTRUSTED_CLOSE = "</untrusted_app_response>"

MAX_EXCERPT_CHARS = 120

_FORGED_TAG = re.compile(r"(?i)<\s*/?\s*untrusted_app_response\s*>")

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_previous", re.compile(r"(?i)(?:please\s+)?ignore\s+(?:all\s+|the\s+|any\s+)?(?:previous|prior)\s+instructions?")),
    ("ignore_previous_vi", re.compile(r"(?i)b(?:ỏ|o)\s+qua\s+(?:c(?:á|a)c\s+)?h(?:ư|u)(?:ớ|o)ng\s+d(?:ẫ|a)n")),
    ("disregard", re.compile(r"(?i)disregard\s+(?:the\s+)?(?:above|prior|previous)")),
    ("reveal_prompt", re.compile(r"(?i)(?:reveal|show|print|repeat)\s+(?:your\s+)?(?:system\s+)?prompt")),
    ("reveal_secret", re.compile(r"(?i)(?:reveal|show|print)\s+(?:your\s+)?(?:api[_ ]?key|secret|token)")),
    ("role_marker", re.compile(r"(?im)^\s*(?:system|assistant|developer)\s*:\s*(?:you\s+are|you're|bạn\s+là|b(?:ỏ|o)\s+qua|b(?:ạ|a)n\s+gi(?:ờ|o)\s+l(?:à|a)|ignore|new\s+instructions|\n)")),
    ("you_are_now", re.compile(r"(?i)(?:you\s+are\s+now|you're\s+now|from\s+now\s+on\s+you\s+are)\s+")),
    ("new_instructions", re.compile(r"(?i)new\s+instructions?\s*:")),
    ("tool_call", re.compile(r"(?im)^\s*(?:you\s+must\s+|please\s+)?(?:call|invoke|execute)\s+(?:the\s+)?(?:tool|function|endpoint)\b")),
    ("external_url_instruction", re.compile(r"(?i)\b(?:call|fetch|request|send|post|get|visit|browse)\s+(?:to\s+)?https?://(?!127\.0\.0\.1|localhost)[\w.-]+")),
    ("exfiltrate_to_url", re.compile(r"(?i)\b(?:send|post|upload|leak|exfiltrate|forward)\b[^\n]{0,80}?\b(?:api[_ -]?key|access[_ -]?token|token|secret|password|credential|system\s+prompt)\b[^\n]{0,80}?\bhttps?://(?!127\.0\.0\.1|localhost)[\w.-]+")),
]


@dataclass(frozen=True)
class InjectionMatch:
    pattern_name: str
    excerpt: str


@dataclass(frozen=True)
class InjectionVerdict:
    verdict: str
    matches: tuple[InjectionMatch, ...]
    sanitized_text: str


def scan(text: str) -> InjectionVerdict:
    """Quét nội dung không đáng tin, trả phán quyết và bản đã cắt bỏ."""
    if not isinstance(text, str) or not text:
        return InjectionVerdict(verdict="clean", matches=(), sanitized_text=text or "")

    matches: list[InjectionMatch] = []
    spans: list[tuple[int, int]] = []

    for name, pattern in _PATTERNS:
        for found in pattern.finditer(text):
            start = max(0, found.start() - 20)
            end = min(len(text), found.end() + 20)
            matches.append(
                InjectionMatch(
                    pattern_name=name,
                    excerpt=text[start:end][:MAX_EXCERPT_CHARS],
                )
            )
            spans.append((found.start(), found.end()))

    if not matches:
        return InjectionVerdict(verdict="clean", matches=(), sanitized_text=text)

    sanitized = _remove_spans(text, spans)
    return InjectionVerdict(
        verdict="suspicious", matches=tuple(matches), sanitized_text=sanitized
    )


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Cắt bỏ các đoạn khớp, gộp phần chồng lấn."""
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    result: list[str] = []
    cursor = 0
    for start, end in merged:
        result.append(text[cursor:start])
        result.append("[REMOVED_INJECTION_ATTEMPT]")
        cursor = end
    result.append(text[cursor:])
    return "".join(result)


def wrap_untrusted(text: str) -> str:
    """Bọc nội dung trong thẻ, vô hiệu hoá thẻ đóng/mở giả bên trong."""
    neutralised = _FORGED_TAG.sub("[neutralised_tag]", text or "")
    return f"{UNTRUSTED_OPEN}\n{neutralised}\n{UNTRUSTED_CLOSE}"
