# Project Sentinel — Architecture Overview

Project Sentinel is a product-oriented security finding normalization and AI-assisted analysis pipeline.

---

## Pipeline Overview

```text
OpenGrep (SAST Scanner)
  └─> artifacts/raw/opengrep.json
        │
        ▼
ingestion (project_sentinel.ingestion.normalizer)
  └─> artifacts/normalized/findings.json
        │
        ▼
retrieval (project_sentinel.retrieval.keyword_search)
  └─> data/knowledge-base/ (OWASP, vulnerabilities, tools)
        │
        ▼
analysis (project_sentinel.analysis)
  ├─> Evidence Extraction (source code windows)
  ├─> Deduplication & Grouping
  ├─> Prompt Construction (configs/prompts/)
  └─> Bounded Security Analysis Agent (project_sentinel.llm)
        │
        ▼
validation & analysis output
  ├─> Schema Validation (schemas/security-analysis-record.schema.json)
  ├─> Provenance Check (anti-hallucination)
  └─> artifacts/analysis/
        ├─> security-analysis.jsonl
        └─> run-summary.json
        │
        ▼
verification (project_sentinel.verification)
  ├─> Safe Request Candidate Planner
  ├─> Local Target HTTP Prober (127.0.0.1:8080) / Offline FakeProber
  └─> artifacts/verification/
        ├─> verification-plan.json
        └─> verification-results.jsonl
```

---

## Module Ownership & Responsibilities

| Module | Location | Responsibilities |
| --- | --- | --- |
| **Ingestion** | `src/project_sentinel/ingestion/` | Parses raw SAST scanner JSON (OpenGrep) and converts to normalized JSON schemas (`findings.json`). |
| **Retrieval** | `src/project_sentinel/retrieval/` | Performs deterministic keyword and alias search over `data/knowledge-base/` markdown files. |
| **Analysis** | `src/project_sentinel/analysis/` | Groups duplicate findings, extracts source code windows, builds analysis packets, validates outputs. |
| **LLM Provider** | `src/project_sentinel/llm/` | Implements provider boundaries (`FakeLLM` for offline/tests, `OpenRouterClient` for production). |
| **Verification** | `src/project_sentinel/verification/` | Deterministic verification request candidate planner, safe local HTTP prober (`127.0.0.1:8080`), offline `FakeProber`. |
| **CLI & Config** | `src/project_sentinel/` | `cli.py` entry point and `config.py` environment/path configuration. |

---

## Security Boundaries

1. **Deterministic Preprocessing**: Data loading, grouping, path validation, and retrieval are strictly code-driven before LLM invocation to prevent prompt injection and hallucination.
2. **Post-LLM Enforceable Validation**: LLM outputs are treated as untrusted and validated against JSON Schemas and input provenance records before writing to disk.
3. **Loopback Isolation**: WebGoat benchmark target is isolated to `127.0.0.1`.
