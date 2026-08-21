"""Lệnh `validate`: đối chiếu một analysis.jsonl với JSON Schema."""

from __future__ import annotations

import sys

from project_sentinel.analysis.validators import read_jsonl, validate_record_schema


def cmd_validate(args) -> int:
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
