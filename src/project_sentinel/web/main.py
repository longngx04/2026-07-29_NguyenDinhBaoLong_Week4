"""Mặt tiền web. Không chứa logic pipeline — chỉ đọc artifact và gọi orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from project_sentinel.guardrails.approval import ApprovalDecision, write_decision
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.runner import create_run, execute_run, resume_run
from project_sentinel.orchestrator.state import load_run
from project_sentinel.web import views

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Project Sentinel")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_context() -> RunContext:
    """Điểm ghi đè duy nhất cho test."""
    return RunContext.default()


def _render(request: Request, template: str, data: dict) -> HTMLResponse:
    return templates.TemplateResponse(request, template, data)


def _load_or_404(loader, *args):
    try:
        return loader(*args)
    except Exception:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy hoặc file state hỏng") from None


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    host = request.headers.get("host")
    origin_host = origin.split("://")[-1].rstrip("/")
    if host and origin_host != host:
        raise HTTPException(status_code=403, detail="Cross-origin requests are forbidden")


@app.get("/", response_class=HTMLResponse)
def overview(request: Request, ctx: RunContext = Depends(get_context)):
    return _render(request, "overview.html", views.overview_data(ctx))


@app.post("/runs")
def start_new_run(request: Request, background: BackgroundTasks, ctx: RunContext = Depends(get_context)):
    _check_origin(request)
    record = create_run(ctx)
    background.add_task(execute_run, ctx, record.run_id)
    return RedirectResponse(url=f"/runs/{record.run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_screen(request: Request, run_id: str, ctx: RunContext = Depends(get_context)):
    return _render(request, "run.html", _load_or_404(views.run_data, ctx, run_id))


@app.get("/api/runs/{run_id}")
def run_status_api(run_id: str, ctx: RunContext = Depends(get_context)):
    return _load_or_404(views.run_status, ctx, run_id)


@app.get("/runs/{run_id}/findings", response_class=HTMLResponse)
def findings_screen(request: Request, run_id: str, ctx: RunContext = Depends(get_context)):
    return _render(request, "findings.html", _load_or_404(views.findings_data, ctx, run_id))


@app.get("/runs/{run_id}/analysis", response_class=HTMLResponse)
def analysis_screen(request: Request, run_id: str, ctx: RunContext = Depends(get_context)):
    return _render(request, "analysis.html", _load_or_404(views.analysis_data, ctx, run_id))


@app.get("/runs/{run_id}/events", response_class=HTMLResponse)
def events_screen(request: Request, run_id: str, ctx: RunContext = Depends(get_context)):
    return _render(request, "events.html", _load_or_404(views.events_data, ctx, run_id))


@app.get("/runs/{run_id}/requests", response_class=HTMLResponse)
def requests_screen(request: Request, run_id: str, ctx: RunContext = Depends(get_context)):
    return _render(request, "requests.html", _load_or_404(views.requests_data, ctx, run_id))


@app.get("/approvals", response_class=HTMLResponse)
def approvals_screen(request: Request, ctx: RunContext = Depends(get_context)):
    return _render(request, "approvals.html", views.approvals_data(ctx))


@app.get("/api/approvals")
def approvals_api(ctx: RunContext = Depends(get_context)):
    return views.approvals_data(ctx)


@app.post("/approvals/{run_id}")
def decide_approval(
    request: Request,
    run_id: str,
    background: BackgroundTasks,
    decision: str = Form(...),
    ctx: RunContext = Depends(get_context),
):
    _check_origin(request)
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Quyết định phải là approve hoặc reject")

    record = _load_or_404(load_run, ctx.runs_dir, run_id)

    fingerprint = ""
    req_file = record.root / "approval-request.json"
    if decision == "approve":
        if not req_file.exists():
            raise HTTPException(status_code=400, detail="Không có approval-request.json để phê duyệt")
        try:
            req_data = json.loads(req_file.read_text(encoding="utf-8"))
            fingerprint = req_data.get("request_fingerprint", "")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="approval-request.json hỏng") from exc
    elif req_file.exists():
        try:
            req_data = json.loads(req_file.read_text(encoding="utf-8"))
            fingerprint = req_data.get("request_fingerprint", "")
        except Exception:
            fingerprint = ""

    write_decision(
        record.root / "decision.json",
        ApprovalDecision(
            approved=decision == "approve",
            decided_at=datetime.now(timezone.utc).isoformat(),
            decided_by="web-operator",
            request_fingerprint=fingerprint,
        ),
    )
    background.add_task(resume_run, ctx, run_id)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)
