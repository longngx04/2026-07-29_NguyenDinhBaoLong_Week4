"""
Command-line interface for Project Sentinel.
Provides commands:
- analyze: run end-to-end security analysis pipeline
- validate: validate output JSONL records against schema
- probe: gửi một request kiểm thử an toàn qua Gateway
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from project_sentinel.config import AppConfig
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.request_log import log_request
from project_sentinel.llm.factory import build_llm
from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.analysis.validators import read_jsonl, validate_record_schema
from project_sentinel.probe.proposal import SafeProbe, validate_objective
from project_sentinel.probe.tool import send_probe


def _write_json_atomic(data: Any, target_file: Path) -> None:
    """Atomic write for JSON files using NamedTemporaryFile and os.replace."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_file.parent,
        delete=False,
    ) as tf:
        json.dump(data, tf, indent=2, ensure_ascii=False)
        tf.write("\n")
        temp_path = Path(tf.name)
    os.replace(temp_path, target_file)


def _append_jsonl_atomic(data: dict[str, Any], target_file: Path) -> None:
    """Append one record atomically to a JSONL file."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(data, ensure_ascii=False) + "\n"
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def _confine_path(path: Path, allowed_parent_dir: Path, arg_name: str) -> Path:
    """Ensure path is strictly confined inside allowed_parent_dir without escapes."""
    allowed_parent = allowed_parent_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_parent)
    except ValueError:
        raise ValueError(
            f"Path confinement violation: {arg_name} ({path}) must be located within {allowed_parent}"
        )
    return resolved


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # analyze sub-command
    analyze_parser = subparsers.add_parser("analyze", help="Run end-to-end security analysis pipeline")
    analyze_parser.add_argument("--input", type=Path, default=Path("artifacts/normalized/findings.json"), help="Input normalized findings JSON")
    analyze_parser.add_argument("--output", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Output security analysis JSONL")
    analyze_parser.add_argument("--summary", type=Path, default=Path("artifacts/analysis/run-summary.json"), help="Output run summary JSON")
    analyze_parser.add_argument("--target-root", type=Path, default=None, help="Target project root directory")
    analyze_parser.add_argument("--knowledge-dir", type=Path, default=Path("data/knowledge-base"), help="Knowledge base directory")

    # validate sub-command
    validate_parser = subparsers.add_parser("validate", help="Validate output JSONL file against JSON schema")
    validate_parser.add_argument("--input", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Input JSONL file")
    validate_parser.add_argument("--schema", type=Path, default=Path("schemas/security-analysis-record.schema.json"), help="JSON schema path")

    # probe sub-command
    probe_parser = subparsers.add_parser("probe", help="Gửi một request kiểm thử an toàn qua Gateway")
    probe_parser.add_argument("--method", choices=["GET", "POST"], default="GET")
    probe_parser.add_argument("--path", type=str, default="/WebGoat/actuator/health")
    probe_parser.add_argument(
        "--payload-kind",
        choices=["long_string", "special_chars", "empty_value", "wrong_type"],
        default=None,
    )
    probe_parser.add_argument("--allowlist", type=Path, default=Path("configs/gateway/endpoint-allowlist.json"))
    probe_parser.add_argument("--log", type=Path, default=Path("artifacts/gateway/requests.log.jsonl"))

    args = parser.parse_args(argv)

    # If no subcommand given, default to analyze
    if args.command is None:
        args = parser.parse_args(["analyze"] + (argv if argv else []))

    if args.command == "validate":
        try:
            records = read_jsonl(args.input)
            if not records:
                print(f"Error: JSONL file '{args.input}' is empty", file=sys.stderr)
                return 4
            for idx, rec in enumerate(records, 1):
                is_valid, err = validate_record_schema(rec, args.schema)
                if not is_valid:
                    print(f"Error: Record {idx} in '{args.input}' failed schema validation: {err}", file=sys.stderr)
                    return 4
            print(f"Validated {len(records)} analysis records successfully.")
            return 0
        except FileNotFoundError as e:
            print(f"Error: File not found: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Error: Validation failed: {e}", file=sys.stderr)
            return 4

    if args.command == "probe":
        api_key = os.getenv("SENTINEL_GATEWAY_API_KEY", "")
        if not api_key:
            print("Error: SENTINEL_GATEWAY_API_KEY is required", file=sys.stderr)
            return 2

        try:
            allowlist = Allowlist.from_json(args.allowlist)
        except (OSError, ValueError) as exc:
            print(f"Error: Failed to load allowlist: {exc}", file=sys.stderr)
            return 2

        outcome = send_probe(
            SafeProbe(method=args.method, path=args.path, payload_kind=args.payload_kind),
            allowlist,
            api_key,
            log_path=str(args.log),
        )
        if not outcome.sent:
            print(f"DENIED: {outcome.denied_reason}")
            return 1
        print(f"SENT: {args.method} {args.path} -> {outcome.status_code} ({outcome.elapsed_ms}ms)")
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
