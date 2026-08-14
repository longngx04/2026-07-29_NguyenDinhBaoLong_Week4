# Code Review Instructions & Guidelines (`.agents/review.md`)

This document defines the review checklist, severity scale, and escalation procedures for code
changes in Project Sentinel. Week 4 architecture reference: `.agents/implementation_plan.md`
(Settled decisions D1–D12) and `.agents/rules/coding_agent_rules.md`.

---

## 1. Diff Review Checklist

When reviewing pull requests or git diffs, verify:

1. **Scope & Correctness**: Does the change accomplish its goal without introducing unintended side
   effects or breaking contracts?
2. **Path & Import References**: Are all imports pointing to `src/project_sentinel/`? Does nothing
   under `gateway/` or `verification/` import `analysis`, `SecurityAnalysisRecord`, or read
   `artifacts/analysis/` — Week 4 is self-contained and does not depend on Week 3 (D8)?
3. **No test doubles**: Does the diff add any class named `Fake*`/`Mock*`/`Stub*`/`Dummy*`, or any
   `provider="fake"` branch, anywhere under `src/` or `tests/`? None are permitted (D9) — flag as a
   blocking finding, not a style note.
4. **Proposal → resolver flow**: Does every executed request originate from an LLM `ProbeProposal`
   that was schema-validated and then re-resolved field-by-field (`endpoint_id`, `method`,
   parameter names, `payload_type`, header values) against the catalog/allowlist, never trusted
   directly? Is `endpoint_id: null` handled as `NOT_APPLICABLE`, not an error (D3)?
5. **Gateway Boundary**: Does every live probe request go through the Gateway at the fixed origin
   `http://127.0.0.1:9080`? Is WebGoat internal-only with no host port, and is the Gateway host
   binding loopback-only?
6. **Allowlist & Request Safety**: Are method/path/header/payload policies deny-by-default at both
   tool and Gateway? Are header values restricted to the catalog's enumerated list (D2) — no
   agent-authored header name or value? Can redirects, unsafe methods or arbitrary bodies bypass
   policy?
7. **Limits & Errors**: Are rate limit, timeout, response-size cap (`response_preview` ≤ 512 bytes,
   response cap 64 KiB, body cap 16 KiB), connection errors and truncation enforced and tested?
8. **Security & Secrets**: Are Gateway/LLM API keys, tokens, cookies, raw bodies and sensitive
   headers absent from code, exceptions and logs?
9. **Testing — real infrastructure only**: Do tests exercise a real Gateway/WebGoat or a real LLM
   call rather than a double? Does any test `skip` when Docker or an LLM key is missing — that is
   disallowed; it must fail loudly instead (D10)? Do denial/guardrail assertions check the Nginx
   access log gained no entry, not a double's call count (D11)? Are LLM-token-spending tests gated
   behind `make llm-test` (D12)?
10. **Provenance**: Does candidate/audit provenance use `objective_id` + `proposal_id` only, with no
    `analysis_id`/`group_key`/Week 3 field anywhere in Week 4 code, schemas, or logs (D8)?
11. **Report Invariance**: Are historical sprint reports under `reports/` left untouched?

---

## 2. Severity Scale

| Severity | Definition | Review Action |
| --- | --- | --- |
| **Critical** | Exploitable vulnerability, auth bypass, secret leak, or data destruction | Immediate block; escalation required |
| **High** | Real correctness/security bug in plausible execution paths | Must fix before merge |
| **Medium** | Missing validation, weak error handling, or test gap | Recommended fix before release |
| **Low** | Code style, minor formatting, or unnecessary complexity | Discretionary fix |
| **Info** | Informational note or suggestion | Non-blocking |

A reintroduced test double or a resurrected Week 3 dependency in `gateway/`/`verification/` is at
least **High** — it directly contradicts a settled architectural decision (D8/D9), not a style
preference.

---

## 3. Layer 2 — Security deep review (runs on every diff)

There is no conditional escalation round. **Every** diff gets a Layer 2 security pass, in the same
review, on the same model (Reviewer / Codex / GPT-5.6 Sol) — see [`rules/role_reviewer.md`](rules/role_reviewer.md).
Layer 2 gives closest attention when any of the following is true, but it still runs when none are:

1. Diff touches authentication, secrets, or credential handling.
2. Diff modifies Docker infrastructure, CI workflows, or execution boundaries.
3. Diff produced a High or Critical Layer 1 finding that needs confirmation.
4. Concurrency, state mutation, or security schema changes are made.
5. Diff changes Gateway authentication, endpoint allowlists/catalog, target exposure, redirects,
   rate limits, request methods or payload policy.
6. Diff touches the proposer/resolver boundary (`verification/proposer.py`, `verification/resolver.py`)
   — the layer responsible for treating LLM output as untrusted.
7. Diff adds or modifies anything resembling a test double, or removes the no-doubles guard test.
