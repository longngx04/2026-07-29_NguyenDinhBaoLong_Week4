import os
from project_sentinel.gateway.cli import EXIT_BLOCKED, EXIT_CONFIG_ERROR, EXIT_NETWORK_ERROR, EXIT_OK, main


def test_cli_requires_canonical_api_key(monkeypatch):
    monkeypatch.delenv("SENTINEL_GATEWAY_API_KEY", raising=False)
    assert main(["request"]) == EXIT_CONFIG_ERROR


def test_cli_rejects_unknown_template(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    assert main(["request", "--template-id", "arbitrary-template"]) == EXIT_BLOCKED


def test_cli_maps_unreachable_gateway_to_network_error(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    # Gateway port 9999 is closed, so RealTransport fails connection and CLI returns EXIT_NETWORK_ERROR
    monkeypatch.setattr("project_sentinel.verification.gateway_client.GATEWAY_ORIGIN", "http://127.0.0.1:9999")
    assert main(["request"]) == EXIT_NETWORK_ERROR
