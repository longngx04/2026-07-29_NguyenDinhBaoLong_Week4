# Coding Agent Rules — Project Sentinel Week 4

> Applies to every coding agent working on the Week 4 API Gateway and Safe Probe Tool.
>
> Priority: PDF/user requirements > security boundary > provenance/data integrity > tests > convenience.
>
> Week 4 is a **self-contained sub-project**. It does not read Week 3 artifacts and does not use the
> Week 3 analysis agent. `.agents/implementation_plan.md` — Settled decisions D1–D12 — is the
> canonical architecture; do not reintroduce a Week 3-grounded design without a new recorded decision.

## 1. Mandatory startup protocol

Before changing code:

1. Read every file under `.agents/`.
2. Read the Week 4 section of `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`.
3. Read `.agents/context.md` and `.agents/implementation_plan.md` completely — if the two disagree,
   `implementation_plan.md`'s "Settled decisions" win; flag the conflict to the user instead of
   silently picking a side.
4. Inspect at least:
   - `AGENTS.md`, `README.md`, `Makefile`, `docker-compose.yml`, `.env.example`;
   - `src/project_sentinel/cli.py`;
   - `src/project_sentinel/gateway/` and `src/project_sentinel/verification/`;
   - `configs/gateway/endpoint-allowlist.json`, `configs/verification/endpoint-catalog.json`,
     `configs/verification/probe-templates.json`, `configs/verification/probe-objectives.json`;
   - current verification schemas/tests/artifacts;
   - actual WebGoat route declarations relevant to any proposed allowlist entry.
5. State a small change plan with files, tests, risks and rollback.
6. Work one phase from `implementation_plan.md` (Phase 0–6) at a time, in order.

## 2. Week 4 scope

### MUST implement

- API Gateway before WebGoat.
- Runtime API key for the probe tool (`SENTINEL_GATEWAY_API_KEY`, header `X-Sentinel-API-Key`).
- Deny-by-default endpoint and method allowlist, agreed between the Gateway allowlist and the agent
  catalog (same `endpoint_id`, `path`, `allowed_methods` in both — tested).
- An external LLM **proposer** that returns one `ProbeProposal` from a reviewed objective and the
  endpoint catalog — untrusted input, never executed directly.
- An **IAM verification layer** (`verification/resolver.py`) that re-resolves every proposed field
  against the catalog/allowlist before anything reaches the network. Unresolved fields deny; they
  never fall back to a nearby value.
- Python Safe Probe Tool supporting GET and explicitly reviewed safe POST requests only.
- Header allowlist as fixed name → enumerated-value pairs; the agent selects a listed value, never
  a header name or free-form value.
- Timeout, rate limit and response-size cap, enforced independently by both the tool and the Gateway.
- Safe, version-controlled payload templates.
- Structured request/result audit log (request **and** response) without API-key leakage.
- Real-infrastructure tests only (see §11) — no fake/mock/stub of any kind.
- CLI/Makefile/demo flow through the Gateway using the `probe` verb.

### MUST NOT implement in Week 4

- Any read of `artifacts/analysis/`, `SecurityAnalysisRecord`, or Week 3 provenance fields
  (`analysis_id`, `group_key`, `source_finding_ids`) inside `gateway/` or `verification/`.
- Any test double: a class named `Fake*`, `Mock*`, `Stub*`, or `Dummy*`, or a `provider="fake"`
  branch, anywhere under `src/` or `tests/`.
- A test that `skip`s because Docker or an LLM key is unavailable — it must fail loudly instead.
- Direct tool-to-WebGoat requests that bypass the Gateway.
- Arbitrary target URL, method, header name, header value, or literal payload value chosen by the
  LLM proposer.
- Endpoint inference from CWE, source filename, title or LLM prose.
- Feeding `response_preview` (or any application response content) back into an LLM prompt.
- Destructive/exploit payloads or public target access.
- Week 5 HITL approval UI, general Prompt Injection filtering or PII redaction.
- Multi-Agent, MCP/A2A, GraphRAG, LangChain or unrelated infrastructure.
- Changes to WebGoat source or completed `reports/week-XX/`.

## 3. Gateway invariants

1. Gateway is the only host-facing entry point for verification traffic; canonical origin
   `http://127.0.0.1:9080`, hard-coded, never a runtime parameter.
2. WebGoat stays internal to the Docker network in the default profile; no host port.
3. Host binding is loopback only; never `0.0.0.0`.
4. Missing/wrong API key is rejected before proxying.
5. Unknown method/path is rejected before proxying.
6. Rate limit (30 req/min/key, burst 5) and request-size limits (16 KiB body, 1 KiB long-string
   field) are enforced server-side, independently of the tool.
