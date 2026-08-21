"""Lệnh `analyze`: chạy pipeline phân tích trên một file findings."""

from __future__ import annotations

import sys

from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.config import AppConfig


def cmd_analyze(args) -> int:
    # analyze command
    try:
        config = AppConfig.from_env(
            input_findings_path=args.input,
            output_jsonl_path=args.output,
            summary_path=args.summary,
            knowledge_dir=args.knowledge_dir,
            target_root=args.target_root
        )
        run_pipeline(config)
        return 0
    except (FileNotFoundError, ValueError) as e:
        err_str = str(e)
        if "LLM_API_KEY" in err_str or "LLM_PROVIDER" in err_str or "Provider" in err_str or "OpenRouter" in err_str:
            print(f"Error: {e}", file=sys.stderr)
            return 3
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected pipeline error: {e}", file=sys.stderr)
        return 1
