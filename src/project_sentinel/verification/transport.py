"""Compatibility shim until Task 12 deletes verification package."""
from project_sentinel.probe.transport import (  # noqa: F401
    BaseTransport,
    RealTransport,
    MAX_RESPONSE_BYTES,
    MAX_TIMEOUT_SECONDS,
    _read_bounded,
)
