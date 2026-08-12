#!/usr/bin/env python3
import json
import sys


def main():
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        data = {}

    ephemeral_msg = (
        "[AUTOMATIC MODEL & RULE GUIDANCE]\n"
        "1. Mandatory Rule: View and read all instruction files in .agents/ before writing code.\n"
        "2. Automatic Model Tier Selection Matrix:\n"
        "   - LIGHT TASK (Docs, formatting, single file fix): Use 'flash_lite' or 'flash'\n"
        "   - STANDARD TASK (Routine features, pipeline modules, standard tests): Use 'flash'\n"
        "   - DEEP TASK (Security boundaries, complex architecture, multi-module refactor, hard bugs): Use 'pro' or 'inherit'\n"
        "3. Subagent Model Selection:\n"
        "   - Simple lookups/grep: Model='flash_lite'\n"
        "   - Codebase research/file reading: Model='flash'\n"
        "   - Heavy refactoring/complex debugging: Model='pro'"
    )

    output = {"injectSteps": [{"ephemeralMessage": ephemeral_msg}]}

    print(json.dumps(output))


if __name__ == "__main__":
    main()
