from unittest.mock import patch
from project_sentinel.gateway.cli import (
    EXIT_BLOCKED,
    EXIT_CONFIG_ERROR,
    EXIT_NETWORK_ERROR,
    EXIT_OK,
    main,
)
from project_sentinel.gateway.models import GatewayErrorType, GatewayResult


def test_cli_missing_api_key(monkeypatch):
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    exit_code = main(["request", "--method", "GET", "--path", "/WebGoat/actuator/health"])
    assert exit_code == EXIT_CONFIG_ERROR


def test_cli_missing_allowlist_file(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    missing_file = str(tmp_path / "non_existent_allowlist.yaml")
    exit_code = main(
        [
            "request",
            "--method",
            "GET",
            "--path",
            "/WebGoat/actuator/health",
            "--allowlist",
            missing_file,
        ]
    )
    assert exit_code == EXIT_CONFIG_ERROR


def test_cli_forbidden_by_allowlist(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    allowlist_file = tmp_path / "allowlist.yaml"
    allowlist_file.write_text(
        "allowlist:\n  - method: GET\n    path: /WebGoat/actuator/health\n    match: exact\n",
        encoding="utf-8",
    )

    with patch("project_sentinel.gateway.cli.GatewayClient.request") as mock_req:
        mock_req.return_value = GatewayResult(
            ok=False,
            status_code=None,
            body_preview=None,
            error_type=GatewayErrorType.FORBIDDEN_BY_ALLOWLIST,
            elapsed_ms=0.0,
        )
        exit_code = main(
            [
                "request",
                "--method",
                "GET",
                "--path",
                "/WebGoat/login",
                "--allowlist",
                str(allowlist_file),
            ]
        )
        assert exit_code == EXIT_BLOCKED


def test_cli_network_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    allowlist_file = tmp_path / "allowlist.yaml"
    allowlist_file.write_text(
        "allowlist:\n  - method: GET\n    path: /WebGoat/actuator/health\n    match: exact\n",
        encoding="utf-8",
    )

    with patch("project_sentinel.gateway.cli.GatewayClient.request") as mock_req:
        mock_req.return_value = GatewayResult(
            ok=False,
            status_code=None,
            body_preview=None,
            error_type=GatewayErrorType.TIMEOUT,
            elapsed_ms=5000.0,
        )
        exit_code = main(
            [
                "request",
                "--method",
                "GET",
                "--path",
                "/WebGoat/actuator/health",
                "--allowlist",
                str(allowlist_file),
            ]
        )
        assert exit_code == EXIT_NETWORK_ERROR


def test_cli_success_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    allowlist_file = tmp_path / "allowlist.yaml"
    allowlist_file.write_text(
        "allowlist:\n  - method: GET\n    path: /WebGoat/actuator/health\n    match: exact\n",
        encoding="utf-8",
    )

    with patch("project_sentinel.gateway.cli.GatewayClient.request") as mock_req:
        mock_req.return_value = GatewayResult(
            ok=True,
            status_code=200,
            body_preview='{"status":"UP"}',
            error_type=None,
            elapsed_ms=12.5,
        )
        exit_code = main(
            [
                "request",
                "--method",
                "GET",
                "--path",
                "/WebGoat/actuator/health",
                "--allowlist",
                str(allowlist_file),
            ]
        )
        assert exit_code == EXIT_OK
