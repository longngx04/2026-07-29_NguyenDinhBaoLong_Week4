# Security Guidelines & Invariants

## 1. Secret isolation

- Never commit `.env`, Gateway API keys, LLM keys, tokens, cookies or credentials.
- `.env.example` contains placeholders only.
- Never log API-key/Authorization/Cookie headers, full environment, raw secret-bearing exceptions or full request/response bodies.
- Tests must use fake canaries and assert those values are absent from results and logs.

## 2. Real verification & No test doubles

- The repository contains no fake, mock, stub, or dummy implementations (D9).
- Verification tests run against the real Gateway and WebGoat target (D10).
- Pure logic tests (grouping, parsing, schema validation, rate limit bucket, allowlist matching) run offline with deterministic inputs without mock objects.
- LLM tests requiring model tokens run via `make llm-test` (D12).
- Tests that cannot reach an external dependency fail loudly with an actionable message; they never skip.

## 3. Gateway and vulnerable-target isolation

- Week 4 verification traffic must pass through the API Gateway.
- Only Gateway may publish a host port; the Week 4 canonical origin is `http://127.0.0.1:9080`.
- WebGoat must remain on the internal Docker network in the default profile and must not publish a host port that bypasses Gateway.
- Never use host networking, `0.0.0.0`, public interfaces or external targets.
- Missing/wrong Gateway API key, unknown endpoint or disallowed method must be rejected before proxying.

## 4. Deny-by-default request policy

- Tool accepts stable `endpoint_id`/`probe_template_id`, not arbitrary URLs or bodies.
- Gateway and tool independently enforce the reviewed method/path allowlist.
- Only GET and explicitly reviewed benign POST templates are allowed.
- Reject `PUT`, `PATCH`, `DELETE`, file uploads, arbitrary headers and automatic cross-origin redirects.
- Do not generate or send destructive, exploit, system-access or persistent-state payloads.

## 5. Resource limits

- Gateway enforces request-per-minute and request-body limits.
- Tool enforces timeout, hard response-byte cap and bounded retries.
- Never call an unbounded response `read()`.
- Never automatically retry POST.

## 6. Provenance and anti-hallucination

- Select objectives only from version-controlled `configs/verification/probe-objectives.json`.
- Preserve `objective_id` and the real LLM-provided `proposal_id` through candidate, result and audit records.
- Validate the untrusted proposal schema, then re-resolve every executable field against the reviewed catalog and allowlist.
- Every executable route and payload template must exist in reviewed version-controlled inventory with a real source reference.
- Never infer endpoints from CWE, title, source filename or LLM prose.
- Unsupported proposals become `NOT_APPLICABLE`/`NOT_PLANNABLE`; never silently fall back.
- Nothing under `gateway/` or `verification/` may read Week 3 analysis artifacts or fabricate Week 3 provenance.

## 7. Audit safety

- Audit only request ID, timestamp, provenance IDs, endpoint ID, method, payload-template ID, status, latency, byte count, truncation and error class.
- Prefer hashes and bounded previews over raw content.
- Logs must remain useful without exposing API keys, auth/session data or sensitive payload/response content.

## 8. Scope boundary

- Human approval, Prompt Injection response filtering and general PII redaction are Week 5.
- Their absence in Week 4 does not permit unsafe logging, arbitrary POST or Gateway bypass.
- Do not modify WebGoat source or completed historical reports.
