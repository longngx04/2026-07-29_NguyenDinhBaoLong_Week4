"""Model request/response HTTP cho transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class HttpRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


@dataclass
class HttpResponse:
    status_code: Optional[int]
    headers: Dict[str, str]
    body: str
    response_bytes_observed: int
    truncated: bool
    elapsed_ms: float
    error_class: Optional[str] = None
    error_reason: Optional[str] = None
