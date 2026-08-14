# Week 4 — API Gateway & Safe Probe Tool: Implementation Plan

Week 4 is a **self-contained sub-project**. It does not read Week 3 artifacts and does not use the
Week 3 analysis agent. The capstone PDF Week 4 section and `.agents/context.md` remain the
requirements source of truth.

The Week 4 agent is an **external LLM that proposes probe parameters**. Its proposal is untrusted
and is re-verified against the same endpoint catalog it was shown, then again by the Gateway.

**This project contains no test doubles.** There is no fake LLM, no fake transport, and no mock
run mode. Every result — in tests, in demos, and in `artifacts/` — comes from a real request to a
real Gateway in front of a real WebGoat, or from a real LLM call. A green suite means the system
was exercised for real.

## Canonical flow

```text
configs/verification/probe-objectives.json   (version-controlled operator objectives)
  -> proposer builds a prompt from configs/prompts/probe-proposal-system.md
     + configs/verification/endpoint-catalog.json
  -> external LLM returns one ProbeProposal (untrusted)
  -> layer 1: schemas/probe-proposal.schema.json
  -> layer 2: resolver re-resolves every field against endpoint-catalog.json  -> DENIED or candidate
  -> layer 3: one executor, fixed http://127.0.0.1:9080 Gateway origin
  -> Nginx Gateway independently re-checks key/method/path, rate limit, body size
  -> internal-only WebGoat
```

No step in this flow reads `artifacts/analysis/`, `SecurityAnalysisRecord`, or `verification_steps`.

## Settled decisions

These were open questions; they are now decided. Revisit only with a recorded reason.

| # | Decision | Rationale |
|---|---|---|
| D1 | Objectives live in `configs/verification/probe-objectives.json`, selected by `--objective-id`; no free-text objective from the command line | Version-controlled, reviewable, reproducible. A free-text flag would make every run unreproducible and would put unreviewed text into the prompt. |
| D2 | The catalog declares `allowed_request_headers` as fixed name→enumerated-value pairs. The agent may only choose a listed value; it can never author a header name or value | Satisfies the PDF requirement "thiết lập header" without granting header control to an LLM. Header injection and credential spoofing stay impossible by construction. |
| D3 | `{"endpoint_id": null, "reason": "..."}` is a **valid, successful** outcome recorded as decision `NOT_APPLICABLE` | Forcing a probe is how the previous design produced 18/21 mis-mapped candidates. Declining must be cheaper than fabricating. |
| D4 | The catalog stays at exactly the two human-verified endpoints (`ep_health`, `ep_attack`). Adding one requires a `source` reference to WebGoat source or compose config, reviewed by a human | Invariant 6 (no hallucinated evidence). Guessed routes were the defect that forced the previous rewrite. |
| D5 | Package names `gateway/` and `verification/` stay. Independence is enforced by an automated import-boundary test, not by a folder rename | The guarantee comes from a failing test, not from a directory name. |
| D6 | Response preview is capped at 512 bytes, recorded in the result and the audit log, and **never** fed back into any LLM prompt in Week 4 | Satisfies "đọc một phần response" and "nhật ký request và response". Feeding application output back to the model is the Week 5 prompt-injection surface. |
| D7 | The CLI verb is `probe`. There is no `probe-mock`, no `verify`, no `verify-mock`, and no `--provider` flag anywhere | A mock run mode writes fake-looking records into `artifacts/`. The previous `verify-mock` wrote 21 `DENIED` records that were indistinguishable from real output. |
| D8 | Candidate provenance is `objective_id` + `proposal_id`. All Week 3 provenance fields are removed | `gateway/cli.py` currently fabricates `analysis_record_id="operator-demo"` and `cwe="CWE-N/A"`. Fabricated provenance in an audit log is worse than no provenance. |
| **D9** | **No test doubles exist in the repository.** `llm/fake.py`, `transport.FakeTransport`, and every `provider="fake"` branch are deleted | Operator decision. A double can only prove that the code matches the double's assumptions; it cannot prove the system works. |
| **D10** | **Tests fail loudly when the environment is missing.** A test that cannot reach the Gateway, or has no LLM key, reports failure — never `skip` | A skipped test yields a green suite that verified nothing. That is the same disease as a mock, wearing a different colour. |
| **D11** | Guardrail proofs are measured **at the Gateway boundary**, by asserting the Nginx access log gained no entry, not by counting calls on a double | This is a strictly stronger proof: it shows no packet reached the boundary, rather than showing our own object was not called. |
| **D12** | Tests that spend LLM tokens live behind `make llm-test`, run on demand and nightly. Everything else runs on every push against real containers | Real LLM calls cost money, are rate-limited, and are non-deterministic. Cost control is not the same thing as faking. |

## Canonical names and paths

