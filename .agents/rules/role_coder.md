# Role — Coder (Antigravity)

## Role

> [!IMPORTANT]
> **Agent**: Antigravity · **Model**: Gemini 3.6 Flash High · **Role**: Coder

Antigravity is the sole **code writer and executor** in this workflow.
Reviewer (Codex) reviews every handoff in two layers; Coder must not perform self-review beyond the
checklist below.

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

## Before handoff to Reviewer

Run and record results for all applicable checks:

```bash
make gateway-up                         # required before any Week 4 test — no test doubles exist
make agent-test                         # pytest suite against real containers; fails loud, never skips
python3 -m compileall -q src/project_sentinel # Python syntax
bash -n scripts/*.sh                    # shell syntax
make normalize                          # smoke test ingestion
make probe                              # smoke test proposer -> resolver -> Gateway -> WebGoat
make gateway-down
```

Produce the handoff bundle:

```
## Handoff — Coder complete

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
<anything Reviewer should know>
```

## Self-check (minimum bar — not a substitute for review)

Before handoff, verify:

- [ ] Every acceptance criterion from `implementation_plan.md` is addressed or explicitly deferred.
- [ ] No secrets, tokens, or credentials in the diff.
- [ ] No committed runtime artifacts (`__pycache__/`, unreviewed `artifacts/verification/`, local scan output).
- [ ] Error paths handled — no bare `except:`, no silently ignored exit codes.
- [ ] Untrusted input (scanner JSON, submodule content, CI values) is validated before use.
- [ ] Filesystem writes stay inside declared output dirs (`artifacts/` or test `tmp_path`).
- [ ] Only Gateway publishes a loopback host port; WebGoat remains internal-only in the default profile.
- [ ] Gateway API key, auth headers and secret canaries are absent from diff, output and logs.
- [ ] No `Fake`/`Mock`/`Stub`/`Dummy` class or `provider="fake"` branch was added — no test doubles
      exist in this repository (`.agents/implementation_plan.md` D9).
- [ ] No test added or changed `skip`s when Docker or an LLM key is unavailable — it must fail with
      an actionable message instead (D10).
- [ ] Nothing under `gateway/`/`verification/` imports `analysis`, `SecurityAnalysisRecord`, or reads
      `artifacts/analysis/` — Week 4 does not depend on Week 3 (D8).

## After Reviewer review

- Apply fixes from **both review layers** in a **new Coder pass**.
- Re-run checks and produce a **new git diff** for re-review.
- Do not dismiss findings without evidence; if disagreeing, document why in the handoff notes.
