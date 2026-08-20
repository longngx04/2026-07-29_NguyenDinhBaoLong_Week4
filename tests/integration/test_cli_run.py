"""Luồng orchestrator qua CLI, dùng subprocess thật và không có test double."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run, save_run
from project_sentinel.orchestrator.steps import step_approval

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


def _cli(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "project_sentinel.cli", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def _failing_scan_env(tmp_path: Path) -> dict[str, str]:
    scan_script = tmp_path / "failing-scan.sh"
    scan_script.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
    scan_script.chmod(0o700)
    return {
        "SENTINEL_RUNS_DIR": str(tmp_path),
        "SENTINEL_SCAN_COMMAND": str(scan_script),
        "SENTINEL_GATEWAY_API_KEY": "integration-test-key",
    }


def _awaiting_run(tmp_path: Path):
    ctx = RunContext.default(repo_root=REPO_ROOT).replace(runs_dir=tmp_path)
    record = new_run(ctx.runs_dir)
    (record.root / "proposal.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "reason": "test",
                "probe": {
                    "method": "POST",
                    "path": "/WebGoat/attack",
                    "payload_kind": "empty_value",
                },
                "source_analysis_id": "analysis-test",
                "objective": {"description": "Kiểm chứng qua CLI"},
            }
        ),
        encoding="utf-8",
    )
    record = step_approval(record, ctx)
    save_run(record)
    return record


def test_runs_command_exits_zero_even_with_no_runs(tmp_path):
    result = _cli("runs", env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)})
    assert result.returncode == 0
    assert "Chưa có lần chạy nào" in result.stdout


def test_run_reports_failure_clearly_when_scan_cannot_start(tmp_path):
    result = _cli("run", env_extra=_failing_scan_env(tmp_path))

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "traceback" not in combined.lower()
    assert "FAILED" in combined or "thất bại" in combined


def test_run_without_a_gateway_key_fails_before_creating_a_run(tmp_path):
    result = _cli(
        "run",
        env_extra={
            "SENTINEL_RUNS_DIR": str(tmp_path),
            "SENTINEL_GATEWAY_API_KEY": "",
        },
    )

    assert result.returncode != 0
    assert "SENTINEL_GATEWAY_API_KEY" in result.stderr
    assert not list(tmp_path.iterdir())


def test_failed_run_still_leaves_state_on_disk(tmp_path):
    _cli("run", env_extra=_failing_scan_env(tmp_path))

    run_dirs = [path for path in tmp_path.iterdir() if (path / "state.json").exists()]
    assert run_dirs, "Lần chạy hỏng vẫn phải để lại state.json"
    data = json.loads((run_dirs[0] / "state.json").read_text(encoding="utf-8"))
    assert data["state"] == "FAILED"


def test_runs_command_lists_the_failed_run(tmp_path):
    _cli("run", env_extra=_failing_scan_env(tmp_path))

    result = _cli("runs", env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)})

    assert result.returncode == 0
    assert "FAILED" in result.stdout


def test_runs_command_marks_a_corrupt_state_without_crashing(tmp_path):
    corrupt = tmp_path / "20200101T000000Z"
    corrupt.mkdir()
    (corrupt / "state.json").write_text("{hong", encoding="utf-8")

    result = _cli("runs", env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)})

    assert result.returncode == 0
    assert "20200101T000000Z  CORRUPT" in result.stdout


def test_approve_on_unknown_run_fails_clearly(tmp_path):
    result = _cli(
        "approve",
        "20200101T000000Z",
        "--decision",
        "approve",
        env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)},
    )

    assert result.returncode != 0
    assert "traceback" not in (result.stdout + result.stderr).lower()


def test_approve_reject_copies_fingerprint_from_the_request_file(tmp_path):
    record = _awaiting_run(tmp_path)
    request = json.loads(
        (record.root / "approval-request.json").read_text(encoding="utf-8")
    )

    result = _cli(
        "approve",
        record.run_id,
        "--decision",
        "reject",
        env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(
        (record.root / "decision.json").read_text(encoding="utf-8")
    )
    assert decision["request_fingerprint"] == request["request_fingerprint"]
    state = json.loads((record.root / "state.json").read_text(encoding="utf-8"))
    assert state["state"] == RunState.REJECTED.value


def test_approve_rejects_an_approval_request_with_empty_fingerprint(tmp_path):
    record = _awaiting_run(tmp_path)
    request_path = record.root / "approval-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["request_fingerprint"] = ""
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = _cli(
        "approve",
        record.run_id,
        "--decision",
        "reject",
        env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)},
    )

    assert result.returncode != 0
    assert not (record.root / "decision.json").exists()
    assert "fingerprint" in result.stderr.lower()


def test_approve_rejects_a_run_id_outside_the_runs_directory(tmp_path):
    result = _cli(
        "approve",
        "../20200101T000000Z",
        "--decision",
        "reject",
        env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)},
    )

    assert result.returncode != 0
    assert "traceback" not in (result.stdout + result.stderr).lower()


def test_approve_does_not_overwrite_a_terminal_run(tmp_path):
    record = new_run(tmp_path)
    record.state = RunState.DONE
    save_run(record)

    result = _cli(
        "approve",
        record.run_id,
        "--decision",
        "reject",
        env_extra={"SENTINEL_RUNS_DIR": str(tmp_path)},
    )

    assert result.returncode != 0
    assert not (record.root / "decision.json").exists()
    assert "không chờ phê duyệt" in result.stderr


def test_approve_requires_a_gateway_key_only_when_approving(tmp_path):
    record = _awaiting_run(tmp_path)

    result = _cli(
        "approve",
        record.run_id,
        "--decision",
        "approve",
        env_extra={
            "SENTINEL_RUNS_DIR": str(tmp_path),
            "SENTINEL_GATEWAY_API_KEY": "",
        },
    )

    assert result.returncode != 0
    assert "SENTINEL_GATEWAY_API_KEY" in result.stderr
    assert not (record.root / "decision.json").exists()
