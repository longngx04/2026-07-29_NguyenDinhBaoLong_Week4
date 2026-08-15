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
Reviewed Objective ──> External LLM Probe Proposer
  └─> strict schema ──> IAM Resolver ──> Safe Request Tool
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

Prerequisites:

- Python 3.10 or newer (CI uses Python 3.12).
- Docker Engine with Docker Compose v2.
- Git, `curl`, `jq`, and `openssl` available on the host.
- Outbound network access for the first container build and live LLM tests.

```bash
# Clone with submodules (if downloading fresh)
git submodule update --init --recursive

# Create an isolated environment and install the locked grader dependencies.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Generate an ephemeral Gateway credential for this shell. It is never printed
# or written to Git; repeat this export in a new shell when needed.
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"

# Run the non-LLM test suite against the real Gateway and WebGoat.
# the target containers are started automatically and left running for debugging.
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

# Real OpenRouter analysis run. Read the key without echoing it or storing it in
# shell history; alternatively put it in an untracked .env copied from .env.example.
read -rsp 'OpenRouter API key: ' LLM_API_KEY && export LLM_API_KEY && printf '\n'
make analyze
make validate-analysis

# API Gateway & Safe Verification Probe (Week 4)
export SENTINEL_GATEWAY_API_KEY="${SENTINEL_GATEWAY_API_KEY:-$(openssl rand -hex 32)}"
make target-up        # start Gateway & WebGoat containers with health check
make probe OBJ=obj-health-check  # run canonical probe verification flow
make gateway-demo
make gateway-test      # focused verification tests
make gateway-live-test # real Docker Gateway + WebGoat acceptance test
make llm-test          # real OpenRouter tests, sequential by default for reliability
./scripts/demo-week4.sh --keep-up  # full Agent -> IAM -> Gateway demo
make target-down
```

`requirements.txt` is the locked, pip-compatible grader entry point exported from `uv.lock`; it
installs this repository in editable mode. After an intentional dependency change in
`pyproject.toml`, regenerate both files with:

```bash
uv lock
uv export --locked --extra dev --no-hashes --output-file requirements.txt
```

`make llm-test` bounds grader runs to one pytest worker, one finding-group request at a time, and a
60-second absolute provider deadline with no transport retry. Production runs keep the runtime values from
`.env`; the live suite retains one schema-validation retry for malformed model output.

The Week 4 flow is self-contained: it selects a reviewed objective from
`configs/verification/probe-objectives.json`; it does not read Week 3 analysis artifacts. LLM output
is untrusted until schema validation and exact resolution against the endpoint catalog, Gateway
allowlist, header values, and safe payload templates.

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