- Secret environment variable: `SENTINEL_GATEWAY_API_KEY`; LLM key: `LLM_API_KEY`
- Internal request header: `X-Sentinel-API-Key`
- Gateway origin: `http://127.0.0.1:9080` (hard-coded; never a parameter)
- Endpoint allowlist (Gateway view): `configs/gateway/endpoint-allowlist.json`
- Endpoint catalog (agent view + IAM verification): `configs/verification/endpoint-catalog.json`
- Probe templates: `configs/verification/probe-templates.json`
- Operator objectives: `configs/verification/probe-objectives.json`
- Agent system prompt: `configs/prompts/probe-proposal-system.md`
- Proposal contract: `schemas/probe-proposal.schema.json`
- Audit JSONL: `artifacts/gateway/requests.log.jsonl`
- Run outputs: `artifacts/verification/probe-proposals.jsonl`, `probe-results.jsonl`, `run-summary.json`

The catalog and the allowlist must agree on `endpoint_id`, `path` and `allowed_methods`; a test
asserts this. The catalog adds the agent-facing description; the allowlist stays the Gateway view.

## Required controls

- Only exact GET or reviewed benign POST tuples are allowed; path matching is exact.
- Agent proposes `endpoint_id`, `method`, parameter names, `payload_type`, and listed header values
  only. It never proposes a path, URL, host, port, scheme, header name, or literal payload value.
- Tool rate: 30 requests/minute, burst 5; the Gateway independently enforces the same.
- Timeout default 5 seconds, hard maximum 10 seconds. Redirects are never followed.
- Response preview 512 bytes; response cap 64 KiB; request body cap 16 KiB; long-string payload 1 KiB.
- HTTP 429, and only explicitly tagged Gateway 503 rate limits, map to `RATE_LIMITED`, never `OBSERVED`.
- Audit records include request ID, `objective_id`, `proposal_id`, endpoint/template, policy
  decision, status, latency, byte count, truncation, response preview, and structured error.
- Audit records never accept header maps, request bodies, cookies, or secrets.
- WebGoat has no host port; only the Gateway binds `127.0.0.1:9080`.

## How each behaviour is proven without a double

Every mapping the old fake transport used to simulate has a real, deterministic trigger.

| Behaviour | Real trigger |
|---|---|
| `OBSERVED` 200 | Real GET `/WebGoat/actuator/health` through the Gateway |
| `OBSERVED` 302 | Real POST `/WebGoat/attack` unauthenticated; WebGoat really redirects |
| `DENIED` 401 / 403 / 405 | Real request with no key / unlisted path / unlisted method |
| `RATE_LIMITED` 429 | Fire 10 real requests; the Gateway's own `limit_req` returns 429 |
| `UNREACHABLE` timeout | Real Gateway with the client timeout set to 1 ms |
| `FAILED` connection error | Real connection to closed port `127.0.0.1:9099` |
| `truncated = true` | Real response with `max_response_bytes` set to 100 |
| "no packet was sent" | Read the Nginx access log before and after; assert it gained no line (D11) |

## Phases

Each phase lands independently and leaves the suite green against real infrastructure.

### Phase 0 — Sever the Week 3 dependency

- Delete `verification/planner.py` and the record-reading half of `verification/pipeline.py`.
- Remove `verify` / `verify-mock` from `cli.py` and the Makefile (D7).
- Remove Week 3 provenance fields from `VerificationCandidate`, `verification-plan.schema.json`,
  and the audit record; add `objective_id` and `proposal_id` (D8).
- Remove `accepted_proposals` from `probe-templates.json`.
- Add `tests/unit/verification/test_no_week3_imports.py` asserting that nothing under
  `src/project_sentinel/{gateway,verification}` imports `analysis`, `SecurityAnalysisRecord`, or
  reads `artifacts/analysis/`.

**Acceptance:** the boundary test passes; `grep -rn "SecurityAnalysisRecord\|security-analysis"
src/project_sentinel/{gateway,verification}` is empty.

### Phase 1 — Delete every test double

- Delete `src/project_sentinel/llm/fake.py` and the `fake` branch of `llm/factory.py`.
- Delete `FakeTransport` from `verification/transport.py` and its export in `verification/__init__.py`.
- Delete `tests/unit/llm/test_fake.py`.
- Remove `--provider` from every CLI subcommand and `analyze-mock` / `analyze-offline-full` /
  `verify-mock` from the Makefile.
- Add `tests/test_no_doubles.py`: fails if the words `Fake`, `Mock`, `Stub`, or `Dummy` appear as a
  class name anywhere under `src/` or `tests/`. This is what keeps a double from creeping back in.
- Rewrite `AGENTS.md` invariant 2. New text:
  *"**Real Verification Only**: the repository contains no fake, mock, or stub implementation.
  Tests exercise the real Gateway, the real target, and the real LLM. A test that cannot reach its
  dependency fails; it never skips."*

**Acceptance:** `grep -rn "class Fake\|class Mock\|provider.*fake" src tests` is empty; the new
guard test passes.

