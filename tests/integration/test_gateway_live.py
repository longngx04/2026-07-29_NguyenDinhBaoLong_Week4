import os
import pytest
from project_sentinel.gateway.cli import EXIT_BLOCKED, EXIT_OK, main


@pytest.mark.integration
def test_live_gateway_integration(monkeypatch, tmp_path):
    api_key = os.environ.get("SENTINEL_API_KEY")
    if not api_key:
        pytest.skip("SENTINEL_API_KEY environment variable not set")

    log_path = str(tmp_path / "live_gateway.log.jsonl")

    # 1. Allowed Path with valid key -> EXIT_OK (status 200)
    ret_allowed = main(
        [
            "request",
            "--method",
            "GET",
            "--path",
            "/WebGoat/actuator/health",
            "--base-url",
            "http://127.0.0.1:9080",
            "--allowlist",
            "configs/gateway/allowlist.yaml",
            "--log-path",
            log_path,
        ]
    )
    assert ret_allowed == EXIT_OK

    # 2. Path not in allowlist -> EXIT_BLOCKED (status None, local block)
    ret_blocked = main(
        [
            "request",
            "--method",
            "GET",
            "--path",
            "/WebGoat/login",
            "--base-url",
            "http://127.0.0.1:9080",
            "--allowlist",
            "configs/gateway/allowlist.yaml",
            "--log-path",
            log_path,
        ]
    )
    assert ret_blocked == EXIT_BLOCKED
