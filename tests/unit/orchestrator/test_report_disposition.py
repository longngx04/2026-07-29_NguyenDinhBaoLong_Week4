"""Báo cáo cuối phải nói kết luận, không chỉ nói mức nghiêm trọng.

Một finding `needs_review` mà báo cáo chỉ in "medium" thì người đọc vẫn hiểu là
hệ thống khẳng định có lỗ hổng mức medium. Kết luận phải hiện ra, và nếu Python
đã hạ mức thì vết hạ đó cũng phải hiện ra.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run
from project_sentinel.orchestrator.steps import step_report


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(runs_dir=tmp_path / "runs")


def _write_analyses(record, entries):
    (record.root / "analysis.jsonl").write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries) + "\n",
        encoding="utf-8",
    )


def test_report_shows_the_disposition_of_each_finding(ctx):
    record = new_run(ctx.runs_dir)
    _write_analyses(
        record,
        [
            {
                "analysis_id": "analysis-a",
                "title": "SQL Injection",
                "severity": "medium",
                "disposition": "needs_review",
                "attacker_control": "not_proven",
                "reachability": "not_proven",
            }
        ],
    )
    record = step_report(record, ctx)
    markdown = (record.root / "report.md").read_text(encoding="utf-8")

    assert "needs_review" in markdown
    assert "not_proven" in markdown


def test_report_counts_findings_by_disposition(ctx):
    record = new_run(ctx.runs_dir)
    _write_analyses(
        record,
        [
            {"analysis_id": "analysis-a", "title": "A", "disposition": "needs_review"},
            {"analysis_id": "analysis-b", "title": "B", "disposition": "needs_review"},
            {"analysis_id": "analysis-c", "title": "C", "disposition": "likely"},
        ],
    )
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))

    assert data["dispositions"] == {"needs_review": 2, "likely": 1}


def test_report_discloses_that_python_lowered_a_severity(ctx):
    """Hạ mức là một quyết định của hệ thống — không được giấu."""
    record = new_run(ctx.runs_dir)
    _write_analyses(
        record,
        [
            {
                "analysis_id": "analysis-a",
                "title": "SQL Injection",
                "severity": "medium",
                "disposition": "needs_review",
                "calibration": {
                    "rules": ["attacker_control_not_proven"],
                    "severity_from": "high",
                    "severity_to": "medium",
                    "disposition_from": None,
                    "disposition_to": None,
                },
            }
        ],
    )
    record = step_report(record, ctx)
    markdown = (record.root / "report.md").read_text(encoding="utf-8")
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))

    assert data["calibrated_records"] == 1
    assert "high" in markdown and "medium" in markdown
    assert "attacker_control_not_proven" in markdown


def test_report_without_calibration_says_nothing_about_it(ctx):
    record = new_run(ctx.runs_dir)
    _write_analyses(
        record,
        [{"analysis_id": "analysis-a", "title": "A", "disposition": "confirmed"}],
    )
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["calibrated_records"] == 0


def test_record_without_disposition_does_not_break_the_report(ctx):
    """analysis.jsonl có thể là bản cũ sinh trước khi thêm field."""
    record = new_run(ctx.runs_dir)
    _write_analyses(record, [{"analysis_id": "analysis-a", "title": "A"}])
    record = step_report(record, ctx)
    assert (record.root / "report.md").exists()
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["dispositions"] == {}
