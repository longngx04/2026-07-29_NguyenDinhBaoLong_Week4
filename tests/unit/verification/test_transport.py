from project_sentinel.verification.models import HttpRequest
from project_sentinel.verification.transport import MAX_RESPONSE_BYTES, FakeTransport, RealTransport


def test_fake_transport_success():
    transport = FakeTransport(
        status_code=200,
        body='{"status":"UP"}',
        headers={"Content-Type": "application/json"},
    )
    req = HttpRequest(
        method="GET",
        url="http://127.0.0.1:9080/WebGoat/actuator/health",
        headers={"X-Sentinel-Key": "testkey"},
    )
    resp = transport.send_request(req)

    assert resp.status_code == 200
    assert resp.body == '{"status":"UP"}'
    assert resp.response_bytes_observed == len('{"status":"UP"}'.encode("utf-8"))
    assert resp.truncated is False
    assert transport.last_request == req


def test_fake_transport_timeout():
    transport = FakeTransport(should_timeout=True)
    req = HttpRequest(method="GET", url="http://127.0.0.1:9080/WebGoat/actuator/health")
    resp = transport.send_request(req)

    assert resp.status_code is None
    assert resp.error_class == "TimeoutException"
    assert "timed out" in resp.error_reason


def test_fake_transport_truncation():
    large_body = "A" * (MAX_RESPONSE_BYTES + 100)
    transport = FakeTransport(body=large_body)
    req = HttpRequest(method="GET", url="http://127.0.0.1:9080/WebGoat/actuator/health")
    resp = transport.send_request(req)

    assert resp.status_code == 200
    assert resp.truncated is True
    assert len(resp.body) == MAX_RESPONSE_BYTES
    assert resp.response_bytes_observed == len(large_body)


def test_real_transport_connection_refused():
    transport = RealTransport(timeout_s=1.0)
    # Target an unassigned local port to test ConnectionError handling safely
    req = HttpRequest(method="GET", url="http://127.0.0.1:59999/WebGoat/actuator/health")
    resp = transport.send_request(req)

    assert resp.status_code is None
    assert resp.error_class == "ConnectionError"
    assert resp.error_reason is not None
