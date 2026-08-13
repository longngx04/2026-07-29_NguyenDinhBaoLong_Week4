# Coding Agent Rules — Project Sentinel Week 4

> Applies to every coding agent working on the Week 4 API Gateway and Safe Request Tool.
>
> Priority: PDF/user requirements > security boundary > provenance/data integrity > tests > convenience.

## 1. Mandatory startup protocol

Before changing code:

1. Read every file under `.agents/`.
2. Read the Week 4 section of `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`.
3. Read `.agents/context.md` and `.agents/implementation_plan.md` completely.
4. Inspect at least:
   - `AGENTS.md`, `README.md`, `Makefile`, `docker-compose.yml`, `.env.example`;
   - `src/project_sentinel/cli.py`;
   - `src/project_sentinel/analysis/pipeline.py`;
   - `src/project_sentinel/verification/`;
   - `schemas/security-analysis-record.schema.json`;
   - current verification schemas/tests/artifacts;
   - actual WebGoat route declarations relevant to any proposed allowlist entry.
5. State a small change plan with files, tests, risks and rollback.
6. Work one gated phase from `implementation_plan.md` at a time.

## 2. Week 4 scope

### MUST implement

- API Gateway before WebGoat.
- Runtime API key for the testing tool.
- Deny-by-default endpoint and method allowlist.
- Python Safe Request Tool supporting GET and explicitly reviewed safe POST requests.
- Header policy, timeout, rate limit and response-size cap.
- Safe, version-controlled payload templates.
- Structured request/result audit logs without API key leakage.
- Grounded candidate planning from validated Week 3 output.
- Offline fake transport and deterministic tests.
- CLI/Makefile/demo flow through Gateway.

### MUST NOT implement in Week 4

- Direct tool-to-WebGoat requests that bypass Gateway.
- Arbitrary target URL, method, header or body execution.
- Endpoint inference from CWE, source filename, title or LLM prose.
- Destructive/exploit payloads or public target access.
- Week 5 HITL UI, general Prompt Injection filtering or PII redaction.
- Multi-Agent, MCP/A2A, GraphRAG, LangChain or unrelated infrastructure.
- Changes to WebGoat source or completed `reports/week-XX/`.

## 3. Gateway invariants

1. Gateway is the only host-facing entry point for verification traffic.
2. WebGoat stays internal to the Docker network in the default profile.
3. Host binding is loopback only; never `0.0.0.0`.
4. Missing/wrong API key is rejected before proxying.
5. Unknown method/path is rejected before proxying.
6. Rate limit and request-size limits are enforced server-side.
7. Gateway logs exclude API key, authorization, cookies and bodies.
8. Gateway config/image versions are pinned and reproducible.

Do not weaken Gateway controls merely because the Python Tool already validates input. Defense in depth is mandatory.

## 4. Endpoint and payload provenance

- Every executable endpoint has a stable `endpoint_id` in a version-controlled inventory.
- Every path has a real source/router or reviewed documentation reference.
- Every executable request uses a reviewed `probe_template_id`.
- Method is part of the allowlist identity.
- POST field names, types and byte limits are explicit.
- No arbitrary URL or body field exists in the public execution API.
- Unsupported proposals produce `NOT_PLANNABLE` or `REJECTED_POLICY`; they do not fall back silently.
- `analysis_id`, `group_key` and `source_finding_ids` remain distinct and traceable.

## 5. Safe request rules

Allowed:

- GET to an allowlisted endpoint.
- POST only to an endpoint explicitly allowing POST and only with a reviewed benign payload template.
- Bounded empty, wrong-type, special-character or long-string test values.
- A bounded benign request marker for correlation.

Forbidden:

- `PUT`, `PATCH`, `DELETE`, file upload or arbitrary method.
- Shell, SQL, deserialization, path-traversal or credential payloads.
- Payloads designed to persist, delete, modify real data or access the host system.
- Candidate-controlled `Host`, API-key, `Authorization`, cookie or hop-by-hop headers.
- Automatic redirect to another origin.
- Unbounded retries or automatic POST retry.

## 6. Input, schema and provenance validation

Treat all scanner, LLM, config, Gateway and application data as untrusted.

Validation order:

