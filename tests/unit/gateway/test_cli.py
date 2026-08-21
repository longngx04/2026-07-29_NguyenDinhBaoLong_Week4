from project_sentinel.gateway.cli import EXIT_BLOCKED, EXIT_CONFIG_ERROR, EXIT_NETWORK_ERROR, main


def test_cli_requires_canonical_api_key(monkeypatch):
    monkeypatch.delenv("SENTINEL_GATEWAY_API_KEY", raising=False)
    assert main(["request"]) == EXIT_CONFIG_ERROR


def test_cli_rejects_unknown_path(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    assert main(["request", "--path", "/WebGoat/admin"]) == EXIT_BLOCKED


def test_cli_maps_unreachable_gateway_to_network_error(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    monkeypatch.setattr("project_sentinel.probe.tool.GATEWAY_ORIGIN", "http://127.0.0.1:59999")
    assert main(["request"]) == EXIT_NETWORK_ERROR
