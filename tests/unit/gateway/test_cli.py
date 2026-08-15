from unittest.mock import patch

from project_sentinel.gateway.cli import EXIT_BLOCKED, EXIT_CONFIG_ERROR, EXIT_NETWORK_ERROR, EXIT_OK, main
from project_sentinel.verification.models import VerificationResult, VerificationStatus


def _result(status: VerificationStatus) -> VerificationResult:
    return VerificationResult(result_id="res-1", plan_id="gateway-demo", status=status, status_code=200)


def test_cli_requires_canonical_api_key(monkeypatch):
    monkeypatch.delenv("SENTINEL_GATEWAY_API_KEY", raising=False)
    assert main(["request"]) == EXIT_CONFIG_ERROR


def test_cli_rejects_unknown_template(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    assert main(["request", "--template-id", "arbitrary-template"]) == EXIT_BLOCKED


def test_cli_uses_unified_executor(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    with patch("project_sentinel.gateway.cli.execute_candidate", return_value=_result(VerificationStatus.OBSERVED)) as execute:
        assert main(["request"]) == EXIT_OK
        assert execute.call_count == 1


def test_cli_maps_transport_failure(monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "test-key")
    with patch("project_sentinel.gateway.cli.execute_candidate", return_value=_result(VerificationStatus.FAILED)):
        assert main(["request"]) == EXIT_NETWORK_ERROR
