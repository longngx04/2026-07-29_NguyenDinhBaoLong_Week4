"""Đường DUY NHẤT một request kiểm thử rời khỏi hệ thống.

Mọi request đều phải: qua allowlist, qua rate limiter, đi tới Gateway loopback,
và để lại một dòng audit không chứa API key.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.request_log import log_request
from project_sentinel.probe.http_models import HttpRequest
from project_sentinel.probe.payload_kinds import (
    PAYLOAD_KIND_TO_TYPE,
    payload_value_for,
)
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.rate_limit import ToolRateLimiter
from project_sentinel.probe.transport import BaseTransport, RealTransport

GATEWAY_ORIGIN = "http://127.0.0.1:9080"
API_KEY_HEADER = "X-Sentinel-API-Key"
PAYLOAD_FIELD = "value"
MAX_PREVIEW_BYTES = 512

_DEFAULT_RATE_LIMITER = ToolRateLimiter(requests_per_minute=30, burst=5)


@dataclass(frozen=True)
class ProbeOutcome:
    sent: bool
    status_code: int | None = None
    body_preview: str = ""
    elapsed_ms: float = 0.0
    error_class: str | None = None
    error_reason: str | None = None
    denied_reason: str | None = None


def _preview(body: str) -> str:
    if not body:
        return ""
    return body.encode("utf-8")[:MAX_PREVIEW_BYTES].decode("utf-8", errors="ignore")


def send_probe(
    probe: SafeProbe,
    allowlist: Allowlist,
    api_key: str,
    *,
    transport: BaseTransport | None = None,
    rate_limiter: ToolRateLimiter | None = None,
    log_path: str | None = "artifacts/gateway/requests.log.jsonl",
) -> ProbeOutcome:
    """Gửi một probe đã được duyệt qua Gateway. Không duyệt thì không gửi."""
    request_id = f"req-{uuid.uuid4().hex[:12]}"

    if not allowlist.is_allowed(probe.method, probe.path):
        reason = f"'{probe.method} {probe.path}' không có trong allowlist Gateway."
        if log_path:
            log_request(
                log_path,
                request_id=request_id,
                method=probe.method,
                path=probe.path,
                payload_type=probe.payload_kind,
                status="DENIED",
                policy_decision="DENIED",
                error_class="AllowlistViolation",
                error_reason=reason,
            )
        return ProbeOutcome(sent=False, denied_reason=reason)

    body = None
    if probe.payload_kind is not None:
        if (
            not isinstance(probe.payload_kind, str)
            or probe.payload_kind not in PAYLOAD_KIND_TO_TYPE
        ):
            reason = f"payload_kind không hợp lệ: {probe.payload_kind!r}"
            if log_path:
                log_request(
                    log_path,
                    request_id=request_id,
                    method=probe.method,
                    path=probe.path,
                    status="DENIED",
                    policy_decision="DENIED",
                    error_class="InvalidPayloadKind",
                    error_reason=reason,
                )
            return ProbeOutcome(sent=False, denied_reason=reason)
        body = json.dumps(
            {PAYLOAD_FIELD: payload_value_for(probe.payload_kind)}, ensure_ascii=False
        )

    limiter = rate_limiter if rate_limiter is not None else _DEFAULT_RATE_LIMITER
    limiter.wait()

    active_transport = transport if transport is not None else RealTransport()
    response = active_transport.send_request(
        HttpRequest(
            method=probe.method,
            url=f"{GATEWAY_ORIGIN}{probe.path}",
            headers={API_KEY_HEADER: api_key},
            body=body,
        )
    )

    preview = _preview(response.body)
    if log_path:
        log_request(
            log_path,
            request_id=request_id,
            method=probe.method,
            path=probe.path,
            payload_type=probe.payload_kind,
            status="SENT",
            status_code=response.status_code,
            elapsed_ms=round(response.elapsed_ms, 2),
            response_bytes_observed=response.response_bytes_observed,
            truncated=response.truncated,
            response_preview=preview or None,
            error_class=response.error_class,
            error_reason=response.error_reason,
            policy_decision="ALLOWED",
        )

    return ProbeOutcome(
        sent=True,
        status_code=response.status_code,
        body_preview=preview,
        elapsed_ms=response.elapsed_ms,
        error_class=response.error_class,
        error_reason=response.error_reason,
    )
