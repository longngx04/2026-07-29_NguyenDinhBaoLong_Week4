"""Proposal phải mang theo finding nó định kiểm chứng, và báo cáo phải nói
thẳng kết quả probe khẳng định, bác bỏ, hay chưa kết luận được gì.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run
from project_sentinel.orchestrator.steps import step_propose, step_report


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(runs_dir=tmp_path / "runs")


ANALYSIS = {
    "analysis_id": "analysis-a",
    "source_finding_ids": ["finding-1", "finding-2"],
    "title": "SQL Injection",
    "severity": "medium",
    "disposition": "needs_review",
    "explanation": "Truy vấn chạy qua Statement.",
    "evidence": [
        {
            "type": "source",
            "path": "SqlInjectionLesson9.java",
            "start_line": 110,
            "end_line": 120,
            "content": "stmt.executeQuery(query)",
        }
    ],
    "verification_objective": {
        "description": "Quan sat phan hoi trang login",
        "endpoint_hint": "GET /WebGoat/login",
        "payload_kind": "empty_value",
        "rationale": "r",
    },
}


def _write_analysis(record, entry=ANALYSIS):
    (record.root / "analysis.jsonl").write_text(
        json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_proposal_carries_the_finding_ids_it_means_to_verify(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(record)
    record = step_propose(record, ctx)

    proposal = json.loads(
        (record.root / "proposal.json").read_text(encoding="utf-8")
    )
    assert proposal["source_analysis_id"] == "analysis-a"
    assert proposal["source_finding_ids"] == ["finding-1", "finding-2"]


def test_operator_override_declares_it_verifies_no_finding(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(record)
    override_ctx = ctx.replace(
        probe_override={
            "description": "do nguoi van hanh chi dinh",
            "endpoint_hint": "GET /WebGoat/login",
            "payload_kind": "empty_value",
            "rationale": "r",
        }
    )
    record = step_propose(record, override_ctx)

    proposal = json.loads(
        (record.root / "proposal.json").read_text(encoding="utf-8")
    )
    assert proposal["source_analysis_id"] == "operator-override"
    assert proposal["source_finding_ids"] == []


def test_report_says_an_unrelated_200_verified_nothing(ctx):
    """Đúng ca của lần chạy cuối — báo cáo không được để người đọc hiểu nhầm."""
    record = new_run(ctx.runs_dir)
    _write_analysis(record)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "reason": "ok",
                "probe": {
                    "method": "GET",
                    "path": "/WebGoat/login",
                    "payload_kind": None,
                },
                "source_analysis_id": "analysis-a",
                "source_finding_ids": ["finding-1"],
                "objective": {"endpoint_hint": "GET /WebGoat/login"},
                "operator_override": False,
            }
        ),
        encoding="utf-8",
    )
    (record.root / "probe-result.json").write_text(
        json.dumps(
            {"sent": True, "status_code": 200, "body_preview": "<html>Login</html>"}
        ),
        encoding="utf-8",
    )

    record = step_report(record, ctx)
    markdown = (record.root / "report.md").read_text(encoding="utf-8")
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))

    assert data["probe_verdict"]["verdict"] == "inconclusive"
    assert data["probe_verdict"]["evidence_kind"] == "unrelated_endpoint"
    assert "inconclusive" in markdown
    assert "không nằm trong bằng chứng" in markdown


def test_report_reads_finding_ids_from_the_analysis_not_the_proposal(ctx):
    """proposal.json là bản sao có thể cũ; nguồn đúng là chính analysis record."""
    record = new_run(ctx.runs_dir)
    _write_analysis(record)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "probe": {"method": "GET", "path": "/WebGoat/login"},
                "source_analysis_id": "analysis-a",
                "source_finding_ids": ["finding-1"],
                "objective": {"endpoint_hint": "GET /WebGoat/login"},
                "operator_override": False,
            }
        ),
        encoding="utf-8",
    )
    (record.root / "probe-result.json").write_text(
        json.dumps({"sent": True, "status_code": 200, "body_preview": "x"}),
        encoding="utf-8",
    )
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["probe_verdict"]["analysis_id"] == "analysis-a"
    # Proposal chỉ chép "finding-1"; record thật có cả hai. Báo cáo theo record.
    assert data["probe_verdict"]["source_finding_ids"] == ["finding-1", "finding-2"]


def test_report_with_no_probe_still_states_a_verdict(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(record)
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["probe_verdict"]["verdict"] == "inconclusive"
    assert data["probe_verdict"]["evidence_kind"] == "none"
