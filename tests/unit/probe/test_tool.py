"""send_probe là đường DUY NHẤT request rời khỏi hệ thống."""

from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import GATEWAY_ORIGIN, ProbeOutcome, send_probe
from project_sentinel.probe.transport import BaseTransport

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


class _NeverCalledTransport(BaseTransport):
    """Dây bẫy: probe bị từ chối thì không được chạm tới transport."""

    def send_request(self, request):
        raise AssertionError(
            f"Transport bị gọi cho request lẽ ra phải bị chặn: {request.method} {request.url}"
        )


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return Allowlist.from_json(ALLOWLIST_PATH)


def test_gateway_origin_is_loopback_only():
    assert GATEWAY_ORIGIN == "http://127.0.0.1:9080"


def test_probe_outside_allowlist_is_denied_before_any_transport(allowlist, tmp_path):
    outcome = send_probe(
        SafeProbe(method="GET", path="/WebGoat/admin", payload_kind=None),
        allowlist,
        api_key="khong-quan-trong",
        transport=_NeverCalledTransport(),
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert isinstance(outcome, ProbeOutcome)
    assert outcome.sent is False
    assert outcome.status_code is None
    assert "allowlist" in outcome.denied_reason.lower()


def test_denied_probe_is_still_written_to_the_audit_log(allowlist, tmp_path):
    log_path = tmp_path / "requests.jsonl"
    send_probe(
        SafeProbe(method="GET", path="/WebGoat/admin", payload_kind=None),
        allowlist,
        api_key="khong-quan-trong",
        transport=_NeverCalledTransport(),
        log_path=str(log_path),
    )
    contents = log_path.read_text(encoding="utf-8")
    assert '"policy_decision": "DENIED"' in contents
    assert '"path": "/WebGoat/admin"' in contents


def test_api_key_never_reaches_the_audit_log(allowlist, tmp_path):
    log_path = tmp_path / "requests.jsonl"
    secret = "sk-day-la-bi-mat-tuyet-doi"
    send_probe(
        SafeProbe(method="GET", path="/WebGoat/admin", payload_kind=None),
        allowlist,
        api_key=secret,
        transport=_NeverCalledTransport(),
        log_path=str(log_path),
    )
    assert secret not in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("junk_payload_kind", ["khong-ton-tai", 123, ["long_string"]])
def test_invalid_payload_kind_is_denied_before_transport(allowlist, tmp_path, junk_payload_kind):
    """Payload_kind sai kiểu hoặc ngoài danh mục phải bị chặn ngay trước transport."""
    log_path = tmp_path / "requests.jsonl"
    outcome = send_probe(
        SafeProbe(method="GET", path="/WebGoat/actuator/health", payload_kind=junk_payload_kind),
        allowlist,
        api_key="khong-quan-trong",
        transport=_NeverCalledTransport(),
        log_path=str(log_path),
    )
    assert isinstance(outcome, ProbeOutcome)
    assert outcome.sent is False
    assert outcome.status_code is None
    assert "payload_kind không hợp lệ" in outcome.denied_reason

    contents = log_path.read_text(encoding="utf-8")
    assert '"policy_decision": "DENIED"' in contents
    assert '"error_class": "InvalidPayloadKind"' in contents
