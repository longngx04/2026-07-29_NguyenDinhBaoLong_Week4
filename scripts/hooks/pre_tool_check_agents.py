#!/usr/bin/env python3
import json
import os
import sys


def main():
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        data = {}

    tool_call = data.get("toolCall", {})
    tool_args = tool_call.get("args", {})

    target_file = tool_args.get("TargetFile", "") or tool_args.get("AbsolutePath", "")
    if ".agents/" in target_file or "AGENTS.md" in target_file or "scripts/hooks/" in target_file:
        print(json.dumps({"decision": "allow"}))
        return

    transcript_path = data.get("transcriptPath", "")
    agents_read = False

    if transcript_path and os.path.exists(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if ".agents" in content or "AGENTS.md" in content:
                    agents_read = True
        except Exception:
            pass
    else:
        agents_read = True

    if agents_read:
        print(json.dumps({"decision": "allow"}))
    else:
        print(
            json.dumps(
                {
                    "decision": "deny",
                    "reason": (
                        "HOOK BLOCKED: You have not read the .agents/ directory yet! "
                        "All coding agents MUST read all instruction files in .agents/ "
                        "(e.g. .agents/context.md, .agents/rules/coding_agent_rules.md, "
                        ".agents/security.md) BEFORE writing or editing any code files."
                    ),
                }
            )
        )


if __name__ == "__main__":
    main()
