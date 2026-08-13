"""
Verification Gateway Client executing candidates via Policy Validation and Transport abstraction.
"""

import json
import uuid
from typing import Optional

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.models import GatewayErrorType
from project_sentinel.gateway.payloads import SAFE_PAYLOADS
from project_sentinel.gateway.request_log import log_request
from project_sentinel.verification.models import (
    HttpRequest,
    VerificationCandidate,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.policy import validate_candidate_policy
from project_sentinel.verification.transport import BaseTransport


def execute_candidate(
    candidate: VerificationCandidate,
    transport: BaseTransport,
    allowlist: Allowlist,
    api_key: str,
    base_url: str = "http://127.0.0.1:9080",
    log_path: Optional[str] = "artifacts/gateway/requests.log.jsonl",
) -> VerificationResult:
    """Execute a VerificationCandidate through policy validation and transport.
    
    Returns a structured VerificationResult with response metadata, truncation indicator,
    and sanitized error details without leaking secrets or tracebacks.
    """
    result_id = f"res-{uuid.uuid4().hex[:12]}"
    
    # 1. Policy Validation (Deny-by-Default)
    allowed, denial_reason = validate_candidate_policy(candidate, allowlist)
    if not allowed:
        if log_path:
            log_request(
                log_path,
                candidate.method,
                candidate.path,
                candidate.payload_type,
                None,
                GatewayErrorType.FORBIDDEN_BY_ALLOWLIST,
                0.0,
            )
        return VerificationResult(
            result_id=result_id,
            plan_id=candidate.candidate_id,
            group_id=candidate.group_id,
            status=VerificationStatus.DENIED,
            status_code=None,
            evidence=f"Policy denial: {denial_reason}",
            execution_time_ms=0.0,
            response_bytes_observed=0,
            truncated=False,
            error_class="PolicyViolation",
            error_reason=denial_reason,
        )

    # 2. Build HttpRequest with API Key headers
    target_url = f"{base_url.rstrip('/')}{candidate.path}"
    headers = {
        "X-Sentinel-Key": api_key,
        "X-Sentinel-API-Key": api_key,
    }
    
    body: Optional[str] = None
    if candidate.payload_type and candidate.target_field:
        try:
            payload_val = SAFE_PAYLOADS.get(candidate.payload_type, "")
            body = json.dumps({candidate.target_field: payload_val}, ensure_ascii=False)
        except Exception:
            body = None

    req = HttpRequest(
        method=candidate.method,
        url=target_url,
        headers=headers,
        body=body,
    )

    # 3. Transport Execution
    response = transport.send_request(req)

    # 4. Log request safely (No headers/secrets logged)
    if log_path:
        error_enum = None
        if response.error_class == "TimeoutException":
            error_enum = GatewayErrorType.TIMEOUT
        elif response.error_class in ("ConnectionError", "HTTPError"):
            error_enum = GatewayErrorType.CONNECTION
            
        log_request(
            log_path,
            candidate.method,
            candidate.path,
            candidate.payload_type,
            response.status_code,
            error_enum,
            response.elapsed_ms,
        )

    # 5. Evaluate VerificationStatus
    if response.status_code == 200:
        status = VerificationStatus.VERIFIED_REACHABLE
        evidence = f"HTTP 200 OK; observed {response.response_bytes_observed} bytes (truncated={response.truncated})."
    elif response.status_code is not None:
        status = VerificationStatus.OBSERVED
        evidence = f"HTTP {response.status_code} observed from Gateway."
    elif response.error_class == "TimeoutException":
        status = VerificationStatus.UNREACHABLE
        evidence = f"Gateway transport timeout after {response.elapsed_ms}ms."
    else:
        status = VerificationStatus.FAILED
        evidence = f"Transport error ({response.error_class}): {response.error_reason or 'Execution failed'}"

    return VerificationResult(
        result_id=result_id,
        plan_id=candidate.candidate_id,
        group_id=candidate.group_id,
        status=status,
        status_code=response.status_code,
        evidence=evidence,
        execution_time_ms=response.elapsed_ms,
        response_bytes_observed=response.response_bytes_observed,
        truncated=response.truncated,
        error_class=response.error_class,
        error_reason=response.error_reason,
    )
