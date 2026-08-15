import json
import time
from pathlib import Path
import pytest
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import (
    _bounded_response_preview,
    execute_candidate,
)
from project_sentinel.verification.models import VerificationCandidate, VerificationDecision, VerificationStatus
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import RealTransport


def _configs():
    return Allowlist.from_json("configs/gateway/endpoint-allowlist.json"), ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")


def _candidate():
    return VerificationCandidate(
        "cand-1", "obj-1", "prop-1",
        VerificationDecision.PLANNED, "ep_health", "tmpl_health_get", "GET",
        "/WebGoat/actuator/health",
    )


def test_response_preview_is_bounded_by_utf8_bytes():
    preview = _bounded_response_preview("é" * 512)

    assert preview is not None
    assert len(preview.encode("utf-8")) <= 512


def test_policy_denial_returns_denied_without_network_call(tmp_path, gateway_ready, gateway_access_log_tracker):
    candidate = _candidate()
    candidate.path = "/WebGoat/disallowed"

    logs_before = gateway_access_log_tracker()
    result = execute_candidate(candidate, RealTransport(), *_configs(), gateway_ready, log_path=str(tmp_path / "audit.jsonl"))
    logs_after = gateway_access_log_tracker()

    assert result.status is VerificationStatus.DENIED
    assert result.status_code is None
    # Boundary proof (D11): Nginx access log gained 0 entries
    assert logs_after == logs_before


@pytest.mark.parametrize("header_name", ["Authorization", "Cookie", "Host", "X-Sentinel-API-Key", "Connection", "X-Forwarded-Host"])
def test_policy_denies_restricted_headers_without_network_call(header_name, tmp_path, gateway_ready, gateway_access_log_tracker):
    candidate = _candidate()
    candidate.headers = {header_name: "malicious_or_restricted_value"}

    logs_before = gateway_access_log_tracker()
    result = execute_candidate(candidate, RealTransport(), *_configs(), gateway_ready, log_path=str(tmp_path / "audit.jsonl"))
    logs_after = gateway_access_log_tracker()

    assert result.status is VerificationStatus.DENIED
    assert result.status_code is None
    assert "Restricted header" in result.evidence
    # Boundary proof (D11): Nginx access log gained 0 entries
    assert logs_after == logs_before


@pytest.mark.parametrize("headers,expected_reason_substr", [
    ({"Accept": "application/xml"}, "not in reviewed allowed values"),
    ({"X-Custom-Header": "custom"}, "not in reviewed allowed_request_headers"),
    ({"Accept": "application/json\r\nEvil: true"}, "contains newline character"),
])
def test_policy_denies_unreviewed_headers_and_values(headers, expected_reason_substr, tmp_path, gateway_ready, gateway_access_log_tracker):
    candidate = _candidate()
    candidate.headers = headers

    logs_before = gateway_access_log_tracker()
    result = execute_candidate(candidate, RealTransport(), *_configs(), gateway_ready, log_path=str(tmp_path / "audit.jsonl"))
    logs_after = gateway_access_log_tracker()

    assert result.status is VerificationStatus.DENIED
    assert result.status_code is None
    assert expected_reason_substr in result.evidence
    # Boundary proof (D11): Nginx access log gained 0 entries
    assert logs_after == logs_before


def test_not_plannable_candidate_returns_denied(tmp_path, gateway_ready, gateway_access_log_tracker):
    candidate = VerificationCandidate(
        "cand-2", "obj-2", "prop-2",
        VerificationDecision.NOT_PLANNABLE,
        reason="Endpoint not found in catalog",
    )

    logs_before = gateway_access_log_tracker()
    result = execute_candidate(candidate, RealTransport(), *_configs(), gateway_ready, log_path=str(tmp_path / "audit.jsonl"))
    logs_after = gateway_access_log_tracker()

    assert result.status is VerificationStatus.DENIED
    assert result.status_code is None
    # Boundary proof (D11): Nginx access log gained 0 entries
    assert logs_after == logs_before


def test_execute_planned_health_get_live(tmp_path, gateway_ready):
    # Let rate limit recharge
    time.sleep(2.0)
    candidate = _candidate()
    candidate.headers = {"Accept": "application/json", "User-Agent": "Sentinel-SafeProbe/1.0"}
    audit_file = tmp_path / "audit.jsonl"

    result = execute_candidate(candidate, RealTransport(timeout_s=5.0), *_configs(), gateway_ready, log_path=str(audit_file))

    assert result.status in {VerificationStatus.OBSERVED, VerificationStatus.REACHABLE}
    assert result.status_code == 200
    assert result.response_preview is not None
    assert len(result.response_preview.encode("utf-8")) <= 512
    assert "UP" in result.response_preview

    # Verify audit log contains response preview and does NOT leak secrets or header maps
    audit_content = audit_file.read_text(encoding="utf-8")
    assert gateway_ready not in audit_content
    log_rec = json.loads(audit_content.strip())
    assert log_rec["endpoint_id"] == "ep_health"
    assert log_rec["status_code"] == 200
    assert "headers" not in log_rec
    assert "api_key" not in log_rec
    assert log_rec["response_preview"] == result.response_preview


def test_positive_control_valid_request_increases_gateway_log(tmp_path, gateway_ready, gateway_access_log_tracker):
    time.sleep(1.0)
    candidate = _candidate()
    candidate.headers = {"Accept": "application/json"}
    audit_file = tmp_path / "audit.jsonl"

    logs_before = gateway_access_log_tracker()
    result = execute_candidate(candidate, RealTransport(timeout_s=5.0), *_configs(), gateway_ready, log_path=str(audit_file))
    logs_after = gateway_access_log_tracker()

    assert result.status_code == 200
    assert logs_after > logs_before
