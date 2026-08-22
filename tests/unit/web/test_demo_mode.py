"""Chế độ demo ghim một lần chạy thành công, phòng khi LLM hoặc mạng chết."""

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


def test_no_demo_banner_by_default(client):
    http, _ = client
    assert "Chế độ demo" not in http.get("/").text


def test_demo_banner_appears_when_pinned(client, monkeypatch):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.DONE
    save_run(record)

    monkeypatch.setenv("SENTINEL_DEMO_RUN", record.run_id)
    body = http.get("/").text
    assert "Chế độ demo" in body
    assert record.run_id in body


def test_pinned_run_is_still_browsable(client, monkeypatch):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.DONE
    save_run(record)
    monkeypatch.setenv("SENTINEL_DEMO_RUN", record.run_id)

    for path in ("", "/findings", "/analysis", "/events", "/requests"):
        response = http.get(f"/runs/{record.run_id}{path}")
        assert response.status_code == 200, f"Màn hình {path or '/run'} hỏng ở chế độ demo"