7. Gateway logs exclude API key, authorization, cookies and bodies.
8. Gateway config/image versions are pinned and reproducible.
9. Guardrail proofs for denied/adversarial requests are measured by asserting the Nginx access log
   gained **no entry** — not by counting calls on a double (D11).

Do not weaken Gateway controls merely because the Python tool already validates input. Defense in
depth is mandatory.

## 4. Provenance, proposals and IAM verification

- Candidate provenance is `objective_id` + `proposal_id`. There is no `analysis_id`, `group_key`,
  or other Week 3 field anywhere in Week 4 code, schemas, or logs (D8).
- Objectives live only in `configs/verification/probe-objectives.json`, selected by
  `--objective-id`; there is no free-text objective from the CLI (D1).
- The proposer calls a real LLM and parses its output strictly; malformed/non-JSON output produces
  `PROPOSAL_INVALID`, never a crash and never a request.
- The resolver re-resolves every field — `endpoint_id`, `method`, parameter names, `payload_type`,
  header values — against the catalog/allowlist. Anything unresolved is denied with a reason and
  logged.
- `{"endpoint_id": null, "reason": "..."}` is a valid, successful outcome recorded as
  `NOT_APPLICABLE` — it is cheaper than fabricating a target and must stay that way (D3).
- The endpoint catalog stays at exactly the human-verified entries. Adding one requires a `source`
  reference to WebGoat source or compose config, reviewed by a human (D4).
- No arbitrary URL, host, port, scheme, header name, or literal payload value exists in the public
  execution API.

## 5. Safe request rules

Allowed:

- GET to an allowlisted endpoint.
- POST only to an endpoint explicitly allowing POST and only with a reviewed benign payload
  template.
- Bounded empty, wrong-type, special-character or long-string test values from
  `configs/verification/probe-templates.json`.
- A bounded benign request marker for correlation.

Forbidden:

- `PUT`, `PATCH`, `DELETE`, file upload or arbitrary method.
- Shell, SQL, deserialization, path-traversal or credential payloads.
- Payloads designed to persist, delete, modify real data or access the host system.
- Candidate-controlled `Host`, API-key, `Authorization`, cookie or hop-by-hop headers, or any
  header name/value the agent invented rather than selected from the allowlist.
- Automatic redirect to another origin — redirects are never followed.
- Unbounded retries or automatic POST retry.

## 6. Input, schema and provenance validation

Treat all LLM, config, Gateway and application data as untrusted.

Validation order:

1. Parse the LLM proposal as JSON.
2. Validate `schemas/probe-proposal.schema.json` (closed enums; injected `path`/`headers` keys
   rejected).
3. Resolve every field against the endpoint catalog and allowlist (`verification/resolver.py`).
4. Build a `VerificationCandidate` or a typed `Denial` using reviewed IDs only.
5. Apply `policy.validate_candidate_policy` as the final tuple check before transport.
6. Execute through the Gateway; map the real HTTP status to a result state.
7. Validate result/audit record shape before writing.
8. Write atomic artifacts/logs.

Never use permissive defaults to manufacture missing required facts. Never "repair" an invented
endpoint, header, or ID to a nearby value silently — deny it.

## 7. Secret handling

- Gateway API key (`SENTINEL_GATEWAY_API_KEY`) and LLM key (`LLM_API_KEY`) come from runtime
  environment or an approved secret mechanism.
- `.env.example` contains placeholders only.
- Never commit `.env`, API keys, tokens, cookies or captured credentials.
- Never print/log API-key headers, full environment, request headers or raw secret-bearing
  exception bodies.
- Redact the exact configured key from all exception/evidence paths as defense in depth.
- Tests that need real credentials read them from the environment and **fail** (never silently
  substitute a fake value) if absent (D10).

## 8. Network and response safety

- Tool Gateway origin is fixed configuration (`http://127.0.0.1:9080`), never candidate input.
- Only HTTP to the loopback-bound Gateway is allowed in local Week 4 scope.
- Redirects are never followed automatically.
- Timeout has a safe default (5s) and hard maximum (10s).
- Response reads are capped at `max_response_bytes`; the tool reads `max_response_bytes + 1` to set
  `truncated=true` and never calls unbounded `read()`.
- Response preview is capped at 512 bytes, stored in the result and audit record, and never fed
  back into any LLM prompt (D6).
- Connection, timeout, HTTP and policy errors return typed outcomes, never a crash.

## 9. Filesystem and logging

- Runtime writes stay under `artifacts/verification/`, `artifacts/gateway/`, or test `tmp_path`.
- JSON/JSONL writes are atomic and UTF-8.
- Failure must not leave a partial final report.
- Runtime verification artifacts are ignored unless explicitly promoted to reviewed fixtures.
- Audit ordering and IDs are deterministic where time/request IDs are injected by test clocks/
  factories.

## 10. Dependency and infrastructure rules

