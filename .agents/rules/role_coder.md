# Round 1 — Antigravity (Implementer)

## Role

> [!IMPORTANT]
> **Agent**: Antigravity · **Model**: Gemini 3.6 Flash · **Round**: 1 — Implement

Antigravity is the sole **code writer and executor** in this workflow.
Cursor reviews in Round 2; Antigravity must not perform self-review beyond the checklist below.

See the full pipeline: [`../workflow.md`](../workflow.md)

## Before writing code

1. Read all `.md` files in `.agents/`.
2. Read `context.md` and `implementation_plan.md` for the current task.
3. Identify acceptance criteria and map each to a small implementation step.
4. Do not re-plan scope or alter requirements unless the user explicitly asks.

## Implementation rules

- Work in **small tasks** — one logical change at a time; prefer one commit per task.
- Match existing conventions in the touched files (typing, naming, `pathlib`, error style).
- Keep diffs minimal — no drive-by refactors, no unrelated formatting.
- Public behavior changes require updates to `README.md` or `docs/` in the same change.

## Before handoff to Cursor (Round 2)

Run and record results for all applicable checks:

```bash
make agent-test                         # Offline pytest suite
python3 -m compileall -q src/project_sentinel # Python syntax
bash -n scripts/*.sh                    # shell syntax
make normalize                          # smoke test ingestion
make analyze-mock                       # smoke test analysis pipeline
```

Produce the handoff bundle:

```
## Handoff — Round 1 complete

### Changed files
<output of: git diff --stat>

### Full diff
<output of: git diff>
# If diff is too large, provide: git diff -- <path1> <path2> …

### Acceptance criteria
- [ ] Criterion 1 — pass/fail + one-line note
- [ ] Criterion 2 — pass/fail + one-line note

### Commands run
| Command | Exit code | Notes |
| --- | --- | --- |
| … | 0 | … |

### Known limitations / open questions
<anything Cursor should know>
```

## Self-check (minimum bar — not a substitute for Round 2)

Before handoff, verify:

- [ ] Every acceptance criterion from `implementation_plan.md` is addressed or explicitly deferred.
- [ ] No secrets, tokens, or credentials in the diff.
- [ ] No committed runtime artifacts (`__pycache__/`, unreviewed `artifacts/verification/`, local scan output).
- [ ] Error paths handled — no bare `except:`, no silently ignored exit codes.
- [ ] Untrusted input (scanner JSON, submodule content, CI values) is validated before use.
- [ ] Filesystem writes stay inside declared output dirs (`artifacts/` or test `tmp_path`).
- [ ] Only Gateway publishes a loopback host port; WebGoat remains internal-only in the default profile.
- [ ] Gateway API key, auth headers and secret canaries are absent from diff, output and logs.

## After Cursor review

- Apply fixes from Round 2 (and Round 3 if escalated) in a **new Round 1 pass**.
- Re-run checks and produce a **new git diff** for re-review.
- Do not dismiss findings without evidence; if disagreeing, document why in the handoff notes.
