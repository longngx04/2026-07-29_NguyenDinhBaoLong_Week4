from __future__ import annotations
from typing import Any
from .models import SafePayloadType

SAFE_PAYLOADS: dict[SafePayloadType, Any] = {
    SafePayloadType.LONG_STRING: "A" * 5000,
    SafePayloadType.SPECIAL_CHARS: "!@#$%^&*()'\"<>;",
    SafePayloadType.EMPTY_VALUE: "",
    SafePayloadType.WRONG_TYPE: 12345,
}