### Phase 2 — Rebuild the suite against real infrastructure

- Add `tests/conftest.py` session fixtures: `gateway_ready` (fails with an actionable message if
  `127.0.0.1:9080` does not answer 401) and `llm_ready` (fails if `LLM_API_KEY` is absent). Both
  fail, never skip (D10).
- Add a `gateway_access_log` fixture that snapshots `docker compose logs gateway` so tests can
  assert "no new entry" (D11).
- Rewrite the 9 tests that used `FakeTransport` using the real triggers in the table above.
- Move the 4 LLM-dependent tests (`test_analyzer`, `test_validators`, `integration/test_cli`,
  `integration/test_analysis_pipeline`) behind `make llm-test` (D12). The remaining analysis tests
  are pure functions and need no provider at all — they only need the constructed-provider call
  removed.
- `make agent-test` now starts containers first; its docstring says so.

**Acceptance:** the whole suite passes with containers up; it **fails**, with a readable message, when
they are down.

### Phase 3 — Probe proposer

- `configs/verification/probe-objectives.json`: 3–5 reviewed objectives, each with `objective_id`,
  a plain-language goal, and the finding context text to include (D1).
- `verification/proposer.py`: render prompt from catalog + objective, call the real LLM via
  `llm/openrouter.py`, parse strictly.
- Malformed or non-JSON LLM output produces a structured `PROPOSAL_INVALID` outcome, never a crash
  and never a request.
- Assertions are structural, not textual: the proposal is schema-valid and its `endpoint_id`
  resolves in the catalog. Never assert on exact model wording.

**Acceptance:** `make llm-test` shows a real proposal from a real model; an objective containing
injected instructions still yields either a catalogued proposal or `endpoint_id: null`.

### Phase 4 — IAM verification layer

- `verification/resolver.py`: `resolve_proposal(proposal, catalog, allowlist) -> VerificationCandidate | Denial`.
- Re-resolve every field: `endpoint_id`, `method`, each parameter name, each `payload_type`, each
  header value. Anything unresolved is denied with a reason and logged.
- `endpoint_id: null` resolves to `NOT_APPLICABLE` and is not an error (D3).
- `policy.validate_candidate_policy` stays as the final tuple check before transport.

**Acceptance:** for each adversarial proposal (invented endpoint, forbidden method, literal payload,
injected header, injected path), the Nginx access log gains **no entry** (D11).

### Phase 5 — Close the three PDF gaps

- Headers: catalog `allowed_request_headers`, resolver verification, executor applies only resolved
  values (D2).
- Response preview: add `response_preview` (512 bytes) to `VerificationResult`, the CLI output, and
  the audit record (D6).
- Confirm the audit log is a request **and response** record as the PDF deliverable requires.

**Acceptance:** `make probe` prints a status code and a real response excerpt; the audit record
contains `response_preview`; the secret-canary scan over the log finds nothing.

### Phase 6 — Demo, CI, report

- Extend `scripts/demo-week4.sh` with "LLM proposes → IAM verifies → tool executes", showing a
  denied proposal beside an accepted one.
- Update `.github/workflows/security-scan.yml`: bring up `docker compose` before the test step; add
  a separate nightly job for `make llm-test` with `LLM_API_KEY` as a repository secret.
- Rewrite `reports/week-04/report.md`; re-capture live evidence.
- Update `README.md`, `docs/architecture.md`, `.agents/context.md`.

**Acceptance:** the demo script runs end to end with zero failed checks; CI is green with real
containers.

## Test matrix

Nothing in this table is simulated.

| Layer | Needs | What must be proven |
|---|---|---|
| Catalog/allowlist agreement | nothing | Same `endpoint_id`, `path`, `allowed_methods` in both files |
| Proposal schema | nothing | Closed enums; injected `path`/`headers` keys rejected |
| No-doubles guard | nothing | No fake/mock/stub class exists in the repo |
| Import boundary | nothing | No Week 3 import reachable from Week 4 packages |
| Resolver (IAM) | containers | Every denial leaves the Gateway access log unchanged |
| Executor status mapping | containers | 200/302/401/403/405/429, timeout, connection error, truncation |
| Audit log | containers | Secret field names raise; `response_preview` present; no key in file |
| Live acceptance | containers | 000 direct / 401 / 403 / 405 / 200 / 429 |
| Proposer | containers + LLM key | Real model returns a schema-valid, catalogued proposal |

## Out of scope — Week 5

Prompt-injection test fixtures, human approve/reject before POST, and PII masking belong to Week 5.

The tempting boundary violation in Phase 5 is feeding `response_preview` back to the LLM. Do not.
That is precisely the surface Week 5 exists to defend.

## Verification commands

```bash
make gateway-up          # required before any test run
make agent-test
python3 -m compileall -q src/project_sentinel
make probe
make gateway-demo
make llm-test            # spends real tokens
make gateway-live-test
./scripts/demo-week4.sh
make gateway-down
```
