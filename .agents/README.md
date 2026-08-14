# Agent Instructions Directory (`.agents`)

Instruction files for AI coding agents in this repository (Antigravity as Coder, Codex as Reviewer).

## Mandatory Rule

> [!IMPORTANT]
> **Before any task**, every agent MUST read all `.md` files in this directory and follow them.
> For Week 4, also read the capstone PDF in `docs/`. `.agents/implementation_plan.md` (Settled
> decisions D1–D12) is the canonical Week 4 architecture — self-contained, no Week 3 dependency, no
> test doubles. `.agents/context.md` records the normalized contract derived from the PDF; if it
> ever disagrees with `implementation_plan.md`, the plan's settled decisions win and the conflict
> must be flagged to the user, not silently resolved.

## Two-Role Workflow

| Role | Agent | Model | Rule file |
| --- | --- | --- | --- |
| **Coder** | Antigravity | **Gemini 3.6 Flash High** | [`rules/role_coder.md`](rules/role_coder.md) |
| **Reviewer** | Codex | **GPT-5.6 Sol** | [`rules/role_reviewer.md`](rules/role_reviewer.md) |

There is no model auto-selection and no separate escalation round. Reviewer always runs the same
model, in **two review layers** within a single pass: Layer 1 (correctness/diff) and Layer 2
(security deep review) — both run on every diff, every time.

**Coder → Reviewer handoff is automatic.** Antigravity and Codex are separate tools with no native
bridge, so a `Stop` hook (`hooks.json` → `auto-coder-reviewer-loop` →
[`scripts/hooks/stop_auto_review.py`](../scripts/hooks/stop_auto_review.py)) shells out to
`codex exec` as Reviewer as soon as Coder stops, and feeds `REQUEST CHANGES` findings straight back
into Coder's loop. See [`workflow.md`](workflow.md) § "Automatic Coder -> Reviewer loop" for the
full mechanism and its safety caps (`AUTO_REVIEW_MAX_ROUNDS`, no-diff-change short circuit).

Full pipeline and severity scale: [`workflow.md`](workflow.md)

### Token efficiency rule

Always pass **git diff or a changed-file list** between Coder and Reviewer.
Do **not** re-read the entire repository on every review cycle.

### Model defaults

- Do not enable Fast, Max Context, or Thinking by default.
- Models are fixed per role (see table above) — do not substitute a different model.

## Rules Index

| File | Applies to | Purpose |
| --- | --- | --- |
| [`context.md`](context.md) | All agents | Week 4 normalized contract derived from the PDF |
| [`implementation_plan.md`](implementation_plan.md) | All agents | Canonical Week 4 architecture — settled decisions D1–D12, phases, test matrix |
| [`security.md`](security.md) | All agents | Security invariants (secrets, Gateway boundary, no-doubles, provenance, audit safety) |
| [`review.md`](review.md) | Reviewer | Diff review checklist, severity scale, Layer 2 triggers |
| [`workflow.md`](workflow.md) | All agents | End-to-end two-role pipeline |
| [`rules/coding_agent_rules.md`](rules/coding_agent_rules.md) | Coder | Full Week 4 implementation rulebook (scope, invariants, testing, DoD) |
| [`rules/role_coder.md`](rules/role_coder.md) | Coder (Antigravity) | Implement, test, hand off diff |
| [`rules/role_reviewer.md`](rules/role_reviewer.md) | Reviewer (Codex) | Layer 1 + Layer 2 review in one pass, findings table |
| [`rules/git_commit_workflow.md`](rules/git_commit_workflow.md) | All agents | No automatic commits without user review |
| [`hooks.json`](hooks.json) | Antigravity | `.agents/`-read enforcement + `auto-coder-reviewer-loop` Stop hook |
