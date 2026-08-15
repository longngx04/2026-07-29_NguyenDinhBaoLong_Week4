# Two-Role Workflow

Two roles for this repository. Each role has a fixed agent, model, and scope.
Do not skip a role or merge them unless the user explicitly overrides.

## Roles

| Role | Agent | Model | Rule file |
| --- | --- | --- | --- |
| **Coder** | Antigravity | **Gemini 3.6 Flash High** | [`rules/role_coder.md`](rules/role_coder.md) |
| **Reviewer** | Codex | **GPT-5.6 Sol** | [`rules/role_reviewer.md`](rules/role_reviewer.md) |

There is no auto-selected or escalated model. Reviewer always runs the same model, in **two review
layers**, in a single pass — see below.

### Model settings (defaults)

- Do **not** enable Fast, Max Context, or Thinking by default.
- Prefer **small, targeted context** (git diff or changed-file list) over re-reading the full repository.

## Coder implements

**Agent**: Antigravity · **Model**: Gemini 3.6 Flash High · **Rule**: [`rules/role_coder.md`](rules/role_coder.md)

1. Read `context.md`, `implementation_plan.md`, and all files in `.agents/`.
2. Implement in **small, incremental tasks** — one logical unit per commit when possible.
3. Run tests, lint, and static analysis before handoff.
4. Produce a **git diff** (or explicit changed-file list) as the handoff artifact.
5. Self-check against the acceptance criteria in `implementation_plan.md`.

**Handoff to Reviewer must include:**

```
git diff                    # or git diff --stat + git diff <paths>
Changed files: <list>       # if diff is too large, list paths only
Acceptance criteria status: pass | partial | fail (with notes)
Commands run: <test/lint/static-analysis commands + exit codes>
```

## Reviewer reviews (diff-only, two layers, one pass)

**Agent**: Codex · **Model**: GPT-5.6 Sol · **Rule**: [`rules/role_reviewer.md`](rules/role_reviewer.md)

### Input scope — critical for token efficiency

Review **only** the supplied git diff or changed-file list plus directly related call paths.
Do **not** re-read the entire repository unless the user explicitly requests it.

### Layer 1 — Correctness & diff review

- Correctness and unintended behavior changes
- Missing input validation and error handling
- Missing or weak tests, including any test that `skip`s instead of failing when Docker/LLM
  credentials are unavailable (Week 4 tests must fail loud, never skip — see
  `.agents/implementation_plan.md` D10)
- Any reintroduced test double (`Fake*`/`Mock*`/`Stub*`/`Dummy*` class, `provider="fake"` branch) —
  none are permitted anywhere in this repository (D9)
- Any Week 3 import or provenance field (`analysis_id`, `group_key`) leaking into `gateway/` or
  `verification/` — Week 4 is self-contained (D8)
- Unnecessary complexity
- Violations of repository rules (`.agents/`, `README.md`, `Makefile`, CI)

### Layer 2 — Security deep review

Runs on **every** diff, in the same pass as Layer 1 — not conditionally, not on a different model.

- Authentication and authorization bypass
- Trust-boundary violations
- Injection and unsafe data flows
- Insecure defaults
- Business-logic vulnerabilities
- Concurrency and state inconsistencies
- Missing negative tests

Full checklist and required output format: [`rules/role_reviewer.md`](rules/role_reviewer.md).

### Constraints

- **Do not rewrite the code.** Report findings only; Coder applies fixes in a new pass.
- Ignore formatting issues already covered by linters.
- Only report **actionable** findings with clear evidence.
- Every finding must cite `File:Line` from the diff and be tagged with its layer (1 or 2).

### Required output — combined findings table

| Layer | Severity | File:Line | Issue | Why it matters | Recommended fix |
| --- | --- | --- | --- | --- | --- |
| … | … | … | … | … | … |

If no actionable issues: return the table with a single row
`— | — | — | No actionable findings | — | —`.

Always output the **Coder fix prompt** (see [`rules/role_reviewer.md`](rules/role_reviewer.md)) and
a final `VERDICT: APPROVE | REQUEST CHANGES` line.

## Automatic Coder -> Reviewer loop (Stop hook)

Antigravity and Codex are two separate tools with no native bridge between them. The bridge is a
`Stop` hook, configured in [`hooks.json`](hooks.json) under `auto-coder-reviewer-loop`, running
[`../scripts/hooks/stop_auto_review.py`](../scripts/hooks/stop_auto_review.py):

1. Coder (Antigravity) finishes a turn → Antigravity fires the `Stop` hook.
2. The hook checks `git status --porcelain` in the workspace. No uncommitted changes → it lets the
   agent stop, no review runs.
3. Otherwise it shells out to `codex exec -s read-only` running the **Reviewer** role
   (`rules/role_reviewer.md` + `review.md`, Layer 1 + Layer 2 in one pass) against `git diff HEAD`.
   Codex's default model is already `gpt-5.6-sol` (see `~/.codex/config.toml`), so no `-m` flag is
   needed. The sandbox is read-only — Reviewer can inspect the repo but never edits files.
4. The full review is saved to `reports/week-04/artifacts/auto-review-<timestamp>.md`.
5. If the review's last line is `VERDICT: APPROVE`, the hook returns `{"decision": "stop"}` and the
   session ends normally.
6. If `VERDICT: REQUEST CHANGES`, the hook returns `{"decision": "continue", "reason": "<findings +
   Coder fix prompt>"}` — Antigravity re-enters its execution loop with the Reviewer's findings
   injected directly, and Coder fixes them **without any manual copy-paste**.

**Safety valves** (both fail toward `"stop"`, never toward an unbounded loop):

- `AUTO_REVIEW_MAX_ROUNDS` (env var, default `3`) caps how many auto-continue rounds run per
  conversation, using the hook's own `executionNum` from Antigravity's Stop payload.
- If the diff is byte-identical to the last reviewed diff for this conversation (tracked in
  `.agents/.state/auto-review-<conversationId>.json`, gitignored), the hook stops instead of
  re-reviewing the same unchanged code forever.
- Any error, timeout (`AUTO_REVIEW_TIMEOUT_SECONDS`, default `1500`s), or missing `codex` binary
  fails safe to `{"decision": "stop"}` — it never blocks or crashes the Coder session.

**What this does not replace:**

- No commit ever happens automatically — [`rules/git_commit_workflow.md`](rules/git_commit_workflow.md)
  still applies; the user reviews and commits by hand.
- Once `AUTO_REVIEW_MAX_ROUNDS` is hit or Reviewer approves, a human still makes the final call on
  whether to ship. Treat the auto-loop as removing manual handoff busywork, not as removing
  oversight.
- To turn it off temporarily, set `"enabled": false` on `auto-coder-reviewer-loop` in `hooks.json`,
  or run one-off manual reviews instead: `codex review --uncommitted`.

## Loop after review

```
Coder (Antigravity) → Reviewer (Codex: Layer 1 + Layer 2, one pass)
                              ↓
                    VERDICT: APPROVE?
                     /              \
                   yes               no
                    ↓                 ↓
              Done / next phase   Coder applies fixes
                                      ↓
                                  Reviewer re-reviews (Layer 1 + Layer 2 again)
                                      ↓
                              Repeat until APPROVE or user accepts
```

## Severity scale (shared across both layers)

| Severity | Meaning |
| --- | --- |
| **Critical** | Exploitable security hole, auth bypass, secret leak, data loss |
| **High** | Real bug with security or correctness impact in plausible cases |
| **Medium** | Missing validation, weak error handling, test gap |
| **Low** | Maintainability, unnecessary complexity |
| **Info** | Observation, not blocking |
