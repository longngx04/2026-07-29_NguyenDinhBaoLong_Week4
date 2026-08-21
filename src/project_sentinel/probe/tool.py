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
from project_sentinel.guardrails.approval import (
    ApprovalDecision,
    request_fingerprint,
    requires_approval,
)
from project_sentinel.guardrails.events import append_event
from project_sentinel.guardrails.redaction import RedactionEvent, redact
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
    redactions: tuple[RedactionEvent, ...] = ()


def _safe_preview(body: str) -> tuple[str, tuple[RedactionEvent, ...]]:
    """Che TOÀN BỘ response rồi mới cắt ngắn, và chỉ trả ra bản đã che.

    Che trước khi cắt là có chủ ý: cắt trước có thể xé đôi một email hay token
    đúng mốc 512 byte, làm mẫu không khớp và một mảnh dữ liệu thật lọt ra.

    Trả về cả danh sách sự kiện vì đây là nơi redaction thật sự xảy ra. Bước
    scrub ghi bằng chứng nhưng nhận được chuỗi đã sạch, nên tự nó không còn
    đếm được gì — số liệu phải đi kèm từ đây.
    """
    if not body:
        return "", ()
    cleaned, events = redact(body)
    preview = cleaned.encode("utf-8")[:MAX_PREVIEW_BYTES].decode(
        "utf-8", errors="ignore"
    )
    return preview, tuple(events)


def send_probe(
    probe: SafeProbe,
    allowlist: Allowlist,
    api_key: str,
    *,
    approval: ApprovalDecision | None = None,
    transport: BaseTransport | None = None,
    rate_limiter: ToolRateLimiter | None = None,
    log_path: str | None = "artifacts/gateway/requests.log.jsonl",
    events_path: str | None = "artifacts/guardrails/events.jsonl",
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
        if events_path:
            append_event(
                events_path,
                run_id=request_id,
                kind="allowlist_block",
                detail={"method": probe.method, "path": probe.path, "reason": reason},
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

    if requires_approval(probe):
        expected = request_fingerprint(probe)
        if approval is None:
            reason = "Request cần được phê duyệt nhưng chưa có quyết định approve hợp lệ."
        elif not approval.approved:
            reason = "Người vận hành đã từ chối request này."
        elif approval.request_fingerprint != expected:
            reason = (
                "Quyết định phê duyệt không khớp với request này "
                "(phiếu duyệt cho một request khác)."
            )
        else:
            reason = None

        if reason is not None:
            if log_path:
                log_request(
                    log_path,
                    request_id=request_id,
                    method=probe.method,
                    path=probe.path,
                    payload_type=probe.payload_kind,
                    status="DENIED",
                    policy_decision="DENIED",
                    error_class="ApprovalRequired",
                    error_reason=reason,
                )
            if events_path:
                append_event(
                    events_path,
                    run_id=request_id,
                    kind="approval",
                    detail={
                        "approved": False,
                        "reason": reason,
                        "method": probe.method,
                        "path": probe.path,
                    },
                )
            return ProbeOutcome(sent=False, denied_reason=reason)

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

    preview, preview_redactions = _safe_preview(response.body)
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

    if events_path and requires_approval(probe):
        append_event(
            events_path,
            run_id=request_id,
            kind="approval",
            detail={
                "approved": True,
                "method": probe.method,
                "path": probe.path,
                "decided_by": approval.decided_by if approval else "none",
            },
        )

    return ProbeOutcome(
        sent=True,
        status_code=response.status_code,
        body_preview=preview,
        elapsed_ms=response.elapsed_ms,
        error_class=response.error_class,
        error_reason=response.error_reason,
        redactions=preview_redactions,
    )
