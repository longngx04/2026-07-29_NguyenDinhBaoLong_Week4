"""Merge multiple normalized scanner files without losing provenance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def merge_files(inputs: list[Path], output: Path) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources: list[str] = []

    for path in inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            raise ValueError(f"Normalized file has no findings array: {path}")
        sources.append(str(data.get("source") or path.name))
        for item in data["findings"]:
            if not isinstance(item, dict):
                raise ValueError(f"Finding in {path} is not an object")
            finding_id = str(item.get("id") or "")
            if not finding_id:
                raise ValueError(f"Finding in {path} has no id")
            if finding_id in seen:
                raise ValueError(f"Duplicate finding id while merging: {finding_id}")
            seen.add(finding_id)
            merged.append(item)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "source": "+".join(sources),
                "count": len(merged),
                "findings": merged,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge normalized scanner findings")
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        merged = merge_files(args.input, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Merged {len(merged)} findings -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
