"""Bước 3 và 4 — phân tích finding và đề xuất probe, có allowlist kẹp lại."""

import json
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run
from project_sentinel.orchestrator.steps import StepFailure, step_analyze, step_propose


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(runs_dir=tmp_path / "runs")


def _write_analysis(record, objective):
    line = {
        "schema_version": "1.0",
        "analysis_id": "analysis-1111aaaa-2222-3333-4444-555566667777",
        "title": "SQL Injection",
        "severity": "high",
        "verification_objective": objective,
    }
    (record.root / "analysis.jsonl").write_text(
        json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_accepted_objective_produces_a_probe(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(
        record,
        {
            "description": "Kiem tra gioi han do dai dau vao",
            "endpoint_hint": "POST /WebGoat/attack",
            "payload_kind": "long_string",
            "rationale": "Finding nam o handler nhan tham so",
        },
    )

    record = step_propose(record, ctx)
    data = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))

    assert data["accepted"] is True
    assert data["probe"]["method"] == "POST"
    assert data["probe"]["path"] == "/WebGoat/attack"
    assert data["source_analysis_id"].startswith("analysis-")
    assert record.step("propose").status == "done"


def test_objective_outside_allowlist_is_rejected_and_recorded(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(
        record,
        {
            "description": "Goi endpoint quan tri",
            "endpoint_hint": "GET /WebGoat/admin",
            "payload_kind": "empty_value",
            "rationale": "van ban khong dang tin",
        },
    )

    record = step_propose(record, ctx)
    data = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))

    assert data["accepted"] is False
    assert "allowlist" in data["reason"].lower()
    assert data["probe"] is None
    assert data["objective"]["endpoint_hint"] == "GET /WebGoat/admin", (
        "Đề xuất bị từ chối vẫn phải được lưu nguyên văn làm bằng chứng"
    )


def test_rejected_objective_writes_an_allowlist_block_event(ctx):
    from project_sentinel.guardrails.events import read_events
    from project_sentinel.orchestrator.run_log import read_log

    record = new_run(ctx.runs_dir)
    _write_analysis(
        record,
        {
            "description": "x",
            "endpoint_hint": "GET /WebGoat/admin",
            "payload_kind": "empty_value",
            "rationale": "y",
        },
    )
    record = step_propose(record, ctx)

    kinds = [event["kind"] for event in read_events(record.root / "events.jsonl")]
    assert "allowlist_block" in kinds

    logs = read_log(record.root)
    assert any(e["level"] == "warn" and "Đề xuất bị chặn" in e["message"] for e in logs)


def test_no_objective_at_all_is_not_a_failure(ctx):
    """Agent trả null là hành vi đúng, không phải lỗi."""
    record = new_run(ctx.runs_dir)
    _write_analysis(record, None)

    record = step_propose(record, ctx)
    data = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))

    assert data["accepted"] is False
    assert "không đề xuất" in data["reason"]
    assert record.step("propose").status == "done"


def test_missing_analysis_file_fails_clearly(ctx):
    record = new_run(ctx.runs_dir)
    with pytest.raises(StepFailure) as excinfo:
        step_propose(record, ctx)
    assert "analysis.jsonl" in str(excinfo.value)


def test_empty_analysis_file_is_handled(ctx):
    record = new_run(ctx.runs_dir)
    (record.root / "analysis.jsonl").write_text("", encoding="utf-8")

    record = step_propose(record, ctx)
    data = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))
    assert data["accepted"] is False


def test_first_record_with_an_objective_wins(ctx):
    record = new_run(ctx.runs_dir)
    lines = [
        {"analysis_id": "analysis-aaaa", "verification_objective": None},
        {
            "analysis_id": "analysis-bbbb",
            "verification_objective": {
                "description": "d",
                "endpoint_hint": "GET /WebGoat/attack",
                "payload_kind": "empty_value",
                "rationale": "r",
            },
        },
    ]
    (record.root / "analysis.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )

    record = step_propose(record, ctx)
    data = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))
    assert data["accepted"] is True
    assert data["source_analysis_id"] == "analysis-bbbb"


