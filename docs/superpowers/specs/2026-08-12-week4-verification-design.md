# Design Specification: Week 4 API Gateway & Safe Request Tool

**Date:** 2026-08-13

**Status:** Corrected from capstone PDF; ready for implementation review

**Branch:** `feat/week4`

## 1. Requirement source

This specification implements the Week 4 section of:

`docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`

The PDF requires an API Gateway before the vulnerable application, a dedicated testing API key, endpoint allowlisting, GET/POST support, header control, bounded response reading, request-per-minute limits, timeouts, safe payloads, sanitized request/response logs and an Agent-to-tool demo.

The previous direct-loopback `HTTPProber` design did not satisfy this requirement and is superseded by this document.

## 2. Goals

1. Convert a validated Week 3 verification proposal into a grounded safe request candidate.
2. Execute only reviewed GET or benign POST templates.
3. Force all live requests through an authenticated, allowlisted and rate-limited Gateway.
4. Keep WebGoat unavailable as a direct host target in the default topology.
5. Capture bounded evidence and sanitized audit records.
6. Keep default tests fully offline and deterministic.

## 3. Non-goals

- Exploit generation or destructive payloads.
- Arbitrary URLs, methods, headers or bodies.
- External/public target scanning.
- Week 5 approval UI, Prompt Injection response filtering or general PII redaction.
- Multi-Agent, MCP/A2A, GraphRAG or a new orchestration framework.

## 4. Architecture

```text
Week 3 analysis JSONL
        |
        v
Input schema validator
        |
        v
Grounded Candidate Planner
  + endpoint inventory
  + safe probe templates
        |
        v
Candidate schema + provenance + policy validator
        |
        v
SafeRequestTool / GatewayClient
  + fixed Gateway origin
  + API key injected internally
  + timeout / redirect policy / response cap
        |
        v
127.0.0.1:8080 API Gateway
  + API-key auth
  + method/path allowlist
  + request-size limit
  + rate limit
  + sanitized access log
        |
        v
webgoat:8080 on internal Docker network
        |
        v
VerificationResult + sanitized audit JSONL
```

## 5. Docker topology

Default local topology:

```text
host 127.0.0.1:8080 -> gateway:8080 -> webgoat:8080
```

- Gateway is the only service with a host `ports` entry.
- Gateway host binding is loopback-only.
- WebGoat uses `expose`/internal networking, not a host `ports` entry.
- Scanner access remains read-only and independent of verification traffic.
- No host networking or privileged container.

Nginx is the selected Gateway for Week 4. Its image must use an explicit version and should be digest-pinned when implementation is finalized.

## 6. Gateway controls

### 6.1 Authentication

- Testing API key is supplied at runtime as `SENTINEL_GATEWAY_API_KEY`.
- The request header name is fixed as `X-Sentinel-API-Key`.
- Gateway rejects missing or incorrect key before proxying.
- Python Tool adds the key internally; candidates cannot set or override the key header.
- Key values never appear in static configuration, logs, CLI output or artifacts.

### 6.2 Endpoint/method allowlist

- Deny by default.
- Match normalized HTTP method plus exact/path-template route.
- Unknown method/path returns a denial response without reaching WebGoat.
- Tool validates against the same logical inventory; Gateway remains authoritative.

### 6.3 Resource controls

- Baseline rate is 30 requests/minute/API-key with burst 5.
- Request-body cap is 16 KiB; an individual bounded-long-string test field is capped at 1 KiB.
- Tool timeout defaults to 5 seconds with a 10-second hard maximum; Gateway proxy timeouts must not exceed the reviewed local-demo envelope.
- Response preview cap is 64 KiB.
- No caching of sensitive responses.
- Gateway does not expose upstream internals in error pages.

### 6.4 Logging

Gateway log may contain request ID, method, normalized path, status, response bytes and latency. It must exclude API-key/auth/cookie headers, request bodies and response bodies.

## 7. Inventory contracts

### 7.1 Endpoint inventory

`configs/gateway/endpoint-allowlist.json` is version-controlled and schema-valid.

Each entry includes:

- stable `endpoint_id`;
- method and path/path template;
- allowed query/header/body fields;
- allowed safe payload-template IDs;
- per-endpoint maximum request/response bytes;
- purpose;
- source reference to actual WebGoat route declaration or reviewed endpoint documentation.

An entry without source provenance is invalid.

### 7.2 Safe probe templates

