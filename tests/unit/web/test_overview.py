"""Màn hình Overview. Web chỉ đọc artifact thật, không dựng dữ liệu giả."""

import json

import pytest
from fastapi.testclient import TestClient

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run, save_run
from project_sentinel.web import main as web_main


@pytest.fixture
def client(tmp_path):
    ctx = RunContext.default().replace(runs_dir=tmp_path / "runs")
    web_main.app.dependency_overrides[web_main.get_context] = lambda: ctx
    yield TestClient(web_main.app), ctx
    web_main.app.dependency_overrides.clear()


def _finished_run(ctx, state=RunState.DONE, findings=3):
    record = new_run(ctx.runs_dir)
    record.state = state
    record.mark_step("scan", "running")
    record.mark_step("scan", "done")
    (record.root / "findings.json").write_text(
        json.dumps({"findings": [{"id": f"f{i}"} for i in range(findings)]}), encoding="utf-8"
    )
    save_run(record)
    return record


def test_overview_returns_html(client):
    http, _ = client
    response = http.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_overview_with_no_runs_says_so(client):
    http, _ = client
    assert "Chưa có lần chạy nào" in http.get("/").text


def test_overview_lists_a_finished_run(client):
    http, ctx = client
    record = _finished_run(ctx)
    body = http.get("/").text
    assert record.run_id in body
    assert "DONE" in body


def test_overview_shows_the_finding_count(client):
    http, ctx = client
    _finished_run(ctx, findings=7)
    assert "7" in http.get("/").text


def test_overview_links_to_the_run_screen(client):
    http, ctx = client
    record = _finished_run(ctx)
    assert f'/runs/{record.run_id}' in http.get("/").text


def test_overview_never_shows_a_secret(client, monkeypatch):
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "f" * 64)
    http, ctx = client
    _finished_run(ctx)
    assert "f" * 64 not in http.get("/").text


def test_stylesheet_is_served_locally(client):
    http, _ = client
    response = http.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_no_page_references_an_external_host(client):
    """Phòng demo có thể mất mạng; mọi tài nguyên phải là cục bộ."""
    http, ctx = client
    _finished_run(ctx)
    body = http.get("/").text
    for marker in ("https://", "http://cdn", "//cdn."):
        assert marker not in body, f"Trang tham chiếu tài nguyên ngoài: {marker}"
