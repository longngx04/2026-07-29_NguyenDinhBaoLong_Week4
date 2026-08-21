"""Lệnh `runs`: liệt kê các lần chạy đã lưu trên đĩa."""

from __future__ import annotations

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import list_runs, load_run


def cmd_runs(args) -> int:
        ctx = RunContext.default()
        run_ids = list_runs(ctx.runs_dir)
        if not run_ids:
            print("Chưa có lần chạy nào.")
            return 0
        for run_id in run_ids:
            try:
                record = load_run(ctx.runs_dir, run_id)
            except (OSError, ValueError, KeyError):
                print(f"{run_id}  CORRUPT")
                continue
            print(f"{run_id}  {record.state.value}")
        return 0
