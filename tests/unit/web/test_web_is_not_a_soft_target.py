"""Web mở ba thứ ra ngoài mà CLI không mở: một cổng, một form, và artifact lạ.

Ba test group dưới đây khoá đúng ba chỗ đó:

1. **Nút Approve phải thật sự duyệt được.** `send_probe` ràng buộc phiếu duyệt
   với dấu vân tay của ĐÚNG request sẽ gửi. Một quyết định thiếu vân tay sẽ bị
   chính lớp bảo vệ đó từ chối — nút bấm trông như hoạt động nhưng không.
2. **Form không được nhận lệnh từ trang khác.** Cổng phê duyệt là ranh giới
   người-máy. Nếu một trang bất kỳ mà người vận hành mở có thể POST tới
   127.0.0.1:8000 thì ranh giới đó không còn.
3. **Một artifact hỏng không được làm sập cả giao diện.** `list_runs` đã chịu
   được bản ghi hỏng; tầng web phải giữ cùng tính chất, nếu không một lần chạy
   hỏng sẽ khoá luôn hàng chờ duyệt — đúng lúc cần từ chối một request.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from project_sentinel.guardrails.approval import read_decision, request_fingerprint
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run, save_run
from project_sentinel.probe.proposal import SafeProbe
from project_sentinel.web import main as web_main

PROBE = {"method": "POST", "path": "/WebGoat/attack", "payload_kind": "long_string"}


@pytest.fixture
def client(tmp_path):
    ctx = RunContext.default().replace(
        runs_dir=tmp_path / "runs", gateway_api_key="khoa-thu-nghiem"
    )
    web_main.app.dependency_overrides[web_main.get_context] = lambda: ctx
    yield TestClient(web_main.app, raise_server_exceptions=False), ctx
    web_main.app.dependency_overrides.clear()


def _pending_run(ctx):
    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "reason": "ok",
                "probe": PROBE,
                "source_analysis_id": "analysis-aaaa",
                "objective": None,
            }
        ),
        encoding="utf-8",
    )
    (record.root / "approval-request.json").write_text(
        json.dumps(
            {
                "run_id": record.run_id,
                "method": "POST",
                "endpoint": "/WebGoat/attack",
                "payload": '{"value": "AAAA"}',
                "purpose": "Kiem tra gioi han do dai",
                "risk_reason": "Request POST co the thay doi trang thai",
                "request_fingerprint": request_fingerprint(SafeProbe(**PROBE)),
            }
        ),
        encoding="utf-8",
    )
    record.state = RunState.AWAITING_APPROVAL
    record.mark_step("approval", "running")
    save_run(record)
    return record


# --- 1. Nút Approve phải sinh ra một phiếu duyệt dùng được ------------------


def test_approving_from_the_web_carries_the_request_fingerprint(client):
    """Thiếu vân tay thì `send_probe` từ chối, và nút Approve chỉ là trang trí."""
    http, ctx = client
    record = _pending_run(ctx)

    http.post(
        f"/approvals/{record.run_id}",
        data={"decision": "approve"},
        follow_redirects=False,
    )

    decision = read_decision(record.root / "decision.json")
    assert decision is not None
    assert decision.approved is True
    assert decision.request_fingerprint == request_fingerprint(SafeProbe(**PROBE))


def test_the_web_decision_matches_what_send_probe_demands(client):
    """Đối chiếu thẳng với ràng buộc mà `send_probe` áp dụng."""
    http, ctx = client
    record = _pending_run(ctx)

    http.post(
        f"/approvals/{record.run_id}",
        data={"decision": "approve"},
        follow_redirects=False,
    )

    decision = read_decision(record.root / "decision.json")
    expected = request_fingerprint(SafeProbe(**PROBE))
    assert decision is not None and decision.request_fingerprint == expected, (
        "send_probe so sánh đúng hai giá trị này; lệch nhau là request bị chặn"
    )


def test_a_run_without_an_approval_request_cannot_be_approved(client):
    """Không có phiếu duyệt thì không có gì để duyệt — phải từ chối, không đoán."""
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.AWAITING_APPROVAL
    save_run(record)

    response = http.post(
        f"/approvals/{record.run_id}",
        data={"decision": "approve"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert not (record.root / "decision.json").exists()


# --- 2. Không nhận lệnh từ trang khác --------------------------------------


def test_a_cross_origin_post_cannot_approve(client):
    """Cổng phê duyệt là ranh giới người-máy; CSRF đi vòng qua nó."""
    http, ctx = client
    record = _pending_run(ctx)

    response = http.post(
        f"/approvals/{record.run_id}",
        data={"decision": "approve"},
        headers={"Origin": "https://ke-tan-cong.example"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert not (record.root / "decision.json").exists()


def test_a_cross_origin_post_cannot_start_a_run(client):
    """Mỗi lần chạy tiêu token thật; một trang lạ không được quyền bấm."""
    http, ctx = client

    response = http.post(
        "/runs",
        headers={"Origin": "https://ke-tan-cong.example"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert not (ctx.runs_dir.exists() and any(ctx.runs_dir.iterdir()))


def test_the_same_origin_form_still_works(client):
    """Chặn CSRF không được chặn luôn người dùng thật."""
    http, ctx = client
    record = _pending_run(ctx)

    response = http.post(
        f"/approvals/{record.run_id}",
        data={"decision": "reject"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (record.root / "decision.json").exists()


# --- 3. Artifact hỏng không được làm sập giao diện -------------------------


@pytest.mark.parametrize(
    "name,content",
    [
        ("state.json", "{ khong phai json"),
        ("state.json", "42"),
        ("findings.json", "[1, 2, 3]"),
        ("analysis.jsonl", '{"a": 1}\nkhong-phai-json\n'),
        ("proposal.json", "null"),
        ("gateway-requests.jsonl", "khong-phai-json\n"),
    ],
)
def test_one_corrupt_artifact_does_not_take_down_the_whole_ui(client, name, content):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.DONE
    save_run(record)
    (record.root / name).write_text(content, encoding="utf-8")

    for path in ("/", "/approvals"):
        assert http.get(path).status_code == 200, (
            f"{name} hỏng làm {path} sập — hàng chờ duyệt phải luôn mở được"
        )

    for path in ("", "/findings", "/analysis", "/events", "/requests"):
        status = http.get(f"/runs/{record.run_id}{path}").status_code
        assert status in {200, 404}, f"{name} hỏng làm {path} trả {status}"
