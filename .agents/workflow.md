# Two-Role Workflow

Two roles for this repository. Do not skip a role or merge them unless the user explicitly overrides.

## Roles

| Role | Supported Agents | Responsibility | Rule file |
| --- | --- | --- | --- |
| **Coder** | Claude, Antigravity, OpenCode | Implement, run tests, self-check DoD, hand off diff | [`rules/coding_agent_rules.md`](rules/coding_agent_rules.md) |
| **Reviewer** | Claude, Antigravity | Layer 1 (correctness) + Layer 2 (security) in one pass | [`review.md`](review.md) |

Reviewer always runs in **two review layers** within a single pass: Layer 1 (correctness/diff) and Layer 2 (security deep review) — both run on every diff, every time.

### Token efficiency rule

- Prefer **small, targeted context** (git diff or changed-file list) over re-reading the full repository.
- Do **not** re-read the entire repository on every review cycle.

---

## Coder implements

1. Read `context.md`, `implementation_plan.md`, and all files in `.agents/`.
2. Implement in **small, incremental tasks** — one logical unit per commit when possible.
3. Run tests, lint, and static analysis before handoff.
4. Produce a **git diff** (or explicit changed-file list) as the handoff artifact.
5. Self-check against acceptance criteria in the active rebuild plan.
6. Write a worklog report to `worklog/<YYYY-MM-DD>-<task-slug>.md` using [`worklog/_TEMPLATE.md`](../worklog/_TEMPLATE.md).

**Handoff to Reviewer must include:**

```text
git diff                    # or git diff --stat + git diff <paths>
Changed files: <list>       # if diff is too large, list paths only
Acceptance criteria status: pass | partial | fail (with notes)
Commands run: <test/lint/static-analysis commands + exit codes>
```

---

## Reviewer reviews (diff-only, two layers, one pass)

### Input scope

Review **only** the supplied git diff or changed-file list plus directly related call paths.

### Layer 1 — Correctness & diff review

- Correctness and unintended behavior changes
- Missing input validation and error handling
- Missing or weak tests, including any test that `skip`s instead of failing when Docker/LLM credentials are unavailable (Week 4 tests must fail loud, never skip)
- Any reintroduced test double (`Fake*`/`Mock*`/`Stub*`/`Dummy*` class, `provider="fake"` branch) — none are permitted anywhere in this repository
- Any Week 3 import or provenance field (`analysis_id`, `group_key`) leaking into `gateway/` or `verification/` — Week 4 is self-contained
- Unnecessary complexity
- Violations of repository rules (`.agents/`, `README.md`, `Makefile`, CI)

### Layer 2 — Security deep review

Runs on **every** diff, in the same pass as Layer 1:

- Authentication and authorization bypass
- Trust-boundary violations
- Injection and unsafe data flows
- Insecure defaults
- Business-logic vulnerabilities
- Concurrency and state inconsistencies
- Missing negative tests

### Constraints

- **Do not rewrite the code.** Report findings only; Coder applies fixes in a new pass.
- Ignore formatting issues already covered by linters.
- Only report **actionable** findings with clear evidence.
- Every finding must cite `File:Line` from the diff and be tagged with its layer (1 or 2).

### Required output — combined findings table

| Layer | Severity | File:Line | Issue | Why it matters | Recommended fix |
| --- | --- | --- | --- | --- | --- |
| … | … | … | … | … | … |

If no actionable issues: return the table with a single row:
`— | — | — | No actionable findings | — | —`

Always output the **Coder fix prompt** and a final `VERDICT: APPROVE | REQUEST CHANGES` line.

---

## Review Loop

```text
Coder (Claude / Antigravity / OpenCode) ──> Reviewer (Claude / Antigravity: Layer 1 + 2)
                                                 │
                                       VERDICT: APPROVE?
                                        /              \
                                      yes               no
                                       │                 │
                                 Commit / Next task    Coder applies fixes
                                                         │
                                                       Reviewer re-reviews
                                                         │
                                                       Repeat until APPROVE
```

## Severity scale

| Severity | Meaning |
| --- | --- |
| **Critical** | Exploitable security hole, auth bypass, secret leak, data loss |
| **High** | Real bug with security or correctness impact in plausible cases |
| **Medium** | Missing validation, weak error handling, test gap |
| **Low** | Maintainability, unnecessary complexity |
| **Info** | Observation, non-blocking note |