1. Parse JSON/JSONL.
2. Validate Week 3 input schema.
3. Validate endpoint inventory and probe templates.
4. Build candidate using reviewed IDs only.
5. Validate candidate schema and provenance.
6. Apply request policy before transport.
7. Validate result and cross-record provenance.
8. Write atomic artifacts/logs.

Never use permissive defaults to manufacture missing required facts. Never “repair” an invented endpoint or ID to a nearby value silently.

## 7. Secret handling

- Gateway API key comes from runtime environment or an approved secret mechanism.
- `.env.example` contains placeholders only.
- Never commit `.env`, API keys, tokens, cookies or captured credentials.
- Never print/log API-key headers, full environment, request headers or raw secret-bearing exception bodies.
- Redact the exact configured key from all exception/evidence paths as defense in depth.
- Tests use obvious fake canaries and assert they are absent from logs/results.

## 8. Network and response safety

- Tool Gateway origin is fixed configuration, not candidate input.
- Only HTTP to the loopback-bound Gateway is allowed in local Week 4 scope.
- Redirects are disabled or revalidated against the exact Gateway origin.
- Timeout has a safe default and hard maximum.
- Response reads are capped; never call unbounded `read()`.
- Store status, headers allowlist, byte count, hash and bounded preview only.
- Connection, timeout, HTTP and policy errors return typed outcomes.

## 9. Filesystem and logging

- Runtime writes stay under `artifacts/verification/` or test `tmp_path`.
- JSON/JSONL writes are atomic and UTF-8.
- Failure must not leave a partial final report.
- Runtime verification artifacts are ignored unless explicitly promoted to reviewed fixtures.
- Audit ordering and IDs are deterministic where time/request IDs are injected by test clocks/factories.

## 10. Dependency and infrastructure rules

- Prefer standard library and existing dependencies for the Python Tool.
- Nginx is the default Gateway; adding another Gateway requires explicit user approval and design justification.
- No `curl | sh`, downloaded executable scripts or unbounded dependency versions.
- Docker images must use explicit versions; pin digest when practical.
- Do not add privileged containers, host networking or broad filesystem mounts.

Stop for user review before:

- changing the chosen Gateway technology;
- broadening target hosts/ports;
- adding a new production dependency;
- allowing a new HTTP method/payload class;
- changing CI secrets/permissions;
- moving Week 5 controls into Week 4.

## 11. Testing rules

Default tests must be completely offline and require no API key, Docker or external network.

Mandatory cases:

- valid GET and reviewed safe POST;
- invalid Week 3 record;
- unknown endpoint/method/template;
- unsafe method/header/payload;
- redirect escape;
- timeout/connection error;
- response truncation;
- provenance mismatch;
- empty input;
- audit secret canary;
- stable ordering/IDs;
- zero network calls in mock mode.

Live Gateway tests must be explicitly marked/opt-in and target only local Docker Compose.

Do not delete, weaken or skip a failing security test to make the suite green.

## 12. Backward compatibility

- Keep Week 1–3 commands and observable outputs working.
- Do not change normalized or analysis schemas unless the user approves a versioned migration.
- Do not overwrite committed Week 3 artifacts during default tests.
- `make agent-test` remains offline.
- Historical reports are immutable.

## 13. Documentation requirements

Any Week 4 behavior change updates the relevant:

- README commands and demo flow;
- architecture diagram;
- Gateway/allowlist configuration documentation;
- schemas and known limitations;
- `.env.example` placeholder keys;
- acceptance evidence.

Observed facts, inferred behavior, unknowns and future Week 5 work must be labeled separately.

## 14. Definition of Done per implementation chunk

- [ ] Scope matches the PDF Week 4 requirements.
- [ ] Gateway boundary remains mandatory and deny-by-default.
- [ ] Endpoint/method/payload provenance is enforced.
- [ ] API key cannot appear in code, output or logs.
- [ ] Tests cover success and negative paths.
- [ ] Existing offline suite passes.
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
| ... | 0 | ... |

## Security checks
- Gateway/API key/allowlist/rate-limit/response-cap/logging evidence

## Remaining limitations
- ...

## Diff for reviewer
- `git diff --stat`
- `git diff -- <changed paths>`
```
