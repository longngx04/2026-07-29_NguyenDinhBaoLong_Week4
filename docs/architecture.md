# Project Sentinel — Architecture Overview

> **Week 4 status:** The Gateway section below is the target architecture required by the capstone PDF. The current `feat/week4` direct-prober implementation does not yet satisfy it.

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
security-analysis.jsonl
        |
        v
validated grounded candidate planner
  + configs/gateway/endpoint-allowlist.json
  + configs/verification/probe-templates.json
        |
        v
Python Safe Request Tool
  + fixed Gateway origin
  + API key injected internally
  + GET / reviewed safe POST only
  + timeout / redirect control / response cap
        |
        v
127.0.0.1:8080 API Gateway
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

1. **LLM/scanner boundary:** Week 3 records and `verification_steps` are untrusted until schema/provenance validation.
2. **Candidate boundary:** Planner may reference reviewed endpoint/template IDs only; it never executes prose or arbitrary URLs.
3. **Tool boundary:** Safe Request Tool reconstructs the request from inventory, injects credentials internally and applies local policy/resource caps.
4. **Gateway boundary:** Gateway independently authenticates, allowlists and rate-limits every request before WebGoat.
5. **Target boundary:** WebGoat is intentionally vulnerable and remains internal-only; it is never the host-facing verification endpoint.
6. **Output boundary:** Response content is untrusted, bounded and logged only as sanitized metadata/preview.

### Docker network target

```text
host
  `-- 127.0.0.1:8080 -> gateway:8080
                              `-- internal network -> webgoat:8080
```

The default Compose profile must not publish WebGoat directly. A debug bypass profile, if ever introduced, requires explicit user approval and must still bind loopback on a non-default port.

### Security controls

| Control | Enforced by |
|---|---|
| Fixed local Gateway origin | Python Tool configuration |
| API-key injection and redaction | Python Tool |
| Endpoint/template provenance | Planner + validators |
| Method/header/payload policy | Tool and Gateway |
| API-key authentication | Gateway |
| Rate/request-size limit | Gateway |
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
    verification-plan.json
    verification-results.jsonl
    request-log.jsonl
    run-summary.json
```

Runtime verification artifacts are not historical reports and should remain ignored unless explicitly promoted to reviewed fixtures.
