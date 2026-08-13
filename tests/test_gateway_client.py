import httpx
import respx
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.client import GatewayClient
from project_sentinel.gateway.models import GatewayErrorType, SafePayloadType


def _make_allowlist(tmp_path):
    config = tmp_path / "allowlist.yaml"
    config.write_text(
        "allowlist:\n"
        "  - method: GET\n"
        "    path: /WebGoat/actuator/health\n"
        "    match: exact\n"
        "  - method: POST\n"
        "    path: /WebGoat/attack\n"
        "    match: prefix\n",
        encoding="utf-8",
    )
    return Allowlist.from_yaml(str(config))


@respx.mock
def test_gateway_client_request_200_ok(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "requests.log.jsonl"
    route = respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").respond(
        status_code=200, text='{"status":"UP"}'
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key="test-api-key",
        allowlist=allowlist,
        log_path=str(log_file),
    )
    result = client.request("GET", "/WebGoat/actuator/health")

    assert result.ok is True
    assert result.status_code == 200
    assert result.body_preview == '{"status":"UP"}'
    assert result.error_type is None
    assert route.called is True


@respx.mock
def test_gateway_client_response_truncation(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "requests.log.jsonl"
    large_body = "X" * 100
    respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").respond(
        status_code=200, text=large_body
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key="test-api-key",
        allowlist=allowlist,
        log_path=str(log_file),
        max_response_bytes=10,
    )
    result = client.request("GET", "/WebGoat/actuator/health")

    assert result.ok is True
    assert result.status_code == 200
    assert len(result.body_preview) == 10
    assert result.body_preview == "X" * 10


@respx.mock
def test_gateway_client_timeout_exception(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "requests.log.jsonl"
    respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").side_effect = (
        httpx.TimeoutException("Connection timed out")
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key="test-api-key",
        allowlist=allowlist,
        log_path=str(log_file),
    )
    result = client.request("GET", "/WebGoat/actuator/health")

    assert result.ok is False
    assert result.status_code is None
    assert result.error_type == GatewayErrorType.TIMEOUT


@respx.mock
def test_gateway_client_connect_error_exception(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "requests.log.jsonl"
    respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").side_effect = (
        httpx.ConnectError("Failed to connect")
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key="test-api-key",
        allowlist=allowlist,
        log_path=str(log_file),
    )
    result = client.request("GET", "/WebGoat/actuator/health")

    assert result.ok is False
    assert result.status_code is None
    assert result.error_type == GatewayErrorType.CONNECTION


@respx.mock
def test_gateway_client_forbidden_by_allowlist_local_block(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "requests.log.jsonl"
    route = respx.get("http://127.0.0.1:9080/WebGoat/login").respond(status_code=200)

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key="test-api-key",
        allowlist=allowlist,
        log_path=str(log_file),
    )
    result = client.request("GET", "/WebGoat/login")

    assert result.ok is False
    assert result.status_code is None
    assert result.error_type == GatewayErrorType.FORBIDDEN_BY_ALLOWLIST
    # Critical check: Network route must NEVER be called if blocked by allowlist
    assert route.called is False
