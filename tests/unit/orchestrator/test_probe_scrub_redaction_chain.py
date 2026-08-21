"""Chuỗi step_probe → step_scrub thật, với response mang canary nhạy cảm.

Các test scrub cũ tự tay ghi `probe-result.json`, nên chúng không đi qua
`step_probe`. File này chạy đúng chuỗi thật để trả lời hai câu hỏi khác nhau:

1. Dữ liệu nhạy cảm có chạm đĩa ở bất kỳ file nào của lần chạy không?
2. Bằng chứng guardrail (`scrubbed.json`, `events.jsonl`) có ghi nhận rằng
   redaction ĐÃ xảy ra không?
"""

import json
from pathlib import Path

import pytest

from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.guardrails.events import read_events
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run
from project_sentinel.orchestrator.steps import step_approval, step_probe, step_scrub
from project_sentinel.probe.http_models import HttpResponse

CANARIES = {
    "email": "canary-victim@example.com",
    "jwt": "eyJhbGciOi.AAAABBBBCCCC.DDDDEEEEFFFF",
    "password": "SuperSecretCanary123",
    "api_key": "0123456789abcdef0123456789abcdef",
}

CANARY_BODY = (
    "<html><body>Chao mung"
    f" email={CANARIES['email']}"
    f" token={CANARIES['jwt']}"
    f" password: {CANARIES['password']}"
    f" api_key: {CANARIES['api_key']}"
    "</body></html>"
)


class CanaryTransport:
    """Ứng dụng đích trả về một response có chứa dữ liệu nhạy cảm thật."""

    def send_request(self, request):
        return HttpResponse(
            status_code=200,
            headers={},
            body=CANARY_BODY,
            response_bytes_observed=len(CANARY_BODY.encode("utf-8")),
            truncated=False,
            elapsed_ms=4.2,
        )


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(
        runs_dir=tmp_path / "runs", gateway_api_key="khoa-thu-nghiem"
    )


@pytest.fixture
def probed_record(ctx):
    """Chạy thật approval → probe → scrub với response mang canary."""
    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "reason": "test",
                "probe": {
                    "method": "POST",
                    "path": "/WebGoat/attack",
                    "payload_kind": "long_string",
                },
                "source_analysis_id": "analysis-aaaa",
                "objective": {
                    "description": "kiem tra",
                    "endpoint_hint": "POST /WebGoat/attack",
                    "payload_kind": "long_string",
                    "rationale": "r",
                },
            }
        ),
        encoding="utf-8",
    )
    record = step_approval(record, ctx)
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=True,
            decided_at="2026-08-21T10:00:00Z",
            decided_by="test-operator",
            request_fingerprint=request["request_fingerprint"],
        ),
    )
    record = step_probe(record, ctx, transport=CanaryTransport())
    assert json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )["sent"] is True, "Probe phải gửi được thì test này mới có ý nghĩa"
    return step_scrub(record, ctx)


def test_no_canary_reaches_any_file_of_the_run(probed_record):
    """Không một byte nhạy cảm nào được nằm lại trong thư mục lần chạy."""
    leaks: list[str] = []
    for path in sorted(probed_record.root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, canary in CANARIES.items():
            if canary in text:
                leaks.append(f"{path.name} chứa canary {name}")
    assert not leaks, "Dữ liệu nhạy cảm chạm đĩa: " + "; ".join(leaks)


def test_scrubbed_keeps_placeholders(probed_record):
    """safe_text phải giữ placeholder, không phải im lặng xoá sạch."""
    scrubbed = json.loads(
        (probed_record.root / "scrubbed.json").read_text(encoding="utf-8")
    )
    assert "[REDACTED_EMAIL]" in scrubbed["safe_text"]
    assert "[REDACTED_TOKEN]" in scrubbed["safe_text"]
    assert scrubbed["safe_text"].startswith("<untrusted_app_response>")


def test_scrubbed_reports_that_redaction_happened(probed_record):
    """Bằng chứng phải nói redaction ĐÃ xảy ra, không được báo 0."""
    scrubbed = json.loads(
        (probed_record.root / "scrubbed.json").read_text(encoding="utf-8")
    )
    kinds = {item["kind"] for item in scrubbed["redactions"]}
    assert "email" in kinds, f"scrubbed.json báo sai: {scrubbed['redactions']}"
    assert "token" in kinds, f"scrubbed.json báo sai: {scrubbed['redactions']}"


def test_redaction_event_is_recorded(probed_record):
    """events.jsonl là nguồn số liệu của báo cáo cuối — phải có dòng redaction."""
    kinds = [event["kind"] for event in read_events(probed_record.root / "events.jsonl")]
    assert "redaction" in kinds, f"Sổ sự kiện thiếu redaction, chỉ có: {kinds}"


class ExplodingTransport:
    def send_request(self, request):
        raise AssertionError("Không request nào được phép rời khỏi hệ thống ở ca này")


def test_a_string_false_decision_sends_nothing(ctx):
    """`{"approved": "false"}` là ý định TỪ CHỐI. Không byte nào được rời hệ thống.

    Trước khi sửa, `bool("false")` là `True` nên cổng hiểu thành ĐỒNG Ý và request
    thật sự được gửi. Test này đi qua đúng file trên đĩa, giống hệt đường mà một UI
    hay một script bên ngoài sẽ ghi quyết định.
    """
    import json as _json

    from project_sentinel.orchestrator.steps import StepFailure, step_approval, step_probe

    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        _json.dumps(
            {
                "accepted": True,
                "reason": "test",
                "probe": {
                    "method": "POST",
                    "path": "/WebGoat/attack",
                    "payload_kind": "long_string",
                },
                "source_analysis_id": "analysis-aaaa",
                "source_finding_ids": [],
                "objective": None,
            }
        ),
        encoding="utf-8",
    )
    record = step_approval(record, ctx)
    request = _json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    (record.root / "decision.json").write_text(
        _json.dumps(
            {
                "approved": "false",
                "decided_at": "2026-08-21T10:00:00Z",
                "decided_by": "ui-ghi-sai-kieu",
                "request_fingerprint": request["request_fingerprint"],
            }
        ),
        encoding="utf-8",
    )

    transport = ExplodingTransport()
    with pytest.raises((StepFailure, ValueError)):
        step_probe(record, ctx, transport=transport)


def test_a_real_json_false_decision_also_sends_nothing(ctx):
    """Đối chiếu: boolean `false` thật vẫn phải chặn, và chặn một cách sạch sẽ."""
    import json as _json

    from project_sentinel.orchestrator.state import RunState
    from project_sentinel.orchestrator.steps import step_approval, step_probe

    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        _json.dumps(
            {
                "accepted": True,
                "reason": "test",
                "probe": {
                    "method": "POST",
                    "path": "/WebGoat/attack",
                    "payload_kind": "long_string",
                },
                "source_analysis_id": "analysis-aaaa",
                "source_finding_ids": [],
                "objective": None,
            }
        ),
        encoding="utf-8",
    )
    record = step_approval(record, ctx)
    request = _json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )
    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=False,
            decided_at="2026-08-21T10:00:00Z",
            decided_by="cli-operator",
            request_fingerprint=request["request_fingerprint"],
        ),
    )
    record = step_probe(record, ctx, transport=ExplodingTransport())
    assert record.state is RunState.REJECTED
    result = json.loads(
        (record.root / "probe-result.json").read_text(encoding="utf-8")
    )
    assert result["sent"] is False
