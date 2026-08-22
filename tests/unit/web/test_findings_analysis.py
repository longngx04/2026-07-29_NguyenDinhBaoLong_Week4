"""Hai màn hình đọc: cảnh báo thô và báo cáo của agent."""

import json

import pytest
from fastapi.testclient import TestClient

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run, save_run
from project_sentinel.web import main as web_main


@pytest.fixture
def client(tmp_path):
    ctx = RunContext.default().replace(runs_dir=tmp_path / "runs")
    web_main.app.dependency_overrides[web_main.get_context] = lambda: ctx
    yield TestClient(web_main.app), ctx
    web_main.app.dependency_overrides.clear()


@pytest.fixture
def record(client):
    _, ctx = client
    rec = new_run(ctx.runs_dir)
    (rec.root / "findings.json").write_text(json.dumps({"findings": [
        {"id": "f1", "tool": "opengrep", "severity": "high",
         "file_or_url": "src/Login.java", "line": 42, "title": "SQL Injection"},
        {"id": "f2", "tool": "opengrep", "severity": "low",
         "file_or_url": "src/Notes.java", "line": 7, "title": "Weak hash"},
    ]}), encoding="utf-8")
    (rec.root / "analysis.jsonl").write_text(json.dumps({
        "analysis_id": "analysis-aaaa", "title": "SQL Injection qua nối chuỗi",
        "severity": "high", "confidence": "high",
        "explanation": "Truy vấn ghép chuỗi từ dữ liệu người dùng.",
        "remediation": ["Dùng PreparedStatement"],
        "locations": [{"file": "src/Login.java", "line": 42}],
        "evidence": [{"type": "scanner", "finding_id": "f1", "content": "concat in SQL"}],
        "verification_objective": {"description": "Thử chuỗi dài",
                                   "endpoint_hint": "POST /WebGoat/attack",
                                   "payload_kind": "long_string", "rationale": "handler tham so"},
    }) + "\n", encoding="utf-8")
    (rec.root / "proposal.json").write_text(json.dumps({
        "accepted": True, "reason": "allowlist duyệt",
        "probe": {"method": "POST", "path": "/WebGoat/attack", "payload_kind": "long_string"},
        "source_analysis_id": "analysis-aaaa", "objective": None,
    }), encoding="utf-8")
    save_run(rec)
    return rec


def test_findings_screen_lists_every_finding(client, record):
    http, _ = client
    body = http.get(f"/runs/{record.run_id}/findings").text
    assert "SQL Injection" in body
    assert "Weak hash" in body
    assert "src/Login.java" in body


def test_findings_screen_shows_severity_breakdown(client, record):
    http, _ = client
    body = http.get(f"/runs/{record.run_id}/findings").text
    assert "high" in body and "low" in body


def test_findings_screen_with_no_findings_says_so(client):
    http, ctx = client
    empty = new_run(ctx.runs_dir)
    save_run(empty)
    assert "Không có cảnh báo" in http.get(f"/runs/{empty.run_id}/findings").text


def test_analysis_screen_shows_explanation_and_remediation(client, record):
    http, _ = client
    body = http.get(f"/runs/{record.run_id}/analysis").text
    assert "Truy vấn ghép chuỗi" in body
    assert "PreparedStatement" in body


def test_analysis_screen_shows_the_evidence_trail(client, record):
    """Rubric đòi phân tích dựa trên bằng chứng — màn hình phải chiếu được."""
    http, _ = client
    body = http.get(f"/runs/{record.run_id}/analysis").text
    assert "concat in SQL" in body
    assert "src/Login.java" in body


def test_analysis_screen_shows_the_accepted_proposal(client, record):
    http, _ = client
    body = http.get(f"/runs/{record.run_id}/analysis").text
    assert "POST /WebGoat/attack" in body or ("POST" in body and "/WebGoat/attack" in body)


def test_analysis_screen_marks_a_blocked_proposal(client):
    http, ctx = client
    rec = new_run(ctx.runs_dir)
    (rec.root / "analysis.jsonl").write_text("", encoding="utf-8")
    (rec.root / "proposal.json").write_text(json.dumps({
        "accepted": False, "reason": "'GET /WebGoat/admin' không có trong allowlist Gateway.",
        "probe": None, "source_analysis_id": "analysis-bbbb",
        "objective": {"endpoint_hint": "GET /WebGoat/admin"},
    }), encoding="utf-8")
    save_run(rec)

    body = http.get(f"/runs/{rec.run_id}/analysis").text
    assert "không có trong allowlist" in body
    assert "blocked" in body


def test_unknown_run_returns_404_on_both_screens(client):
    http, _ = client
    assert http.get("/runs/20200101T000000Z/findings").status_code == 404
    assert http.get("/runs/20200101T000000Z/analysis").status_code == 404
