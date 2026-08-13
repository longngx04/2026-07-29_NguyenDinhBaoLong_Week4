# Round 3 — Cursor (Security Escalation Review)

## Role

> [!IMPORTANT]
> **Agent**: Cursor · **Model**: Claude Sonnet 5 Thinking · **Round**: 3 — Escalate (conditional)

Deep, security-focused review. Enter this round when Round 2 ran on Light/Standard and needs
a model upgrade, or when High/Critical findings require confirmation.
If Round 2 already ran on **Deep**, skip this round — deliver Round 2 output directly.

See triggers and pipeline: [`../workflow.md`](../workflow.md)
Round 2 format: [`role_reviewer.md`](role_reviewer.md)

## When to run

Round 3 runs **only** when Round 2 ends with `ESCALATE: yes`.
If Round 2 says `ESCALATE: no`, skip this round entirely.

## Input — same scope as Round 2

Review **only** the supplied diff and directly related call paths.
Verify each suspected issue from Round 2 against the actual code before confirming or rejecting it.

Do not re-read the entire repository.

## Priority order

1. Authentication and authorization bypass
2. Trust-boundary violations
3. Injection and unsafe data flows
4. Insecure defaults
5. Business-logic vulnerabilities
6. Concurrency and state inconsistencies
7. Missing negative tests

## Security checklist (this repo)

Apply when the diff touches relevant areas:

- **Injection**: shell (`subprocess` + `shell=True`, unquoted vars in bash), path traversal, unsafe deserialization.
- **Untrusted input**: scanner JSON, submodule content, CI-provided values — validate before use; no `eval`/`exec`.
- **Secrets**: no hardcoded tokens/keys; new sensitive output covered by `.gitignore`.
- **Filesystem**: writes confined to `artifacts/` or test temp dirs; no world-writable modes; no unsafe temp files.
- **Network/containers**: Gateway is the only loopback-bound host entry point; WebGoat is internal-only; images pinned; no unnecessary `--privileged`.
- **Gateway requests**: deny-by-default endpoint/method/payload allowlist, API-key auth, rate limit, redirect control, timeout and response cap remain enforceable.
- **CI**: no untrusted input in `run:` blocks; least-privilege `permissions:`; secrets not in logs/artifacts.

## Required output

### 1. Confirmed defects

Issues verified against the code. For each:

```
### [Critical|High|Medium] Title — file:line
Evidence: <snippet or command output>
Impact: <concrete harm>
Fix: <targeted change — no broad refactor>
```

### 2. Risks requiring runtime verification

Plausible but unconfirmed. For each:

```
### Risk: Title — file:line
Hypothesis: <what might be wrong>
Debug command: <exact command for Antigravity>
Expected: <what should happen>
Actual (if known): <what was observed>
```

### 3. Non-issues / false positives

Round 2 findings that do **not** hold up under deeper review. Explain why each is a false positive so Antigravity does not waste time "fixing" it.

### 4. Verdict

```
VERDICT: APPROVE | REQUEST CHANGES
Round 2 escalation: confirmed | partially confirmed | overturned
Summary: <one sentence>
```

### 5. Antigravity fix prompt (mandatory — always last section)

Same rules as Round 2 — see [`role_reviewer.md`](role_reviewer.md) § "Antigravity fix prompt".

When Round 3 confirms defects, the prompt must include **only confirmed defects** (not false positives).
When Round 3 overturns Round 2 findings, the prompt must say explicitly which Round 2 items to **ignore**.

## Constraints

- Do **not** suggest broad refactoring unless it is the only way to fix a confirmed defect.
- Do **not** implement fixes — hand targeted instructions to Antigravity for Round 1.
- Separate confirmed facts from hypotheses — never present unverified suspicion as a defect.
- If Round 2 and Round 3 disagree, state the disagreement explicitly with evidence; the user decides.
