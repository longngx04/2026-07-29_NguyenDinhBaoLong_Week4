import httpx
import respx
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.client import GatewayClient


def _make_allowlist(tmp_path):
    config = tmp_path / "allowlist.yaml"
    config.write_text(
        "allowlist:\n"
        "  - method: GET\n"
        "    path: /WebGoat/actuator/health\n"
        "    match: exact\n",
        encoding="utf-8",
    )
    return Allowlist.from_yaml(str(config))


@respx.mock
def test_log_redaction_ok_response(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "redaction_test.log.jsonl"
    secret_marker = "SENTINEL_TEST_MARKER_SECRET_9999"

    respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").respond(
        status_code=200, text="OK"
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key=secret_marker,
        allowlist=allowlist,
        log_path=str(log_file),
    )
    client.request("GET", "/WebGoat/actuator/health")

    log_content = log_file.read_text(encoding="utf-8")
    assert secret_marker not in log_content


@respx.mock
def test_log_redaction_timeout_response(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "redaction_test.log.jsonl"
    secret_marker = "SENTINEL_TEST_MARKER_SECRET_9999"

    respx.get("http://127.0.0.1:9080/WebGoat/actuator/health").side_effect = (
        httpx.TimeoutException("Timeout")
    )

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key=secret_marker,
        allowlist=allowlist,
        log_path=str(log_file),
    )
    client.request("GET", "/WebGoat/actuator/health")

    log_content = log_file.read_text(encoding="utf-8")
    assert secret_marker not in log_content


@respx.mock
def test_log_redaction_forbidden_response(tmp_path):
    allowlist = _make_allowlist(tmp_path)
    log_file = tmp_path / "redaction_test.log.jsonl"
    secret_marker = "SENTINEL_TEST_MARKER_SECRET_9999"

    client = GatewayClient(
        base_url="http://127.0.0.1:9080",
        api_key=secret_marker,
        allowlist=allowlist,
        log_path=str(log_file),
    )
    client.request("GET", "/WebGoat/login")

    log_content = log_file.read_text(encoding="utf-8")
    assert secret_marker not in log_content
