from io import BytesIO
import time
import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.gateway_client import GATEWAY_ORIGIN, execute_candidate
from project_sentinel.verification.models import HttpRequest, VerificationCandidate, VerificationDecision, VerificationStatus
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import (
    MAX_RESPONSE_BYTES,
    RealTransport,
    _read_bounded,
)


def test_real_transport_enforces_hard_timeout_cap():
    with pytest.raises(ValueError):
        RealTransport(timeout_s=10.1)


def test_real_transport_enforces_positive_timeout():
    with pytest.raises(ValueError):
        RealTransport(timeout_s=0.0)


def test_real_transport_enforces_max_response_bytes_cap():
    with pytest.raises(ValueError):
        RealTransport(max_response_bytes=MAX_RESPONSE_BYTES + 1)


def test_bounded_reader_never_reads_more_than_cap_plus_one():
    assert len(_read_bounded(BytesIO(b"A" * 100), 10)) == 11


def test_real_transport_connection_failure_to_closed_port():
    transport = RealTransport(timeout_s=1.0)
    req = HttpRequest(method="GET", url="http://127.0.0.1:9999/health")
    resp = transport.send_request(req)
    assert resp.status_code is None
    assert resp.error_class in {"ConnectionError", "URLError"}


def test_real_transport_timeout_classification(gateway_ready):
    # Let rate limit bucket recharge
    time.sleep(2.0)
    # Microsecond timeout against real running Gateway triggers deterministic TimeoutException and UNREACHABLE
    transport = RealTransport(timeout_s=0.00001)
    allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
    templates = ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")
    cand = VerificationCandidate(
        "cand-timeout", "obj-1", "prop-1",
        VerificationDecision.PLANNED, "ep_health", "tmpl_health_get", "GET",
        "/WebGoat/actuator/health",
    )
    result = execute_candidate(cand, transport, allowlist, templates, gateway_ready)
    assert result.status is VerificationStatus.UNREACHABLE
    assert result.error_class == "TimeoutException"


def test_real_transport_response_truncation(gateway_ready):
    # Set tiny response cap of 16 bytes
    transport = RealTransport(timeout_s=5.0, max_response_bytes=16)
    req = HttpRequest(
        method="GET",
        url=f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
        headers={"X-Sentinel-API-Key": gateway_ready}
    )
    resp = transport.send_request(req)
    assert resp.status_code in {200, 429}
    assert resp.truncated is True
    assert len(resp.body) <= 16


def test_real_transport_does_not_follow_redirects(gateway_ready):
    # Let rate limit bucket recharge
    time.sleep(2.0)
    # GET /WebGoat/attack returns 302 redirecting to /WebGoat/login in WebGoat
    transport = RealTransport(timeout_s=5.0)
    req = HttpRequest(
        method="GET",
        url=f"{GATEWAY_ORIGIN}/WebGoat/attack",
        headers={"X-Sentinel-API-Key": gateway_ready}
    )
    resp = transport.send_request(req)
    assert resp.status_code == 302
    location = resp.headers.get("Location") or resp.headers.get("location")
    assert location is not None
    assert "/WebGoat/login" in location
