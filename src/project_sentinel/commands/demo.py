"""Lệnh `demo`: chạy kịch bản trình diễn guardrails."""

from __future__ import annotations

from project_sentinel.demo.runner import run_demo


def cmd_demo(args) -> int:
        return run_demo(auto=args.auto)
