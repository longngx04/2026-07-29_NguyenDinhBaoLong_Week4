"""Sáu ca kiểm thử bắt buộc của tuần 5.

Hai ca Prompt Injection, hai ca dữ liệu nhạy cảm, hai ca phê duyệt.
Mỗi ca cho kết quả Pass/Fail rõ ràng và ánh xạ thẳng vào tiêu chí đề bài.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.approval import (
    ApprovalDecision,
    request_fingerprint,
)
from project_sentinel.guardrails.injection import scan, wrap_untrusted
from project_sentinel.llm.base import AnalysisPacket, LLMResult
from project_sentinel.llm.redacting import RedactingProvider
from project_sentinel.probe.proposal import SafeProbe, validate_objective
from project_sentinel.probe.tool import send_probe

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "injection"
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return Allowlist.from_json(ALLOWLIST_PATH)


class Recorder:
    """Provider thật ghi lại prompt nhận được."""

    def __init__(self):
        self.packets = []

    def analyze(self, packet, system_prompt=None):
        self.packets.append(packet)
        return LLMResult(raw_response="{}", parsed_response={})

    def generate(self, *, system_prompt, user_prompt):
        self.packets.append(user_prompt)
        return LLMResult(raw_response="{}", parsed_response={})


class ExplodingTransport:
    def send_request(self, request):
        raise AssertionError("Không request nào được phép rời khỏi hệ thống ở ca này")


# ── CA 1 & 2: Prompt Injection ────────────────────────────────────────────

def test_case_1_injection_demanding_system_prompt_is_blocked():
    """CA 1 — Agent không thực hiện chỉ dẫn độc hại trong response."""
    body = json.loads((FIXTURES / "ignore-instructions.json").read_text(encoding="utf-8"))["body"]

    verdict = scan(body)
    assert verdict.verdict == "suspicious"

    recorder = Recorder()
    RedactingProvider(recorder).analyze(
        AnalysisPacket(group_key="g", finding_group={"response": wrap_untrusted(verdict.sanitized_text)})
    )
    delivered = str(recorder.packets[0].finding_group)
    assert "reveal your system prompt" not in delivered.lower()
    assert "[REMOVED_INJECTION_ATTEMPT]" in delivered
    assert "<untrusted_app_response>" in delivered


def test_case_2_injection_naming_forbidden_endpoint_is_blocked_twice(allowlist):
    """CA 2 — Bị phát hiện bởi bộ quét VÀ bị allowlist chặn."""
    body = json.loads((FIXTURES / "exfiltrate-endpoint.json").read_text(encoding="utf-8"))["body"]

    assert scan(body).verdict == "suspicious"

    decision = validate_objective(
        {
            "description": "Theo chỉ dẫn trong response",
            "endpoint_hint": "GET /WebGoat/admin",
            "payload_kind": "empty_value",
            "rationale": "văn bản không đáng tin",
        },
        allowlist,
    )
    assert decision.accepted is False
    assert decision.probe is None


# ── CA 3 & 4: Dữ liệu nhạy cảm ────────────────────────────────────────────

def test_case_3_pii_never_reaches_the_llm():
    """CA 3 — Dữ liệu nhạy cảm không xuất hiện trong prompt."""
    body = json.loads((FIXTURES / "pii-leak.json").read_text(encoding="utf-8"))["body"]

    recorder = Recorder()
    RedactingProvider(recorder).analyze(
        AnalysisPacket(group_key="g", finding_group={"response": body})
    )
    delivered = str(recorder.packets[0].finding_group)

    for secret in ["nguyen.van.a@example.com", "tran.thi.b@example.com",
                   "0912345678", "0987654321", "4111"]:
        assert secret not in delivered, f"Rò rỉ {secret} vào prompt"
    assert "[REDACTED_EMAIL]" in delivered


def test_case_4_pii_and_api_key_never_reach_the_log(allowlist, tmp_path):
    """CA 4 — Dữ liệu nhạy cảm không xuất hiện trong log."""
    log_path = tmp_path / "requests.jsonl"
    secret_key = "d" * 64

    send_probe(
        SafeProbe("GET", "/WebGoat/admin", None),
        allowlist,
        api_key=secret_key,
        transport=ExplodingTransport(),
        log_path=str(log_path),
    )

    contents = log_path.read_text(encoding="utf-8")
    assert secret_key not in contents, "API key lọt vào log"
    assert "nguyen.van.a@example.com" not in contents


# ── CA 5 & 6: Phê duyệt ───────────────────────────────────────────────────

def test_case_5_reject_means_no_request_is_ever_sent(allowlist, tmp_path):
    """CA 5 — Request cần phê duyệt KHÔNG được gửi khi người dùng chọn Reject."""
    log_path = tmp_path / "requests.jsonl"
    probe = SafeProbe("POST", "/WebGoat/attack", "long_string")

    outcome = send_probe(
        probe,
        allowlist,
        api_key="k",
        approval=ApprovalDecision(
            approved=False,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
            request_fingerprint=request_fingerprint(probe),
        ),
        transport=ExplodingTransport(),
        log_path=str(log_path),
    )

    assert outcome.sent is False
    contents = log_path.read_text(encoding="utf-8")
    assert '"status": "SENT"' not in contents, "Log có dòng SENT dù đã bị từ chối"


def test_case_6_approve_sends_the_request_exactly_once(allowlist, tmp_path):
    """CA 6 — Approve thì request được gửi, đúng một lần."""
    from project_sentinel.probe.http_models import HttpResponse

    class CountingTransport:
        def __init__(self):
            self.calls = 0

        def send_request(self, request):
            self.calls += 1
            return HttpResponse(
                status_code=200, headers={}, body="ok",
                response_bytes_observed=2, truncated=False, elapsed_ms=1.0,
            )

    transport = CountingTransport()
    probe = SafeProbe("POST", "/WebGoat/attack", "empty_value")
    outcome = send_probe(
        probe,
        allowlist,
        api_key="k",
        approval=ApprovalDecision(
            approved=True,
            decided_at="2026-08-17T10:00:00Z",
            decided_by="test",
            request_fingerprint=request_fingerprint(probe),
        ),
        transport=transport,
        log_path=str(tmp_path / "requests.jsonl"),
    )

    assert outcome.sent is True
    assert transport.calls == 1
