"""Màn hình phải nói đúng về backend đã có DAST.

Ba điều UI trước đây nói sai hoặc im lặng:
  - trang cảnh báo tự xưng là "SAST" trong khi đang chứa cả finding của ZAP,
  - số finding gộp hai loại hạt khác nhau vào một con số,
  - `completeness: PARTIAL` nghĩa là vài nhóm biến mất khỏi báo cáo, mà UI
    không hề nhắc tới.

Mỗi test dưới đây khoá một trong ba điều đó. Bộ test cũng phải chứng minh
màn hình chịu được lần chạy KHÔNG có DAST — đó là chỗ dễ vỡ nhất.
"""

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


def _write(record, name, payload):
    (record.root / name).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def dast_run(client):
    """Một lần chạy có DAST: finding hai nguồn, correlation, PARTIAL."""
    _, ctx = client
    rec = new_run(ctx.runs_dir)
    _write(rec, "findings.json", {"findings": [
        {"id": "opengrep-001", "tool": "opengrep", "severity": "high",
         "file_or_url": "src/Login.java", "line": 42, "title": "SQL Injection",
         "runtime_evidence": {"route": "/SqlInjection/attack2",
                              "strength": "reachable", "dast_alerts": []}},
        {"id": "opengrep-002", "tool": "opengrep", "severity": "medium",
         "file_or_url": "src/Notes.java", "line": 7, "title": "Weak hash",
         "runtime_evidence": {"route": None, "strength": "no_route",
                              "dast_alerts": []}},
        {"id": "zap-10038-abc", "tool": "zap", "severity": "medium",
         "file_or_url": "http://gateway-dast:8081/WebGoat/login", "line": 0,
         "title": "CSP Header Not Set", "instances_total": 7},
    ]})
    _write(rec, "analysis-summary.json", {
        "completeness": "PARTIAL",
        "group_count": 3,
        "output_record_count": 2,
        "missing_group_keys": ["group-aaa"],
        "unresolved_group_reasons": {
            "group-aaa": ["schema: Schema validation error tai analysis_id"]
        },
    })
    save_run(rec)
    return rec


@pytest.fixture
def sast_only_run(client):
    """Lần chạy KHÔNG có DAST — mọi khối mới phải ẩn, không vỡ, không hiện 0."""
    _, ctx = client
    rec = new_run(ctx.runs_dir)
    _write(rec, "findings.json", {"findings": [
        {"id": "opengrep-001", "tool": "opengrep", "severity": "high",
         "file_or_url": "src/Login.java", "line": 42, "title": "SQL Injection"},
    ]})
    save_run(rec)
    return rec


# --- 1. Trang cảnh báo không được tự xưng là SAST ---

def test_findings_page_no_longer_calls_itself_sast_only(client, dast_run):
    http, _ = client
    body = http.get(f"/runs/{dast_run.run_id}/findings").text
    assert "Cảnh báo SAST" not in body, (
        "Trang đang chứa cả finding của ZAP nên không được tự xưng là SAST"
    )


def test_findings_page_breaks_the_count_down_by_tool(client, dast_run):
    """23 SAST + 14 ZAP gộp thành một số là trộn hai loại hạt khác nhau."""
    http, _ = client
    body = http.get(f"/runs/{dast_run.run_id}/findings").text
    assert "opengrep" in body.lower()
    assert "zap" in body.lower()
    assert ">2<" in body or "2</span>" in body, "Thiếu số finding OpenGrep"


def test_findings_page_shows_reachability_for_static_findings(client, dast_run):
    http, _ = client
    body = http.get(f"/runs/{dast_run.run_id}/findings").text
    assert "reachable" in body
    assert "no_route" in body


def test_a_dast_finding_gets_no_reachability_column_value(client, dast_run):
    """Finding động ĐÃ LÀ bằng chứng runtime; gắn thêm là vòng lặp vô nghĩa."""
    from project_sentinel.web.views import findings_data

    _, ctx = client
    data = findings_data(ctx, dast_run.run_id)
    zap = next(f for f in data["findings"] if f["tool"] == "zap")
    assert not (zap.get("runtime_evidence") or {}).get("strength")


# --- 2. Số liệu phải tách theo công cụ và có khối DAST ---

def test_run_page_reports_findings_per_tool(client, dast_run):
    from project_sentinel.web.views import run_data

    _, ctx = client
    data = run_data(ctx, dast_run.run_id)
    assert data["metrics"]["findings_by_tool"] == {"opengrep": 2, "zap": 1}


def test_run_page_reports_the_strength_distribution(client, dast_run):
    from project_sentinel.web.views import run_data

    _, ctx = client
    data = run_data(ctx, dast_run.run_id)
    assert data["strengths"] == {"reachable": 1, "no_route": 1}


# --- 3. PARTIAL phải hiện lên kèm lý do ---

def test_run_page_warns_when_the_analysis_is_partial(client, dast_run):
    http, _ = client
    body = http.get(f"/runs/{dast_run.run_id}").text
    assert "PARTIAL" in body
    assert "group-aaa" in body, "Phải nêu nhóm nào biến mất"
    assert "Schema validation error" in body, "Phải nêu lý do, không chỉ số lượng"


def test_a_complete_run_shows_no_partial_warning(client, sast_only_run):
    http, _ = client
    body = http.get(f"/runs/{sast_only_run.run_id}").text
    assert "PARTIAL" not in body


# --- 4. Lần chạy không có DAST vẫn phải xem được ---

def test_a_run_without_dast_still_renders(client, sast_only_run):
    http, _ = client
    for suffix in ("", "/findings"):
        response = http.get(f"/runs/{sast_only_run.run_id}{suffix}")
        assert response.status_code == 200, suffix


def test_a_run_without_dast_hides_the_dast_blocks(client, sast_only_run):
    """Hiện khối DAST với toàn số 0 làm người đọc tưởng đã quét mà không ra gì."""
    from project_sentinel.web.views import run_data

    _, ctx = client
    data = run_data(ctx, sast_only_run.run_id)
    assert data["strengths"] == {}
    assert data["metrics"]["findings_by_tool"] == {"opengrep": 1}


# --- 5. Reachability ĐO ĐƯỢC phải phân biệt với lời khai của Agent ---

@pytest.fixture
def measured_run(client):
    """Record mà Python đã ghi đè reachability bằng phép đo từ correlation."""
    _, ctx = client
    rec = new_run(ctx.runs_dir)
    _write(rec, "findings.json", {"findings": []})
    (rec.root / "analysis.jsonl").write_text(json.dumps({
        "analysis_id": "analysis-aaaa", "title": "SQL Injection",
        "severity": "high", "confidence": "high",
        "reachability": "proven", "attacker_control": "not_proven",
        "explanation": "x", "remediation": ["y"],
        "locations": [{"file": "src/Login.java", "line": 42}],
        "evidence": [], "verification_objective": None,
        "calibration": {"rules": ["reachability_measured"],
                        "severity_from": None, "severity_to": None,
                        "disposition_from": None, "disposition_to": None},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    save_run(rec)
    return rec


def test_analysis_marks_reachability_that_python_measured(client, measured_run):
    """Người đọc phải phân biệt được số ĐO với lời Agent tự khai."""
    http, _ = client
    body = http.get(f"/runs/{measured_run.run_id}/analysis").text
    assert "proven" in body
    assert "đo" in body.lower(), "Phải nói rõ giá trị này do Python đo, không phải Agent khai"
