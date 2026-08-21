"""Một nhóm hợp lệ mất record là mất một phần kết quả — báo cáo phải nói ra.

`make llm-test` hiện mất 1/2 record hợp lệ, và các lần chạy khác dao động 19–21
record cho 21 nhóm. Trạng thái lần chạy vẫn là `DONE`, và người đọc phải tự trừ
"21 nhóm" cho "20 record" mới biết có gì đó đã biến mất.

Mất mát đó phải có tên, có danh sách, và phải hiện trên báo cáo cuối.
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


def _summary(record, **overrides):
    payload = {
        "schema_version": "1.0",
        "completeness": "COMPLETE",
        "group_count": 2,
        "output_record_count": 2,
        "missing_group_keys": [],
        "llm_call_count": 2,
        "invalid_output_count": 0,
    }
    payload.update(overrides)
    (record.root / "analysis-summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_a_complete_run_says_so(ctx):
    record = new_run(ctx.runs_dir)
    _summary(record)
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["analysis_completeness"] == "COMPLETE"
    assert data["missing_group_keys"] == []


def test_a_partial_run_is_named_in_the_report_json(ctx):
    record = new_run(ctx.runs_dir)
    _summary(
        record,
        completeness="PARTIAL",
        output_record_count=1,
        missing_group_keys=["grp-sqli-lesson3"],
    )
    record = step_report(record, ctx)
    data = json.loads((record.root / "report.json").read_text(encoding="utf-8"))
    assert data["analysis_completeness"] == "PARTIAL"
    assert data["missing_group_keys"] == ["grp-sqli-lesson3"]


def test_a_partial_run_is_visible_to_a_human_reader(ctx):
    """Người đọc report.md phải thấy, không phải tự trừ hai con số."""
    record = new_run(ctx.runs_dir)
    _summary(
        record,
        completeness="PARTIAL",
        output_record_count=1,
        missing_group_keys=["grp-sqli-lesson3"],
    )
    record = step_report(record, ctx)
    markdown = (record.root / "report.md").read_text(encoding="utf-8")
    assert "PARTIAL" in markdown
    assert "grp-sqli-lesson3" in markdown


def test_an_old_summary_without_the_field_does_not_break_the_report(ctx):
    record = new_run(ctx.runs_dir)
    (record.root / "analysis-summary.json").write_text(
        json.dumps({"llm_call_count": 3, "invalid_output_count": 0}), encoding="utf-8"
    )
    record = step_report(record, ctx)
    assert (record.root / "report.md").exists()
