# Project Sentinel — Architecture Overview

> **Week 4 status:** Safe verification is implemented as a fail-closed Agent proposal → reviewed template → Gateway flow.

## Analysis pipeline (Week 1–3)

```text
OpenGrep
  -> artifacts/raw/opengrep.json
  -> ingestion / normalized findings
  -> deterministic knowledge retrieval
  -> bounded Security Analysis Agent
  -> schema + provenance validation
  -> artifacts/analysis/security-analysis.jsonl
```

Production modules:

| Capability | Path |
|---|---|
| Ingestion | `src/project_sentinel/ingestion/` |
| Retrieval | `src/project_sentinel/retrieval/` |
| Analysis | `src/project_sentinel/analysis/` |
| LLM adapters | `src/project_sentinel/llm/` |

## Week 4 target: Gateway-only safe verification

```text
reviewed objective selected by --objective-id
  + configs/verification/probe-objectives.json
        |
        v
external LLM Probe Proposer (untrusted JSON)
  + configs/verification/endpoint-catalog.json
        |
        v
strict proposal schema -> IAM resolver
  + endpoint catalog + Gateway allowlist + safe templates
  + exact endpoint/method/header-value/payload resolution
  + unresolved fields -> NOT_PLANNABLE / NOT_APPLICABLE
        |
        v
Python Safe Request Tool
  + fixed Gateway origin
  + API key injected internally
  + GET / reviewed safe POST only
  + timeout / redirect control / response cap
        |
        v
127.0.0.1:9080 API Gateway
  + API-key authentication
  + method/path allowlist
  + rate limit / request-size limit
  + sanitized access logs
        |
        v
WebGoat on internal Docker network only
        |
        v
verification plan + results + sanitized audit log
```

### Trust boundaries

1. **Objective boundary:** The CLI accepts only a version-controlled `objective_id`, never free-text instructions.
2. **LLM boundary:** Every proposal field is untrusted and must pass the closed proposal schema.
3. **IAM boundary:** The resolver reconstructs endpoint, method, header values and payload binding from reviewed configuration; it never executes proposal prose or arbitrary URLs.
4. **Tool boundary:** Safe Request Tool applies final tuple policy, injects credentials internally and enforces local resource caps.
5. **Gateway boundary:** Gateway independently authenticates, allowlists and rate-limits every request before WebGoat.
6. **Target boundary:** WebGoat is intentionally vulnerable and remains internal-only; it is never the host-facing verification endpoint.
7. **Output boundary:** Response content is untrusted, bounded to a 512-byte preview and never fed back to an LLM in Week 4.

### Docker network target

```text
host
  `-- 127.0.0.1:9080 -> gateway:8080
                              `-- internal network -> webgoat:8080
```

The default Compose profile must not publish WebGoat directly. A debug bypass profile, if ever introduced, requires explicit user approval and must still bind loopback on a non-default port.

### Security controls

| Control | Enforced by |
|---|---|
| Fixed local Gateway origin | Python Tool configuration |
| API-key injection and redaction | Python Tool |
| Objective/proposal provenance | Versioned objective + proposal schema |
| Endpoint/template/header provenance | IAM resolver + final tool policy |
| Method/path allowlist | Tool and Gateway |
| API-key authentication | Gateway |
| Rate/request-size limit | Python Tool and Gateway |
| Timeout/redirect/response cap | Tool, plus Gateway proxy timeouts |
| Sanitized request/result audit | Tool/pipeline |
| Internal-only WebGoat | Docker Compose networking |

### Week 5 boundary

Human approval for risky requests, Prompt Injection filtering and general sensitive-data redaction are Week 5. Week 4 nevertheless forbids arbitrary POST, unsafe payloads and secret-bearing logs.

## Runtime artifacts

```text
artifacts/
  raw/
  normalized/
  analysis/
  verification/
    probe-proposals.jsonl
    probe-results.jsonl
    run-summary.json
  gateway/
    requests.log.jsonl
```

Runtime verification artifacts are not historical reports and should remain ignored unless explicitly promoted to reviewed fixtures.
