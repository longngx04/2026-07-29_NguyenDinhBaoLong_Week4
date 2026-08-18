"""Bốn loại payload an toàn đề bài cho phép, ánh xạ sang giá trị thật."""

from __future__ import annotations

from typing import Any

from project_sentinel.gateway.models import SafePayloadType
from project_sentinel.gateway.payloads import SAFE_PAYLOADS

PAYLOAD_KIND_TO_TYPE: dict[str, SafePayloadType] = {
    "long_string": SafePayloadType.LONG_STRING,
    "special_chars": SafePayloadType.SPECIAL_CHARS,
    "empty_value": SafePayloadType.EMPTY_VALUE,
    "wrong_type": SafePayloadType.WRONG_TYPE,
}


def payload_value_for(kind: str) -> Any:
    """Trả về giá trị payload an toàn cho một payload_kind đã được duyệt."""
    return SAFE_PAYLOADS[PAYLOAD_KIND_TO_TYPE[kind]]
