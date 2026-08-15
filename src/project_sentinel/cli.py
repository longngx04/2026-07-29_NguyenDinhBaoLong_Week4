"""
CLI entry point for Project Sentinel Security Analysis Agent.
Provides analyze, validate, verify, and verify-mock subcommands with strict exit code mappings.

Exit Codes:
  0 - Success
  2 - Invalid config / input file error (FileNotFoundError, ValueError)
  3 - Provider / network failure (OpenRouter API errors, missing API key)
  4 - LLM output / schema / provenance validation failure
  5 - Output I/O write failure
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import jsonschema

from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.analysis.validators import read_jsonl, validate_record_schema
from project_sentinel.config import AppConfig


def main(argv: Optional[List[str]] = None) -> int:
    """CLI main execution entry point."""
    parser = argparse.ArgumentParser(description="Project Sentinel Security Analysis Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # analyze sub-command
    analyze_parser = subparsers.add_parser("analyze", help="Run end-to-end security analysis pipeline")
    analyze_parser.add_argument("--input", type=Path, default=Path("artifacts/normalized/findings.json"), help="Input normalized findings JSON")
    analyze_parser.add_argument("--output", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Output security analysis JSONL")
    analyze_parser.add_argument("--summary", type=Path, default=Path("artifacts/analysis/run-summary.json"), help="Output run summary JSON")
    analyze_parser.add_argument("--provider", type=str, choices=["fake", "openrouter"], default=None, help="LLM provider type")
    analyze_parser.add_argument("--target-root", type=Path, default=None, help="Target project root directory")
    analyze_parser.add_argument("--knowledge-dir", type=Path, default=Path("data/knowledge-base"), help="Knowledge base directory")

    # validate sub-command
    validate_parser = subparsers.add_parser("validate", help="Validate output JSONL file against JSON schema")
    validate_parser.add_argument("--input", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Input JSONL file")
    validate_parser.add_argument("--schema", type=Path, default=Path("schemas/security-analysis-record.schema.json"), help="JSON schema path")

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

    # analyze command
    try:
        config = AppConfig.from_env(
            input_findings_path=args.input,
            output_jsonl_path=args.output,
            summary_path=args.summary,
            provider_type=args.provider,
            knowledge_dir=args.knowledge_dir,
            target_root=args.target_root
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: Invalid configuration or input: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: Configuration setup failed: {e}", file=sys.stderr)
        return 2

    if config.provider_type == "openrouter":
        try:
            config.ensure_openrouter_ready()
        except ValueError as e:
            print(f"Error: OpenRouter configuration failure: {e}", file=sys.stderr)
            return 3

    try:
        summary = run_pipeline(config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error: Invalid input data format: {e}", file=sys.stderr)
        return 2
    except PermissionError as e:
        print(f"Error: I/O write permission error: {e}", file=sys.stderr)
        return 5
    except OSError as e:
        print(f"Error: Output I/O failure: {e}", file=sys.stderr)
        return 5
    except RuntimeError as e:
        print(f"Error: Provider runtime failure: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Error: Pipeline execution error: {e}", file=sys.stderr)
        return 4

    # Fail with exit code 4 if groups existed but all failed validation
    if summary.get("group_count", 0) > 0 and summary.get("output_record_count", 0) == 0 and summary.get("invalid_output_count", 0) > 0:
        print("Error: All finding groups failed schema or provenance validation", file=sys.stderr)
        return 4

    print(f"Analysis complete: {summary['output_record_count']} records written to {config.output_jsonl_path}")
    print(f"Run summary written to {config.summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