- Prefer standard library and existing dependencies for the Python tool.
- Nginx is the default Gateway; adding another Gateway requires explicit user approval and design
  justification.
- No `curl | sh`, downloaded executable scripts or unbounded dependency versions.
- Docker images must use explicit versions; pin digest when practical.
- Do not add privileged containers, host networking or broad filesystem mounts.

Stop for user review before:

- changing the chosen Gateway technology;
- broadening target hosts/ports;
- adding a new production dependency;
- allowing a new HTTP method/payload class;
- changing CI secrets/permissions;
- reintroducing any Week 3 dependency or provenance field into Week 4 code;
- adding back a fake/mock/stub/test-double of any kind;
- moving Week 5 controls into Week 4.

## 11. Testing rules — no test doubles, fail loud

This project contains **no test doubles**. There is no fake LLM, no fake transport, and no mock run
mode (D9). Every result — in tests, in demos, and in `artifacts/` — comes from a real request to a
real Gateway in front of a real WebGoat, or from a real LLM call. A green suite means the system was
exercised for real.

- A test that cannot reach the Gateway, or has no LLM key, **fails** with an actionable message; it
  never `skip`s (D10).
- `make agent-test` requires containers up (`make gateway-up` first); it fails, with a readable
  message, when they are down.
- Tests that spend LLM tokens live behind `make llm-test`, run on demand and nightly — everything
  else runs on every push against real containers (D12).
- Guardrail/denial behaviour is proven by asserting the Nginx access log gained no entry, not by
  asserting a double was or wasn't called (D11).

Mandatory cases (see `implementation_plan.md` "Test matrix" and "How each behaviour is proven"):

- catalog/allowlist agreement (same `endpoint_id`/`path`/`allowed_methods`);
- proposal schema rejects injected `path`/`headers` keys;
- import-boundary test: nothing under `gateway/`/`verification/` imports `analysis` or reads
  `artifacts/analysis/`;
- no-doubles guard: no `Fake`/`Mock`/`Stub`/`Dummy` class exists in `src/` or `tests/`;
- resolver denies every adversarial proposal (invented endpoint, forbidden method, literal payload,
  injected header, injected path) with no Gateway access-log entry;
- real 200/302/401/403/405/429, timeout, connection error, truncation via the real Gateway;
- audit log contains no secret field and does contain `response_preview`.

Do not delete, weaken, or skip a failing security test to make the suite green.

## 12. Backward compatibility

- Keep Week 1–2 commands and observable outputs working.
- Week 3's `analyze` pipeline is untouched by Week 4 work; do not couple it back to
  `gateway/`/`verification/`.
- Do not change normalized or analysis schemas unless the user approves a versioned migration.
- Do not overwrite committed historical artifacts during default tests.
- Historical reports are immutable.

## 13. Documentation requirements

Any Week 4 behavior change updates the relevant:

- README commands and demo flow (`probe`, not `verify`/`verify-mock`);
- architecture diagram (proposer → resolver → executor → Gateway → WebGoat);
- Gateway/allowlist/catalog configuration documentation;
- schemas and known limitations;
- `.env.example` placeholder keys;
- acceptance evidence in `reports/week-04/`.

Observed facts, inferred behavior, unknowns and future Week 5 work must be labeled separately.

## 14. Definition of Done per implementation chunk

- [ ] Scope matches the PDF Week 4 requirements and `implementation_plan.md`'s current phase.
- [ ] Gateway boundary remains mandatory and deny-by-default.
- [ ] No Week 3 import or provenance field exists under `gateway/`/`verification/`.
- [ ] No test double (`Fake`/`Mock`/`Stub`/`Dummy`, `provider="fake"`) exists anywhere in the diff.
- [ ] API key cannot appear in code, output or logs.
- [ ] Tests exercise real containers/LLM and cover success and negative paths; none `skip`.
- [ ] Existing suite passes against real infrastructure (`make gateway-up && make agent-test`).
- [ ] No historical report or WebGoat source changed.
- [ ] Docs and acceptance matrix are updated.
- [ ] Diff has been handed to a separate review round.
- [ ] No automatic commit without user approval.

## 15. Required handoff format

```markdown
## Implemented
- ...

## Files changed
- `path`: reason

## Acceptance criteria
- [ ] W4-01 ... pass/partial/fail + evidence

## Validation
| Command | Exit code | Evidence |
|---|---:|---|
| `make gateway-up && make agent-test` | 0 | ... |

## Security checks
- Gateway/API key/allowlist/rate-limit/response-cap/logging evidence
- No test doubles introduced (grep evidence)
- No Week 3 import reachable from `gateway/`/`verification/` (grep evidence)

## Remaining limitations
- ...

## Diff for reviewer
- `git diff --stat`
- `git diff -- <changed paths>`
```
