# Project Sentinel

AI-assisted SAST finding normalization, knowledge retrieval, and security analysis pipeline
evaluated on [OWASP WebGoat](https://owasp.org/www-project-webgoat/). Every request the agent
proposes is constrained by an allowlist, a human approval gate, and an independent API Gateway;
sensitive data is redacted before it reaches an external model or disk.

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
  └─> strict schema ──> IAM Resolver ──> Human Approval Gate
        └─> Safe Request Tool
              └─> 127.0.0.1:9080 Gateway ──> internal-only WebGoat
```

Three guardrail chokepoints sit across that flow. Each one is placed where every code
path must pass through it, so no caller can forget to invoke it:

```text
build_llm()        ──> RedactingProvider     # nothing reaches an external LLM unredacted
log_request()      ──> redact_structure()    # nothing reaches disk unredacted
send_probe()       ──> requires_approval()   # POST or special payload needs a human
```

Content taken from the target application is treated as untrusted data: it is scanned for
injection patterns, stripped of matched instructions, and wrapped in
`<untrusted_app_response>` tags before any model sees it.

Tài liệu target: [docs/target-webgoat.md](docs/target-webgoat.md)

---

## Repository Structure

```text
project-sentinel/
├── src/project_sentinel/         # Production Python code
│   ├── ingestion/ retrieval/     #   SAST normalization and knowledge search
│   ├── analysis/ llm/            #   Analysis pipeline and LLM providers
│   ├── guardrails/               #   Redaction, injection defence, approval, event log
│   ├── gateway/ probe/           #   Allowlist, audit log, and the only request path out
│   └── demo/                     #   Runnable guardrails demo scenario
├── tests/                        # Unit, integration tests, and fixtures
├── data/knowledge-base/          # OWASP & vulnerability knowledge base
├── configs/                      # Prompts, OpenGrep rules, gateway allowlist
├── schemas/                      # JSON Schema definitions
├── artifacts/                    # Active runtime outputs (raw, normalized, analysis, audit logs)
├── reports/                      # Historical sprint reports (week-01 … week-05)
├── benchmarks/targets/webgoat/   # WebGoat benchmark (Git submodule)
└── infra/docker/                 # Scanner image and Nginx API Gateway build context
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

# API Gateway & Safe Verification Probe
export SENTINEL_GATEWAY_API_KEY="${SENTINEL_GATEWAY_API_KEY:-$(openssl rand -hex 32)}"
make target-up        # start Gateway & WebGoat containers with health check
make probe            # run safe probe request through Gateway
make gateway-demo
make gateway-test      # focused gateway + probe tests
make gateway-live-test # real Docker Gateway + WebGoat acceptance test
make llm-test          # real OpenRouter tests, sequential by default for reliability
make target-down

# Guardrails
make guardrails-test              # guardrail unit tests + the six mandatory acceptance cases
make guardrails-demo              # interactive demo: you approve or reject each risky request
make guardrails-demo ARGS=--auto  # same scenario, unattended, for CI or capturing a log
```

`make guardrails-demo` walks seven steps and prints a pass/fail verdict for each: prompt
injection in an application response, a forged closing tag, redaction on the way to the LLM,
redaction on the way to disk, a rejected request, and an approved one. It requires the real
Gateway; the proof that a rejected request sends nothing is that the Nginx access log gains
no line, which is evidence at the infrastructure boundary rather than a call count inside
Python.

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

---

## Historical Sprint Reports

- [Week 1 Report — OpenGrep SAST Setup](reports/week-01/report.md)
- [Week 2 Report — Finding Normalization & Knowledge Retrieval](reports/week-02/report.md)
- [Week 3 Report — Security Analysis Agent & Provenance Guardrails](reports/week-03/report.md)
- [Week 4 Report — API Gateway & Safe Test Request Tool](reports/week-04/report.md)
- [Week 5 Report — Guardrails, Human-in-the-Loop & Redaction](reports/week-05/report.md)

---

## Security Invariants & Target Binding

> **SECURITY NOTE**: OWASP WebGoat is an intentionally vulnerable benchmark application.
> The `docker-compose.yml` configuration strictly binds Nginx Gateway to loopback (`127.0.0.1:9080:8080`). WebGoat container port 8080 is internal only and not exposed on host interfaces.
> Do not modify container networking to expose WebGoat or Gateway on public network interfaces (`0.0.0.0`).
