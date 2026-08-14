from __future__ import annotations
from enum import Enum


class SafePayloadType(str, Enum):
    LONG_STRING = "long_string"
    SPECIAL_CHARS = "special_chars"
    EMPTY_VALUE = "empty_value"
    WRONG_TYPE = "wrong_type"
