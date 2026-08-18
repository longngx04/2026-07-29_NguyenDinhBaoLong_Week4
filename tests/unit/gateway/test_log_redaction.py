import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.request_log import log_request
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import send_probe
from project_sentinel.probe.transport import RealTransport


@pytest.mark.live_gateway
def test_audit_contains_provenance_but_not_secret(tmp_path, gateway_ready):
    allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
    probe = SafeProbe(method="GET", path="/WebGoat/actuator/health", payload_kind=None)
    secret = gateway_ready
    log_path = tmp_path / "audit.jsonl"
    result = send_probe(probe, allowlist, secret, transport=RealTransport(), log_path=str(log_path))
    assert result.status_code in {200, 429}
    content = log_path.read_text(encoding="utf-8")
    assert secret not in content
    assert '"policy_decision": "ALLOWED"' in content


@pytest.mark.parametrize("field", ["headers", "body", "api_key", "metadata"])
def test_audit_rejects_every_unreviewed_field(tmp_path, field):
    with pytest.raises(ValueError, match="Unreviewed audit fields"):
        log_request(str(tmp_path / "audit.jsonl"), **{field: {"api_key": "secret-canary"}})


def test_audit_rejects_preview_over_512_utf8_bytes(tmp_path):
    with pytest.raises(ValueError, match="512 UTF-8 bytes"):
        log_request(
            str(tmp_path / "audit.jsonl"),
            response_preview="é" * 257,
        )
