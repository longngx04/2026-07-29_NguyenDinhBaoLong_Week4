# Week 4 API Gateway & Safe Request Tool — Execution Plan

> Implement only after reading `.agents/context.md`, `.agents/implementation_plan.md`, `.agents/security.md` and the corrected Week 4 design specification.

This file is the short execution checklist. The authoritative phased detail is `.agents/implementation_plan.md`.

## Gate 0 — Requirements and contracts

- [ ] Confirm PDF Week 4 acceptance matrix W4-01 through W4-12.
- [ ] Inventory real WebGoat endpoints from source/documentation.
- [ ] Define endpoint allowlist, probe templates and schemas.
- [ ] Reject all guessed routes from the previous implementation.
- [ ] Review candidate/result/audit semantics before network code changes.

Evidence: reviewed schema/config diff and source references for every endpoint.

## Gate 1 — Grounded planner

- [ ] Validate every Week 3 record before conversion.
- [ ] Preserve analysis/group/finding/step provenance exactly.
- [ ] Resolve only reviewed endpoint/template IDs.
- [ ] Unsupported proposals become `NOT_PLANNABLE`.
- [ ] Add negative tests for invented endpoint prose and invalid input.

Evidence: offline planner tests, deterministic IDs/order, no network.

## Gate 2 — Gateway boundary

- [ ] Add Nginx Gateway service and configuration.
- [ ] Move WebGoat to internal-only networking.
- [ ] Bind Gateway to `127.0.0.1` only.
- [ ] Add runtime API-key authentication.
- [ ] Add method/path allowlist, rate limit, request-size limit and proxy timeouts.
- [ ] Ensure Gateway logs omit API key/auth/cookies/bodies.

Evidence: `docker compose config`, Gateway config test and local denial/success cases.

## Gate 3 — Safe Request Tool

- [ ] Accept candidates/inventory, not raw URLs.
- [ ] Support allowlisted GET and safe POST templates.
- [ ] Reject unsafe methods, headers and bodies before transport.
- [ ] Disable redirects.
- [ ] Enforce timeout and response cap.
- [ ] Handle HTTP/timeout/connection errors structurally.
- [ ] Ensure API key never appears in result/error/log output.

Evidence: fake-transport adversarial tests proving zero unsafe network calls.

## Gate 4 — Audit and end-to-end pipeline

- [ ] Cross-validate input, candidate, plan and result provenance.
- [ ] Write plan/results/audit/summary atomically.
- [ ] Distinguish reachability from observation/reproduction.
- [ ] Handle empty and partially unplannable input honestly.
- [ ] Add CLI and Make targets for mock/live/validation.

Evidence: schema-valid artifacts in `tmp_path`, no fabricated success.

## Gate 5 — Documentation and acceptance

- [ ] Update README setup/demo/teardown.
- [ ] Update architecture diagram and known limitations.
- [ ] Ignore runtime verification artifacts.
- [ ] Run full offline tests and compile checks.
- [ ] Run opt-in local Gateway acceptance suite.
- [ ] Scan logs/diff for API-key canary and secrets.
- [ ] Produce reviewer handoff; do not commit automatically.

## Required verification commands

```bash
make agent-test
python3 -m compileall -q src/project_sentinel
git diff --check
docker compose config
docker compose build gateway
make gateway-up
make verify
make gateway-down
```

Live commands are local-only and must not run in default CI.

## Kill conditions

Stop the phase and request review if implementation would:

- publish WebGoat directly or bind a public interface;
- store API key in source/generated config committed to git/logs;
- allow arbitrary URL, method, header or request body;
- parse LLM prose into executable endpoint/payload without reviewed inventory;
- add exploit/destructive payloads;
- weaken an existing Week 1–3 schema/provenance guardrail;
- expand into Week 5 approval/Prompt Injection/PII features.
