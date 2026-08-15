import jsonschema
import pytest

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
        objective_id="obj-001",
        proposal_id="prop-001",
        decision=VerificationDecision.PLANNED,
        endpoint_id="ep_attack",
        template_id="tmpl_attack_post_empty",
        method="POST",
        path="/WebGoat/attack",
        target_field="input",
        payload_type="empty_value",
        reason="SQLi test candidate",
    )

    data = cand.to_dict()
    assert data["candidate_id"] == "cand-1234567890ab"
    assert data["objective_id"] == "obj-001"
    assert data["proposal_id"] == "prop-001"
    assert data["endpoint_id"] == "ep_attack"
    assert data["template_id"] == "tmpl_attack_post_empty"
    assert data["decision"] == "PLANNED"

    validate_verification_plan_schema(data)

    reconstructed = VerificationCandidate.from_dict(data)
    assert reconstructed.candidate_id == cand.candidate_id
    assert reconstructed.objective_id == cand.objective_id
    assert reconstructed.proposal_id == cand.proposal_id
    assert reconstructed.endpoint_id == cand.endpoint_id
    assert reconstructed.template_id == cand.template_id


def test_http_request_response_models():
    req = HttpRequest(
        method="POST",
        url="http://127.0.0.1:9080/WebGoat/attack",
        headers={"X-Sentinel-API-Key": "testkey"},
        body='{"input":"test"}',
    )
    assert req.method == "POST"
    assert req.headers["X-Sentinel-API-Key"] == "testkey"

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
        status=VerificationStatus.OBSERVED,
        status_code=200,
        evidence="HTTP 200 OK; observed 15 bytes",
        execution_time_ms=12.5,
        response_bytes_observed=15,
        truncated=False,
        response_preview='{"status":"OK"}',
        error_class=None,
        error_reason=None,
    )

    data = res.to_dict()
    assert data["response_bytes_observed"] == 15
    assert data["truncated"] is False
    assert data["status"] == "OBSERVED"
    assert data["response_preview"] == '{"status":"OK"}'

    validate_verification_result_schema(data)

    reconstructed = VerificationResult.from_dict(data)
    assert reconstructed.result_id == res.result_id
    assert reconstructed.response_bytes_observed == 15
    assert reconstructed.response_preview == '{"status":"OK"}'
    assert reconstructed.status == VerificationStatus.OBSERVED


def test_verification_result_schema_requires_response_contract_fields():
    incomplete = {
        "result_id": "res-001",
        "plan_id": "cand-001",
        "status": "OBSERVED",
        "evidence": "HTTP 200 observed",
        "execution_time_ms": 1.0,
    }

    with pytest.raises(jsonschema.ValidationError):
        validate_verification_result_schema(incomplete)


def test_probe_multi_run_jsonl_append(tmp_path):
    import json
    from project_sentinel.cli import _append_jsonl_atomic
    target_file = tmp_path / "probe-results.jsonl"
    r1 = {"result_id": "res-1", "status": "OBSERVED"}
    r2 = {"result_id": "res-2", "status": "REACHABLE"}
    _append_jsonl_atomic(r1, target_file)
    _append_jsonl_atomic(r2, target_file)

    lines = target_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["result_id"] == "res-1"
    assert json.loads(lines[1])["result_id"] == "res-2"
