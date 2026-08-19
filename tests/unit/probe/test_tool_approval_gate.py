"""Cổng phê duyệt nằm trong công cụ, không nằm trong giao diện."""

from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.approval import ApprovalDecision
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.probe.tool import send_probe

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


class ExplodingTransport:
    """Transport thật sẽ nổ nếu bị chạm tới. Chứng minh 'không có gì được gửi'."""

    def __init__(self):
        self.calls = 0

    def send_request(self, request):
        self.calls += 1
        raise AssertionError(
            "Transport bị gọi dù request lẽ ra không được phép gửi"
        )


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return Allowlist.from_json(ALLOWLIST_PATH)


def _approved() -> ApprovalDecision:
    return ApprovalDecision(approved=True, decided_at="2026-08-17T10:00:00Z", decided_by="test")


def _rejected() -> ApprovalDecision:
    return ApprovalDecision(approved=False, decided_at="2026-08-17T10:00:00Z", decided_by="test")


def test_post_without_any_decision_is_not_sent(allowlist, tmp_path):
    transport = ExplodingTransport()
    outcome = send_probe(
        SafeProbe("POST", "/WebGoat/attack", "empty_value"),
        allowlist,
        api_key="k",
        approval=None,
        transport=transport,
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert outcome.sent is False
    assert transport.calls == 0
    assert "duyệt" in outcome.denied_reason.lower()


def test_rejected_decision_means_nothing_is_sent(allowlist, tmp_path):
    transport = ExplodingTransport()
    outcome = send_probe(
        SafeProbe("POST", "/WebGoat/attack", "long_string"),
        allowlist,
        api_key="k",
        approval=_rejected(),
        transport=transport,
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert outcome.sent is False
    assert transport.calls == 0


def test_rejection_leaves_no_sent_line_in_the_audit_log(allowlist, tmp_path):
    """Khẳng định một điều KHÔNG xảy ra: log không có dòng SENT nào."""
    log_path = tmp_path / "requests.jsonl"
    send_probe(
        SafeProbe("POST", "/WebGoat/attack", "long_string"),
        allowlist,
        api_key="k",
        approval=_rejected(),
        transport=ExplodingTransport(),
        log_path=str(log_path),
    )
    contents = log_path.read_text(encoding="utf-8")
    assert '"status": "SENT"' not in contents
    assert '"policy_decision": "DENIED"' in contents


def test_get_without_payload_needs_no_approval(allowlist, tmp_path):
    """Probe không rủi ro vẫn chạy được, để cổng duyệt không cản đường vô ích."""

    class CountingTransport:
        def __init__(self):
            self.calls = 0

        def send_request(self, request):
            from project_sentinel.probe.http_models import HttpResponse

            self.calls += 1
            return HttpResponse(
                status_code=200, headers={}, body="ok",
                response_bytes_observed=2, truncated=False, elapsed_ms=1.0,
            )

    transport = CountingTransport()
    outcome = send_probe(
        SafeProbe("GET", "/WebGoat/actuator/health", None),
        allowlist,
        api_key="k",
        approval=None,
        transport=transport,
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert outcome.sent is True
    assert transport.calls == 1


def test_approved_decision_lets_the_request_through_exactly_once(allowlist, tmp_path):
    class CountingTransport:
        def __init__(self):
            self.calls = 0

        def send_request(self, request):
            from project_sentinel.probe.http_models import HttpResponse

            self.calls += 1
            return HttpResponse(
                status_code=200, headers={}, body="ok",
                response_bytes_observed=2, truncated=False, elapsed_ms=1.0,
            )

    transport = CountingTransport()
    outcome = send_probe(
        SafeProbe("POST", "/WebGoat/attack", "empty_value"),
        allowlist,
        api_key="k",
        approval=_approved(),
        transport=transport,
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert outcome.sent is True
    assert transport.calls == 1, "Request phải được gửi đúng một lần"


def test_allowlist_is_checked_before_approval(allowlist, tmp_path):
    """Endpoint cấm bị chặn ngay cả khi đã có phê duyệt hợp lệ."""
    outcome = send_probe(
        SafeProbe("POST", "/WebGoat/admin", "empty_value"),
        allowlist,
        api_key="k",
        approval=_approved(),
        transport=ExplodingTransport(),
        log_path=str(tmp_path / "requests.jsonl"),
    )
    assert outcome.sent is False
    assert "allowlist" in outcome.denied_reason.lower()
