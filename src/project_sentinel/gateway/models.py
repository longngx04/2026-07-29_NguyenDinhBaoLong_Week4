from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class SafePayloadType(str, Enum):
    LONG_STRING = "long_string"
    SPECIAL_CHARS = "special_chars"
    EMPTY_VALUE = "empty_value"
    WRONG_TYPE = "wrong_type"


class GatewayErrorType(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    FORBIDDEN_BY_ALLOWLIST = "forbidden_by_allowlist"
    HTTP_ERROR = "http_error"


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    status_code: int | None
    body_preview: str | None
    error_type: GatewayErrorType | None
    elapsed_ms: float
