# Agent Instructions Directory (`.agents`)

Instruction files for AI coding agents in this repository (Antigravity, Cursor, etc.).

## Mandatory Rule

> [!IMPORTANT]
> **Before any task**, every agent MUST read all `.md` files in this directory and follow them.
> For Week 4, also read the capstone PDF in `docs/`; `.agents/context.md` records the normalized executable contract derived from it.

## Three-Round Workflow

| Round | Agent | Model | Rule file |
| --- | --- | --- | --- |
| **1 — Implement** | Antigravity | Gemini 3.6 Flash | [`rules/role_coder.md`](rules/role_coder.md) |
| **2 — Review (diff-only)** | Cursor | **Auto-select by complexity** | [`rules/role_reviewer.md`](rules/role_reviewer.md) |
| **3 — Escalate (conditional)** | Cursor | Claude Sonnet 5 Thinking | [`rules/role_reviewer_escalation.md`](rules/role_reviewer_escalation.md) |

**Cursor model auto-selection** (Round 2):

| Complexity | Model | When |
| --- | --- | --- |
| Light | GPT-5.6 Luna | Docs/config, ≤2 files, ≤50 lines, no security surface |
| Standard | Composer 2.5 Standard | Routine code, single module — default when unsure |
| Deep | Claude Sonnet 5 Thinking | Auth/secrets, shell/Docker/CI, multi-module, large diffs |

Full rules: [`rules/model_selection.md`](rules/model_selection.md)

Full pipeline, escalation triggers, and severity scale: [`workflow.md`](workflow.md)

### Token efficiency rule

Always pass **git diff or a changed-file list** between rounds.
Do **not** re-read the entire repository on every review cycle.

### Model defaults

- Do not enable Fast, Max Context, or Thinking by default.
- Do not use Opus for routine work.

## Rules Index

| File | Applies to | Purpose |
| --- | --- | --- |
| [`workflow.md`](workflow.md) | All agents | End-to-end 3-round pipeline |
| [`rules/role_coder.md`](rules/role_coder.md) | Antigravity | Round 1 — implement, test, hand off diff |
| [`rules/model_selection.md`](rules/model_selection.md) | Cursor | Auto-select review model by diff complexity |
| [`rules/role_reviewer.md`](rules/role_reviewer.md) | Cursor | Round 2 — diff-only review, findings table |
| [`rules/role_reviewer_escalation.md`](rules/role_reviewer_escalation.md) | Cursor | Round 3 — security escalation when triggered |
