#!/usr/bin/env python3
"""Antigravity `Stop` hook: bridge Coder (Antigravity) -> Reviewer (Codex CLI) -> Coder.

Fires every time the Coder agent stops. If there is an uncommitted diff that has not
already been reviewed, it shells out to `codex exec` running the Reviewer role
(.agents/rules/role_reviewer.md + .agents/review.md, two layers in one pass).
If the Reviewer's verdict is REQUEST CHANGES, this hook returns
{"decision": "continue", "reason": "<review findings>"} so Antigravity re-enters the
loop and Coder fixes the findings automatically. Safety valves:

  - AUTO_REVIEW_MAX_ROUNDS (env, default 3): hard cap via the hook's own `executionNum`.
  - No-diff-change short circuit: if the diff is byte-identical to the last reviewed
    diff for this conversation, stop instead of re-running the same review forever.
  - Any error, timeout, or missing `codex` binary fails safe to {"decision": "stop"} —
    it never blocks or crashes the Coder session.

See .agents/workflow.md "Automatic Coder -> Reviewer loop" for the full design and how
to disable/tune this hook.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MAX_ROUNDS = int(os.environ.get("AUTO_REVIEW_MAX_ROUNDS", "3"))
REVIEW_TIMEOUT_SECONDS = int(os.environ.get("AUTO_REVIEW_TIMEOUT_SECONDS", "1500"))
REVIEWER_PROMPT_FILES = [".agents/rules/role_reviewer.md", ".agents/review.md"]
MAX_UNTRACKED_FILE_BYTES = 65_536


def respond(decision, reason=None):
    out = {"decision": decision}
    if reason:
        out["reason"] = reason
    print(json.dumps(out))
    sys.exit(0)


def load_stdin():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def git(workspace, *args):
    return subprocess.run(
        ["git", "-C", workspace, *args], capture_output=True, text=True
    ).stdout


def get_untracked_files(workspace):
    res = subprocess.run(
        ["git", "-C", workspace, "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
    )
    raw_paths = res.stdout.split(b"\x00")
    files = {}
    for raw_p in raw_paths:
        if not raw_p:
            continue
        rel_path = raw_p.decode("utf-8", errors="replace")
        abs_path = Path(workspace, rel_path)
        if abs_path.is_file():
            size = abs_path.stat().st_size
            if size > MAX_UNTRACKED_FILE_BYTES:
                files[rel_path] = f"[TRUNCATED: file size {size} exceeds 64KB]"
            else:
                try:
                    files[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    files[rel_path] = f"[ERROR reading file: {exc}]"
    return files


def parse_verdict(review_text: str) -> str | None:
    for line in reversed(review_text.splitlines()):
        stripped = line.strip()
        match = re.match(r"^VERDICT:\s*(APPROVE|REQUEST CHANGES)\b", stripped, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def main():
    data = load_stdin()
    workspace_paths = data.get("workspacePaths") or []
    workspace = workspace_paths[0] if workspace_paths else os.getcwd()
    conversation_id = data.get("conversationId", "unknown")
    execution_num = int(data.get("executionNum", 0) or 0)
    termination_reason = data.get("terminationReason", "")

    if termination_reason == "error":
        respond("stop")

    if execution_num >= MAX_ROUNDS:
        respond(
            "stop",
            f"Auto-review cap reached ({MAX_ROUNDS} rounds, AUTO_REVIEW_MAX_ROUNDS) — "
            "hand off to a human for the next review round.",
        )

    status = git(workspace, "status", "--porcelain")
    if not status.strip():
        respond("stop")

    diff = git(workspace, "diff", "HEAD")
    untracked_map = get_untracked_files(workspace)
    untracked_repr = "\n\n".join(
        f"#### File: `{path}`\n```\n{content}\n```"
        for path, content in sorted(untracked_map.items())
    )

    diff_hash = hashlib.sha256((status + diff + untracked_repr).encode("utf-8", "ignore")).hexdigest()

    state_dir = Path(workspace) / ".agents" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"auto-review-{conversation_id}.json"
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            state = {}

    if state.get("last_diff_hash") == diff_hash:
        respond(
            "stop",
            "Diff unchanged since the last auto-review round — nothing new to review; "
            "stopping for a human to look.",
        )

    diff_stat = git(workspace, "diff", "--stat", "HEAD")

    reviewer_prompt_parts = []
    for rel in REVIEWER_PROMPT_FILES:
        p = Path(workspace, rel)
        if p.exists():
            reviewer_prompt_parts.append(p.read_text())
    reviewer_prompt = "\n\n---\n\n".join(reviewer_prompt_parts)

    prompt = (
        reviewer_prompt
        + "\n\n---\n\n"
        "## Coder Handoff Bundle for Review\n\n"
        f"### `git status --porcelain`\n```text\n{status}\n```\n\n"
        f"### `git diff --stat HEAD`\n```text\n{diff_stat}\n```\n\n"
        f"### `git diff HEAD` (tracked modifications)\n```diff\n{diff}\n```\n\n"
        f"### Untracked Files Content\n{untracked_repr if untracked_repr else 'None'}\n\n"
        "---\n\n"
        "You are the Reviewer. Review the provided git changes against the rules and checklists above. "
        "Perform Layer 1 + Layer 2 review in one pass. Do not modify any files. "
        "End your final message with the required findings table, then the `VERDICT: APPROVE | REQUEST CHANGES` line, then the Coder fix prompt section."
    )

    reports_dir = Path(workspace) / "artifacts" / "auto-reviews"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_file = reports_dir / f"auto-review-{ts}.md"

    if not shutil.which("codex"):
        respond("stop", "codex CLI not found on PATH — cannot run automatic review.")

    try:
        proc = subprocess.run(
            ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-C", workspace, "-o", str(output_file), "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=REVIEW_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            respond("stop", f"Codex review exited with non-zero status {proc.returncode}: {proc.stderr[:500]}")
    except subprocess.TimeoutExpired:
        respond("stop", "Codex review timed out — manual review needed.")

    review_text = output_file.read_text() if output_file.exists() else ""
    if not review_text.strip():
        respond("stop", "Codex review produced no output — manual review needed.")

    state["last_diff_hash"] = diff_hash
    state["last_execution_num"] = execution_num
    state_file.write_text(json.dumps(state))

    verdict = parse_verdict(review_text)
    if verdict == "APPROVE":
        respond("stop", f"Reviewer approved. Full review saved to {output_file}.")
    elif verdict == "REQUEST CHANGES":
        respond(
            "continue",
            "## Reviewer (Codex) findings — apply these fixes now, then stop\n\n"
            + review_text
            + f"\n\n(Full review saved to {output_file}. Auto-review round "
            f"{execution_num + 1}/{MAX_ROUNDS}.)",
        )
    else:
        respond("stop", f"Reviewer output missing unambiguous VERDICT line. Saved to {output_file}.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        respond("stop", f"Auto-review hook error: {e}")
