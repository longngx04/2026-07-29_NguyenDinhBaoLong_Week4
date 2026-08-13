from project_sentinel.verification.models import (
    HttpRequest,
    HttpResponse,
    VerificationCandidate,
    VerificationDecision,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.validators import (
    validate_verification_plan_schema,
    validate_verification_result_schema,
)


def test_verification_candidate_instantiation_and_schema():
    cand = VerificationCandidate(
        candidate_id="cand-1234567890ab",
        analysis_record_id="rec-001",
        group_id="group-001",
        cwe="CWE-89",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_attack",
        template_id="tmpl_attack_post",
        method="POST",
        path="/WebGoat/attack",
        target_field="input",
        payload_type="special_chars",
        reason="SQLi test candidate",
    )

    data = cand.to_dict()
    assert data["candidate_id"] == "cand-1234567890ab"
    assert data["endpoint_id"] == "ep_attack"
    assert data["template_id"] == "tmpl_attack_post"
    assert data["decision"] == "PLANNED"

    validate_verification_plan_schema(data)

    reconstructed = VerificationCandidate.from_dict(data)
    assert reconstructed.candidate_id == cand.candidate_id
    assert reconstructed.endpoint_id == cand.endpoint_id
    assert reconstructed.template_id == cand.template_id


def test_http_request_response_models():
    req = HttpRequest(
        method="POST",
        url="http://127.0.0.1:9080/WebGoat/attack",
        headers={"X-Sentinel-Key": "testkey"},
        body='{"input":"test"}',
    )
    assert req.method == "POST"
    assert req.headers["X-Sentinel-Key"] == "testkey"

    resp = HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body='{"status":"OK"}',
        response_bytes_observed=15,
        truncated=False,
        elapsed_ms=12.5,
    )
    assert resp.status_code == 200
    assert resp.response_bytes_observed == 15
    assert resp.truncated is False
    assert resp.error_class is None


def test_verification_result_with_new_fields_and_schema():
    res = VerificationResult(
        result_id="res-001",
        plan_id="cand-1234567890ab",
        group_id="group-001",
        status=VerificationStatus.VERIFIED_REACHABLE,
        status_code=200,
        evidence="HTTP 200 OK; observed 15 bytes",
        execution_time_ms=12.5,
        response_bytes_observed=15,
        truncated=False,
        error_class=None,
        error_reason=None,
    )

    data = res.to_dict()
    assert data["response_bytes_observed"] == 15
    assert data["truncated"] is False
    assert data["status"] == "VERIFIED_REACHABLE"

    validate_verification_result_schema(data)

    reconstructed = VerificationResult.from_dict(data)
    assert reconstructed.result_id == res.result_id
    assert reconstructed.response_bytes_observed == 15
    assert reconstructed.status == VerificationStatus.VERIFIED_REACHABLE
