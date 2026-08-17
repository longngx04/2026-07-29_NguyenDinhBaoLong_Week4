# Agent Instructions Directory (`.agents`)

Instruction files for AI coding agents in this repository (Claude, Antigravity, OpenCode).

## Mandatory Rule

> [!IMPORTANT]
> **Before any task**, every agent MUST read all `.md` files in this directory and follow them.
> For Week 4, also read the capstone PDF in `docs/`. `.agents/implementation_plan.md` (Settled
> decisions D1–D12) is the canonical Week 4 architecture — self-contained, no Week 3 dependency, no
> test doubles. `.agents/context.md` records the normalized contract derived from the PDF; if it
> ever disagrees with `implementation_plan.md`, the plan's settled decisions win and the conflict
> must be flagged to the user, not silently resolved.

## Roles & Supported Agents

- **Supported Coding Agents**: Claude, Antigravity, OpenCode.
- **Workflow**: Two-role workflow (Coder and Reviewer) with 2-layer review in one pass (Layer 1: Correctness & Architecture; Layer 2: Security Deep Review).
- Full pipeline and severity scale: [`workflow.md`](workflow.md)

### Token efficiency rule

Always pass **git diff or a changed-file list** between Coder and Reviewer.
Do **not** re-read the entire repository on every review cycle.

## Rules Index

| File | Applies to | Purpose |
| --- | --- | --- |
| [`context.md`](context.md) | All agents | Week 4 normalized contract derived from the PDF |
| [`implementation_plan.md`](implementation_plan.md) | All agents | Canonical Week 4 architecture — settled decisions D1–D12, phases, test matrix |
| [`security.md`](security.md) | All agents | Security invariants (secrets, Gateway boundary, no-doubles, provenance, audit safety) |
| [`review.md`](review.md) | Reviewer | Diff review checklist, severity scale, Layer 2 triggers |
| [`workflow.md`](workflow.md) | All agents | End-to-end two-role pipeline |
| [`rules/coding_agent_rules.md`](rules/coding_agent_rules.md) | Coder | Full Week 4 implementation rulebook (scope, invariants, testing, DoD) |
| [`rules/task_prompt_template.md`](rules/task_prompt_template.md) | Coder | Copy-paste task prompt — 3 gates: read-proof, small steps, mandatory `worklog/` report |
| [`rules/git_commit_workflow.md`](rules/git_commit_workflow.md) | All agents | No automatic commits without user review |
| [`hooks.json`](hooks.json) | Antigravity | `.agents/`-read enforcement hooks |
