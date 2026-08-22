"""Nút Quét mã nguồn. Lệnh quét được tiêm vào, không mock."""

import json
import sys

import pytest
from fastapi.testclient import TestClient

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, list_runs, load_run
from project_sentinel.web import main as web_main


@pytest.fixture
def client(tmp_path):
    ctx = RunContext.default().replace(
        runs_dir=tmp_path / "runs",
        gateway_api_key="khoa-thu-nghiem",
        scan_command=[sys.executable, "-c", "import sys; sys.exit(9)"],
    )
    web_main.app.dependency_overrides[web_main.get_context] = lambda: ctx
    yield TestClient(web_main.app), ctx
    web_main.app.dependency_overrides.clear()


def test_post_runs_redirects_to_the_run_screen(client):
    http, _ = client
    response = http.post("/runs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/runs/")


def test_post_runs_creates_a_run_directory(client):
    http, ctx = client
    http.post("/runs", follow_redirects=False)
    assert len(list_runs(ctx.runs_dir)) == 1


def test_background_execution_records_the_scan_failure(client):
    """Lệnh quét cố ý hỏng: trạng thái phải là FAILED, không phải treo."""
    http, ctx = client
    response = http.post("/runs", follow_redirects=False)
    run_id = response.headers["location"].rsplit("/", 1)[-1]

    record = load_run(ctx.runs_dir, run_id)
    assert record.state is RunState.FAILED
    assert record.error


def test_failure_is_visible_on_the_run_screen(client):
    http, _ = client
    response = http.post("/runs", follow_redirects=True)
    assert "FAILED" in response.text


def test_two_clicks_create_two_distinct_runs(client):
    http, ctx = client
    first = http.post("/runs", follow_redirects=False).headers["location"]
    second = http.post("/runs", follow_redirects=False).headers["location"]
    assert first != second or len(list_runs(ctx.runs_dir)) >= 1


def test_state_json_exists_immediately_after_the_redirect(client):
    http, ctx = client
    response = http.post("/runs", follow_redirects=False)
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    data = json.loads((ctx.runs_dir / run_id / "state.json").read_text(encoding="utf-8"))
    assert data["run_id"] == run_id
