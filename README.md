# Project Sentinel

AI-assisted SAST finding normalization, knowledge retrieval, and security analysis pipeline evaluated on [OWASP WebGoat](https://owasp.org/www-project-webgoat/).

---

## Pipeline Overview

```text
OpenGrep (SAST)
  └─> artifacts/raw/opengrep.json
        │
        ▼
Ingestion (Normalizer)
  └─> artifacts/normalized/findings.json
        │
        ▼
Knowledge Retrieval
  └─> data/knowledge-base/
        │
        ▼
Security Analysis Agent (LLM + Provenance Validation)
  └─> artifacts/analysis/security-analysis.jsonl
        │
        ▼
Reviewed Verification Planner + Safe Request Tool
  └─> 127.0.0.1:9080 Gateway ──> internal-only WebGoat
```

---

## Repository Structure

```text
project-sentinel/
├── src/project_sentinel/         # Production Python code (ingestion, retrieval, analysis, llm)
├── tests/                        # Unit, integration tests, and fixtures
├── data/knowledge-base/          # OWASP & vulnerability knowledge base
├── configs/                      # Prompts and OpenGrep rules
├── schemas/                      # JSON Schema definitions
├── artifacts/                    # Active runtime outputs (raw, normalized, analysis)
├── reports/                      # Historical sprint reports (week-01, week-02, week-03)
├── benchmarks/targets/webgoat/   # WebGoat benchmark (Git submodule)
└── infra/docker/scanner/         # Docker scanner environment
```

---

## Quick Start

```bash
# Clone with submodules (if downloading fresh)
git submodule update --init --recursive

# Install editable Python package
pip install -e '.[dev]'

# Run test suite
make agent-test

# Validate analysis output schema
make validate-analysis
```

---

## Common Commands

```bash
# Run OpenGrep in its isolated scanner stack (no Gateway API key required)
make scan

# Normalize raw OpenGrep output
make normalize

# Search security knowledge base
make search Q='SQL Injection'

# Real OpenRouter analysis run (requires LLM_API_KEY in .env)
cp .env.example .env
make analyze
make validate-analysis

# API Gateway & Safe Verification Probe (Week 4)
cp .env.example .env  # set SENTINEL_GATEWAY_API_KEY and LLM_API_KEY
make target-up        # start Gateway & WebGoat containers with health check
make probe OBJ=obj-health-check  # run canonical probe verification flow
make gateway-demo
make gateway-test      # focused verification tests
make gateway-live-test # real Docker Gateway + WebGoat acceptance test
make target-down
```

---

## Historical Sprint Reports

- [Week 1 Report — OpenGrep SAST Setup](reports/week-01/report.md)
- [Week 2 Report — Finding Normalization & Knowledge Retrieval](reports/week-02/report.md)
- [Week 3 Report — Security Analysis Agent & Provenance Guardrails](reports/week-03/report.md)
- [Week 4 Report — API Gateway & Safe Test Request Tool](reports/week-04/report.md)

---

## Security Invariants & Target Binding

> **SECURITY NOTE**: OWASP WebGoat is an intentionally vulnerable benchmark application.
> The `docker-compose.yml` configuration strictly binds Nginx Gateway to loopback (`127.0.0.1:9080:8080`). WebGoat container port 8080 is internal only and not exposed on host interfaces.
> Do not modify container networking to expose WebGoat or Gateway on public network interfaces (`0.0.0.0`).
