"""The single safe execution path for all Gateway requests."""

from __future__ import annotations

import json
import uuid

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.payloads import SAFE_PAYLOADS
from project_sentinel.gateway.request_log import log_request
from project_sentinel.verification.models import (
    HttpRequest,
    VerificationCandidate,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.policy import validate_candidate_policy
from project_sentinel.verification.rate_limit import ToolRateLimiter
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import BaseTransport

GATEWAY_ORIGIN = "http://127.0.0.1:9080"
API_KEY_HEADER = "X-Sentinel-API-Key"
MAX_REQUEST_BODY_BYTES = 16_384


def _is_gateway_rate_limit(status_code: int | None, headers: dict[str, str]) -> bool:
    if status_code == 429:
        return True
    normalized = {key.casefold(): value.casefold() for key, value in headers.items()}
    return status_code == 503 and normalized.get("x-sentinel-rate-limited") == "true"


def execute_candidate(
    candidate: VerificationCandidate,
    transport: BaseTransport,
    allowlist: Allowlist,
    templates: ProbeTemplateRegistry,
    api_key: str,
    *,
    rate_limiter: ToolRateLimiter | None = None,
    log_path: str | None = "artifacts/gateway/requests.log.jsonl",
) -> VerificationResult:
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    result_id = f"res-{uuid.uuid4().hex[:12]}"
    allowed, denial_reason = validate_candidate_policy(candidate, allowlist, templates)
    if not allowed:
        result = VerificationResult(
            result_id=result_id,
            plan_id=candidate.candidate_id,
            status=VerificationStatus.DENIED,
            evidence=f"Policy denial: {denial_reason}",
            error_class="PolicyViolation",
            error_reason=denial_reason,
        )
        if log_path:
            _log_result(log_path, request_id, candidate, result, "DENIED")
        return result

    template = templates.get(candidate.template_id or "")
    assert template is not None  # guaranteed by policy validation
    body = None
    if template.payload_type is not None and template.target_field is not None:
        payload_value = SAFE_PAYLOADS[template.payload_type]
        body = json.dumps({template.target_field: payload_value}, ensure_ascii=False)
        if len(body.encode("utf-8")) > MAX_REQUEST_BODY_BYTES:
            raise ValueError("Reviewed payload exceeds the Week 4 request body cap")

    if rate_limiter is not None:
        rate_limiter.wait()
    response = transport.send_request(
        HttpRequest(
            method=candidate.method or "",
            url=f"{GATEWAY_ORIGIN}{candidate.path}",
            headers={API_KEY_HEADER: api_key},
            body=body,
        )
    )

    if _is_gateway_rate_limit(response.status_code, response.headers):
        status = VerificationStatus.RATE_LIMITED
        evidence = "Gateway rate limit prevented application observation."
    elif response.status_code in template.expected_statuses:
        status = VerificationStatus.OBSERVED
        evidence = f"Expected HTTP {response.status_code} observed through Gateway."
    elif response.status_code in {401, 403, 405}:
        status = VerificationStatus.DENIED
        evidence = f"Gateway denied the request with HTTP {response.status_code}."
    elif response.status_code is not None and 200 <= response.status_code < 400:
        status = VerificationStatus.REACHABLE
        evidence = f"Unexpected but reachable HTTP {response.status_code} observed through Gateway."
    elif response.status_code is not None:
        status = VerificationStatus.INCONCLUSIVE
        evidence = f"HTTP {response.status_code} did not establish the expected application behavior."
    elif response.error_class == "TimeoutException":
        status = VerificationStatus.UNREACHABLE
        evidence = f"Gateway transport timeout after {response.elapsed_ms}ms."
    else:
        status = VerificationStatus.FAILED
        evidence = f"Transport error ({response.error_class or 'unknown'})."

    result = VerificationResult(
        result_id=result_id,
        plan_id=candidate.candidate_id,
        status=status,
        status_code=response.status_code,
        evidence=evidence,
        execution_time_ms=response.elapsed_ms,
        response_bytes_observed=response.response_bytes_observed,
        truncated=response.truncated,
        error_class=response.error_class,
        error_reason=response.error_reason,
    )
    if log_path:
        _log_result(log_path, request_id, candidate, result, "ALLOWED")
    return result


def _log_result(
    log_path: str,
    request_id: str,
    candidate: VerificationCandidate,
    result: VerificationResult,
    policy_decision: str,
) -> None:
    log_request(
        log_path,
        request_id=request_id,
        candidate_id=candidate.candidate_id,
        objective_id=candidate.objective_id,
        proposal_id=candidate.proposal_id,
        endpoint_id=candidate.endpoint_id,
        template_id=candidate.template_id,
        method=candidate.method,
        path=candidate.path,
        payload_type=candidate.payload_type,
        status=result.status.value if hasattr(result.status, "value") else str(result.status),
        status_code=result.status_code,
        elapsed_ms=round(result.execution_time_ms, 2),
        response_bytes_observed=result.response_bytes_observed,
        truncated=result.truncated,
        error_class=result.error_class,
        error_reason=result.error_reason,
        policy_decision=policy_decision,
    )