def test_invalid_json_in_analysis_file_raises_step_failure(ctx):
    record = new_run(ctx.runs_dir)
    (record.root / "analysis.jsonl").write_text("{ dong khong hop le\n", encoding="utf-8")
    with pytest.raises(StepFailure) as excinfo:
        step_propose(record, ctx)
    assert "analysis.jsonl" in str(excinfo.value)


def test_step_analyze_missing_findings_fails_clearly(ctx):
    record = new_run(ctx.runs_dir)
    with pytest.raises(StepFailure) as excinfo:
        step_analyze(record, ctx)
    assert "findings.json" in str(excinfo.value)


def test_step_analyze_invalid_findings_json_fails_clearly(ctx):
    record = new_run(ctx.runs_dir)
    (record.root / "findings.json").write_text("{ hong json", encoding="utf-8")
    with pytest.raises(StepFailure) as excinfo:
        step_analyze(record, ctx)
    assert "findings.json" in str(excinfo.value)


def _record_with_objective(ctx):
    record = new_run(ctx.runs_dir)
    _write_analysis(
        record,
        {
            "description": "Kiem tra",
            "endpoint_hint": "POST /WebGoat/attack",
            "payload_kind": "long_string",
            "rationale": "r",
        },
    )
    return record


def _record_with_two_objectives(ctx):
    record = new_run(ctx.runs_dir)
    lines = [
        {
            "analysis_id": "a1",
            "verification_objective": {
                "description": "d1",
                "endpoint_hint": "GET /WebGoat/admin",
                "payload_kind": "empty_value",
                "rationale": "r1",
            },
        },
        {
            "analysis_id": "a2",
            "verification_objective": {
                "description": "d2",
                "endpoint_hint": "GET /WebGoat/attack",
                "payload_kind": "empty_value",
                "rationale": "r2",
            },
        },
    ]
    (record.root / "analysis.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )
    return record


def test_missing_allowlist_raises_step_failure(ctx, tmp_path):
    """Runner chỉ bắt StepFailure — lỗi đọc allowlist phải về đúng kiểu đó."""
    record = _record_with_objective(ctx)
    broken = ctx.replace(allowlist_path=tmp_path / "khong-ton-tai.json")
    with pytest.raises(StepFailure):
        step_propose(record, broken)


def test_corrupt_allowlist_raises_step_failure(ctx, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ hong", encoding="utf-8")
    record = _record_with_objective(ctx)
    with pytest.raises(StepFailure):
        step_propose(record, ctx.replace(allowlist_path=bad))


def test_other_objectives_are_recorded_even_when_the_first_is_blocked(ctx):
    """Đề xuất hợp lệ bị bỏ qua thì ít nhất phải có dấu vết."""
    from project_sentinel.orchestrator.run_log import read_log

    record = _record_with_two_objectives(ctx)
    record = step_propose(record, ctx)
    payload = json.loads((record.root / "proposal.json").read_text(encoding="utf-8"))
    assert payload["objectives_found"] == 2
    assert payload["source_analysis_id"] == "a1"
    logs = read_log(record.root)
    assert any(e.get("objectives_found") == 2 for e in logs)


def test_step_analyze_invalid_summary_metrics_raises_step_failure(
    ctx, monkeypatch
):
    """Khi run_pipeline trả về dữ liệu tóm tắt không phải số, ném StepFailure."""
    from project_sentinel.orchestrator import steps

    record = new_run(ctx.runs_dir)
    (record.root / "findings.json").write_text(
        json.dumps({"findings": []}), encoding="utf-8"
    )

    monkeypatch.setattr(
        steps,
        "run_pipeline",
        lambda config: {"input_finding_count": "khong-phai-so"},
    )
    with pytest.raises(StepFailure) as excinfo:
        step_analyze(record, ctx)
    assert "Tóm tắt phân tích có số liệu không hợp lệ" in str(excinfo.value)