`configs/verification/probe-templates.json` contains reviewed benign requests. Templates may use only bounded values of these categories:

- empty value;
- wrong primitive type;
- bounded long string;
- benign special characters;
- request correlation marker.

Templates cannot include exploit strings, filesystem paths, credentials or arbitrary LLM-generated values.

## 8. Candidate planning

The planner consumes raw Week 3 records only after validation against `schemas/security-analysis-record.schema.json`.

Free-form `verification_steps` are untrusted proposals. They may support rationale/mapping but are never parsed into an arbitrary URL or payload.

A candidate references reviewed IDs:

```json
{
  "schema_version": "1.0",
  "candidate_id": "candidate-...",
  "analysis_record_id": "analysis-...",
  "group_id": "group-...",
  "source_finding_ids": ["opengrep-001"],
  "verification_step_index": 0,
  "endpoint_id": "webgoat-start",
  "probe_template_id": "reachability-get",
  "decision": "PLANNED",
  "decision_reason": "Mapped to a reviewed application-reachability template"
}
```

If mapping is absent or unsafe, decision is `NOT_PLANNABLE` or `REJECTED_POLICY`, and execution is forbidden.

## 9. Safe Request Tool

### 9.1 Public boundary

The public execution API accepts a validated candidate and inventory objects, not a raw URL/request.

### 9.2 Request construction

- Gateway origin is fixed configuration.
- Method/path/query/body resolve from allowlisted inventory/template IDs.
- API key and safe internal headers are injected after policy validation.
- Candidate headers cannot override `Host`, API-key, `Authorization`, `Cookie`, content length or hop-by-hop headers.

### 9.3 Redirect policy

Automatic redirects are disabled. A 3xx response is recorded as bounded evidence. If same-origin redirect support is later required, every hop must be revalidated and capped; that change needs explicit review.

### 9.4 Timeout and response cap

- Configurable timeout with a hard maximum.
- Read at most `max_response_bytes + 1`.
- Record `response_bytes_observed` and `truncated`.
- Store a bounded preview/hash, never an unbounded raw body.
- No automatic POST retry.

## 10. Result semantics

Result status distinguishes:

- `REACHABLE`: valid Gateway response proves endpoint reachability only.
- `OBSERVED`: reviewed benign expected status/indicator observed.
- `INCONCLUSIVE`: response insufficient or unexpected.
- `DENIED`: tool/Gateway policy rejection.
- `UNREACHABLE`: connection/timeout failure.
- `FAILED`: internal/schema/I/O failure.

No status asserts that a vulnerability is verified merely because an HTTP endpoint returned 2xx/3xx.

## 11. Audit contract

`artifacts/verification/request-log.jsonl` records one schema-valid entry per decision/execution with:

- UTC timestamp and request ID;
- input/candidate/plan/result provenance IDs;
- endpoint and probe-template IDs;
- method and policy decision;
- status, latency, response byte count and truncation;
- bounded error class/reason.

API key, auth/cookie headers, full header sets and raw bodies are forbidden fields.

## 12. Offline and live test strategy

Default tests use a fake transport and temporary output paths. They must prove zero network calls and cover invalid schemas, unknown endpoint, unsafe method/header/payload, redirect escape, timeout, truncation, provenance mismatch and secret-canary logging.

Live Docker tests are opt-in and local-only. They verify auth denial, allowlist denial, successful GET/POST proxying, rate limiting, direct-WebGoat unavailability and log sanitization.

## 13. Failure policy

- Invalid config/input/inventory: fail before network.
- Policy rejection: structured `DENIED`, zero network calls.
- Timeout/connection error: structured `UNREACHABLE`.
- Schema/provenance mismatch: fail result; do not fabricate/repair.
- Output failure: non-zero exit; atomic final artifacts remain intact.
- Missing API key in live mode: configuration failure, no request.

## 14. Acceptance criteria

1. Gateway is operational and mandatory for live verification.
2. WebGoat cannot be reached directly through a host-published port in default topology.
3. Missing/wrong API key and forbidden endpoint/method are denied.
4. GET and reviewed safe POST work through Gateway.
5. Rate limit, timeout and response cap are enforced.
6. Candidate endpoint/template is grounded and provenance-valid.
7. Logs contain no API key or secret canary.
8. Mock pipeline and all default tests run offline.
9. CLI demo shows Agent proposal -> candidate -> Gateway -> WebGoat -> result/log.
10. README and architecture reproduce the flow accurately.
