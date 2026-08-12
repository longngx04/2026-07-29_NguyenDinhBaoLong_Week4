# Automatic Model Selection — Project Sentinel

Agents **must self-select** the appropriate model tier based on task complexity.
Do not use a fixed heavy model for every task — assess difficulty first, then pick the optimal model.

See also: [`workflow.md`](workflow.md)

---

## 1. Primary Coding Agent Auto-Selection Matrix

| Task Complexity | Target Model Tier | When to use |
| --- | --- | --- |
| **Light** | Flash / Flash-Lite | Docs, README, comments, simple typos, single-file config edits |
| **Standard** | Flash (Medium) / Standard | Routine feature implementation, pipeline modules, standard unit tests |
| **Deep** | Pro / High Reasoning | Security boundaries, multi-module architecture, complex refactoring, hard bugs |

---

## 2. Subagent Auto-Selection Matrix (`invoke_subagent`)

When dispatching subagents, set the `Model` parameter automatically based on role:

| Subagent Task | `Model` Parameter | Rationale |
| --- | --- | --- |
| Quick file lookup / single grep | `'flash_lite'` | Maximum speed and lowest cost |
| Codebase research / reading docs | `'flash'` | Balanced speed and search accuracy |
| Multi-file refactor / complex debugging | `'pro'` or `'inherit'` | Deep reasoning required |

---

## 3. Review Agent Auto-Selection Matrix (Cursor Review)

| Tier | Model | Cost profile | Use when |
| --- | --- | --- | --- |
| **Light** | GPT-5.6 Luna | Lowest | Simple, low-risk diffs |
| **Standard** | Composer 2.5 Standard | Medium | Typical code changes — default when unsure |
| **Deep** | Claude Sonnet 5 Thinking | Highest | Security-sensitive or architecturally complex diffs |

### Models NOT to use routinely

- **Opus** — only if the user explicitly requests it.
- **Fast mode** — do not enable by default.
- **Max Context** — do not enable by default; prefer git diff over full-repo reads.
- **Thinking mode** on Light/Standard models — do not enable by default.

## Complexity assessment (run before every review)

Score the diff against these signals. Pick the **highest** tier that matches **any** signal.

### Light — GPT-5.6 Luna

All of the following must be true:

- ≤ 2 files changed, ≤ 50 lines added/removed (check `git diff --stat`)
- No executable logic changes (docs, comments, README, typos, `.gitignore`, formatting-only)
- No security surface: no shell scripts, Docker, CI, secrets, auth, network, filesystem writes
- Single module, no cross-file call-path changes
- No new external dependencies or config keys

### Standard — Composer 2.5 Standard

Default tier when the diff does not qualify as Light **or** Deep:

- Routine feature/fix in one module (`week2/`, `scripts/`, `rules/`)
- Straightforward logic with clear input/output
- Security surface is limited and localized (e.g. JSON parsing with existing patterns)
- ≤ 5 files, ≤ 300 lines changed
- No auth/authz/secrets handling

**When unsure between Light and Standard → pick Standard.**

### Deep — Claude Sonnet 5 Thinking

Pick this tier when **any** signal matches:

- Authentication, authorization, session, or permission logic
- Secrets, tokens, credentials, or `.env` / CI secret handling
- Shell scripts (`scripts/`), Docker (`scanner/`, `docker-compose.yml`), CI workflows (`.github/`)
- Injection risk: `subprocess`, `shell=True`, path construction, deserialization
- Multi-module change with non-obvious dependencies (e.g. `week2/` + `scripts/` + CI together)
- Concurrency, shared state, or race conditions
- Business-logic change where tests pass but behavior is hard to verify statically
- > 5 files or > 300 lines changed
- Antigravity handoff notes flag uncertainty or partial acceptance criteria

**When unsure between Standard and Deep → pick Deep.**

## Decision output (mandatory first line of every review)

Before the findings table, state:

```
MODEL SELECTED: <Light | Standard | Deep> — <model name>
COMPLEXITY: <Light | Standard | Deep> — <one-line reason citing diff signals>
```

Examples:

```
MODEL SELECTED: Light — GPT-5.6 Luna
COMPLEXITY: Light — 1 file, 12 lines, README-only change, no executable logic.
```

```
MODEL SELECTED: Deep — Claude Sonnet 5 Thinking
COMPLEXITY: Deep — diff touches scripts/scan-opengrep.sh and .github/workflows/ (CI + shell).
```

## Mid-review model upgrade

If you started on Light or Standard and **during review** discover:

- A **Critical** or **High** severity issue, or
- A security surface not visible from `git diff --stat` alone, or
- Logic too entangled to assess confidently,

then:

1. Stop the current review pass.
2. Report: `MODEL UPGRADE: <from> → Deep — <reason>`.
3. Re-run the review on **Deep** (Claude Sonnet 5 Thinking) using the same diff scope.

This replaces a separate "Round 3" when the upgrade happens mid-review.
If the review already ran on **Deep**, output the escalation sections defined in
[`rules/role_reviewer_escalation.md`](rules/role_reviewer_escalation.md) — no further model change.

## Token efficiency (always applies)

Regardless of tier:

- Input = git diff or changed-file list + directly related call paths only.
- Do **not** re-read the entire repository unless the user explicitly requests it.
- A cheaper model with a small diff beats an expensive model with full-repo context.

## Quick reference matrix

| Signal | Light | Standard | Deep |
| --- | --- | --- | --- |
| Files changed | ≤ 2 | ≤ 5 | > 5 or cross-module |
| Lines changed | ≤ 50 | ≤ 300 | > 300 |
| Docs/config only | ✓ | — | — |
| Shell / Docker / CI | ✗ | ✗ | ✓ |
| Auth / secrets | ✗ | ✗ | ✓ |
| Injection risk | ✗ | maybe | ✓ |
| Multi-module deps | ✗ | ✗ | ✓ |
| When unsure | → Standard | → Deep | — |
