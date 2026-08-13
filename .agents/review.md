# Code Review Instructions & Guidelines (`.agents/review.md`)

This document defines the review checklist, severity scale, and escalation procedures for code changes in Project Sentinel.

---

## 1. Diff Review Checklist

When reviewing pull requests or git diffs, verify:

1. **Scope & Correctness**: Does the change accomplish its goal without introducing unintended side effects or breaking contracts?
2. **Path & Import References**: Are all imports pointing to `src/project_sentinel/`? Are legacy `week2/` or `week3/` paths avoided?
3. **Validation & Provenance**: Is Week 3 input schema-valid? Do `analysis_id`, `group_key`, finding IDs, endpoint IDs, template IDs and result IDs remain traceable?
4. **Gateway Boundary**: Does every live verification request go through the Gateway? Is WebGoat internal-only and the Gateway host binding loopback-only?
5. **Allowlist & Request Safety**: Are method/path/header/payload policies deny-by-default at both tool and Gateway? Can redirects, unsafe methods or arbitrary bodies bypass policy?
6. **Limits & Errors**: Are rate limit, timeout, response-size cap, connection errors and truncation enforced and tested?
7. **Security & Secrets**: Are Gateway/LLM API keys, tokens, cookies, raw bodies and sensitive headers absent from code, exceptions and logs?
8. **Testing**: Are default tests offline and do they include negative/adversarial cases, not only schema-valid happy paths?
9. **Report Invariance**: Are historical sprint reports under `reports/` left untouched?

---

## 2. Severity Scale

| Severity | Definition | Review Action |
| --- | --- | --- |
| **Critical** | Exploitable vulnerability, auth bypass, secret leak, or data destruction | Immediate block; escalation required |
| **High** | Real correctness/security bug in plausible execution paths | Must fix before merge |
| **Medium** | Missing validation, weak error handling, or test gap | Recommended fix before release |
| **Low** | Code style, minor formatting, or unnecessary complexity | Discretionary fix |
| **Info** | Informational note or suggestion | Non-blocking |

---

## 3. Escalation Conditions (Round 3 Deep Pass)

Escalate to a Deep Review pass if any of the following triggers occur:
1. Diff touches authentication, secrets, or credential handling.
2. Diff modifies Docker infrastructure, CI workflows, or execution boundaries.
3. Unconfirmed High or Critical severity findings exist.
4. Concurrency, state mutation, or security schema changes are made.
5. Diff changes Gateway authentication, endpoint allowlists, target exposure, redirects, rate limits, request methods or payload policy.
