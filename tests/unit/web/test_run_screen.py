"""Màn hình Run và API polling."""

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


def _run_in_progress(ctx):
    record = new_run(ctx.runs_dir)
    record.state = RunState.ANALYZING
    record.mark_step("scan", "running")
    record.mark_step("scan", "done")
    record.mark_step("normalize", "running")
    record.mark_step("normalize", "done")
    record.mark_step("analyze", "running")
    save_run(record)
    return record


def test_run_screen_lists_all_nine_steps(client):
    http, ctx = client
    record = _run_in_progress(ctx)
    body = http.get(f"/runs/{record.run_id}").text
    for name in ("scan", "normalize", "analyze", "propose", "approval",
                 "probe", "scrub", "report", "finalize"):
        assert name in body


def test_run_screen_shows_current_state(client):
    http, ctx = client
    record = _run_in_progress(ctx)
    assert "ANALYZING" in http.get(f"/runs/{record.run_id}").text


def test_unknown_run_returns_404(client):
    http, _ = client
    assert http.get("/runs/20200101T000000Z").status_code == 404


def test_polling_endpoint_returns_compact_json(client):
    http, ctx = client
    record = _run_in_progress(ctx)
    data = http.get(f"/api/runs/{record.run_id}").json()

    assert data["run_id"] == record.run_id
    assert data["state"] == "ANALYZING"
    assert data["terminal"] is False
    assert len(data["steps"]) == 9
    assert data["steps"][0]["status"] == "done"


def test_polling_marks_terminal_states(client):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.DONE
    save_run(record)
    assert http.get(f"/api/runs/{record.run_id}").json()["terminal"] is True


def test_polling_on_unknown_run_returns_404(client):
    http, _ = client
    assert http.get("/api/runs/20200101T000000Z").status_code == 404


def test_failed_run_shows_the_error_message(client):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.FAILED
    record.error = "Bước scan thất bại (mã 9)"
    save_run(record)
    assert "Bước scan thất bại" in http.get(f"/runs/{record.run_id}").text


def test_awaiting_approval_run_links_to_approvals(client):
    http, ctx = client
    record = new_run(ctx.runs_dir)
    record.state = RunState.AWAITING_APPROVAL
    save_run(record)
    assert "/approvals" in http.get(f"/runs/{record.run_id}").text
