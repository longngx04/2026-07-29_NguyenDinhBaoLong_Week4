from io import BytesIO
import time
import pytest

from project_sentinel.probe.http_models import HttpRequest
from project_sentinel.probe.tool import GATEWAY_ORIGIN, TEMPLATE_HEADER
from project_sentinel.probe.transport import (
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
    req = HttpRequest(method="GET", url="http://127.0.0.1:59999/health")
    resp = transport.send_request(req)
    assert resp.status_code is None
    assert resp.error_class in {"ConnectionError", "URLError"}


# Gateway nay enforce ca template chu khong chi API key. Ba test duoi day do
# HANH VI TRANSPORT (timeout, cat response, khong di theo redirect), nen chung
# phai gui mot request HOP LE — mot request bi policy chan se do vi ly do khac
# va khong con do duoc thu can do.
@pytest.mark.live_gateway
def test_real_transport_timeout_classification(gateway_ready):
    # Let rate limit bucket recharge
    time.sleep(2.0)
    # Microsecond timeout against real running Gateway triggers deterministic TimeoutException
    transport = RealTransport(timeout_s=0.00001)
    req = HttpRequest(
        method="GET",
        url=f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
        headers={
            "X-Sentinel-API-Key": gateway_ready,
            TEMPLATE_HEADER: "tmpl_health_get",
        },
    )
    resp = transport.send_request(req)
    assert resp.status_code is None
    assert resp.error_class == "TimeoutException"


@pytest.mark.live_gateway
def test_real_transport_response_truncation(gateway_ready):
    # Set tiny response cap of 16 bytes
    transport = RealTransport(timeout_s=5.0, max_response_bytes=16)
    req = HttpRequest(
        method="GET",
        url=f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
        headers={
            "X-Sentinel-API-Key": gateway_ready,
            TEMPLATE_HEADER: "tmpl_health_get",
        },
    )
    resp = transport.send_request(req)
    assert resp.status_code in {200, 429}
    assert resp.truncated is True
    assert len(resp.body) <= 16


@pytest.mark.live_gateway
def test_real_transport_does_not_follow_redirects(gateway_ready):
    # Let rate limit bucket recharge
    time.sleep(2.0)
    # GET /WebGoat/attack returns 302 redirecting to /WebGoat/login in WebGoat
    transport = RealTransport(timeout_s=5.0)
    req = HttpRequest(
        method="GET",
        url=f"{GATEWAY_ORIGIN}/WebGoat/attack",
        headers={
            "X-Sentinel-API-Key": gateway_ready,
            TEMPLATE_HEADER: "tmpl_attack_get",
        },
    )
    resp = transport.send_request(req)
    assert resp.status_code == 302
    location = resp.headers.get("Location") or resp.headers.get("location")
    assert location is not None
    assert "/WebGoat/login" in location
