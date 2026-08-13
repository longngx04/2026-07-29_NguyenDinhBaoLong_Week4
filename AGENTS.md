# Project Sentinel — Agent Guidelines (`AGENTS.md`)

> [!IMPORTANT]
> **MANDATORY RULE FOR ALL CODING AGENTS (Antigravity, Cursor, Claude, Gemini, Codex):**
> Before executing any task, generating code, or modifying files, every agent MUST inspect and read all instruction files in the `.agents/` directory (`.agents/context.md`, `.agents/rules/*.md`, `.agents/security.md`, `.agents/workflow.md`, `.agents/review.md`).
> For Week 4 work, agents MUST also read the Week 4 section of `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`; the PDF outranks stale implementation assumptions.

This repository follows a product-oriented layout for **Project Sentinel**, an AI-assisted SAST finding normalization and security analysis pipeline.

---

## 1. Project Overview & Repository Structure

Production code is organized by capability under `src/project_sentinel/`. Historical sprint reports are preserved under `reports/week-XX/`. Week identifiers are forbidden in production packages or active test namespaces.

```text
project-sentinel/
├── src/project_sentinel/         # Production Python package
│   ├── ingestion/                # OpenGrep normalization & input loading
│   ├── retrieval/                # Keyword search over data/knowledge-base/
│   ├── analysis/                 # Grouping, evidence extraction, prompt & pipeline
│   ├── verification/             # Grounded candidates and Gateway-only safe requests
│   └── llm/                      # LLM provider abstraction (FakeLLM, OpenRouter)
├── tests/
│   ├── unit/                     # Fast offline unit tests
│   ├── integration/              # Pipeline & CLI end-to-end integration tests
│   └── fixtures/                 # Deterministic test inputs & expected outputs
├── data/knowledge-base/          # Security knowledge base (OWASP, tools, vulns)
├── configs/                      # Prompts, Gateway allowlist, and probe templates
├── schemas/                      # JSON Schemas for validation
├── artifacts/                    # Runtime-generated output (raw, normalized, analysis)
├── reports/                      # Immutable historical sprint reports
├── benchmarks/targets/webgoat/   # OWASP WebGoat target (Git submodule)
├── infra/docker/scanner/         # Docker scanner build context
└── infra/docker/gateway/         # Week 4 API Gateway build context
```

---

## 2. Mandatory Rules & Invariants

1. **Behavior Preservation**: Refactoring or changes must preserve observable pipeline behavior and JSON Schema validity.
2. **Offline Test Safety**: Unit tests (`pytest -q tests`) must execute completely offline using `FakeLLM` without requiring API keys or network access.
3. **Secret Isolation**: Never commit `.env`, API keys, or print secrets in logs.
4. **Gateway-Only Target Isolation**: Week 4 verification requests must go through the API Gateway. Only Gateway may bind a loopback host port; WebGoat remains internal-only in the default profile. Never expose either component publicly.
5. **Historical Reports Protection**: Never overwrite or delete completed weekly reports (`reports/week-XX/`).
6. **No Hallucinated Evidence**: Do not invent finding IDs, paths, line numbers, CWE/OWASP mappings, or exploit payloads.
7. **Schema & Provenance Enforceable**: Post-LLM validation must reject any response violating schema or referencing non-existent input findings/locations.
8. **Deny-by-Default Requests**: Method, endpoint, headers and payload template must be explicitly allowlisted at both the Python Tool and Gateway.
9. **Bounded Execution**: Enforce rate limit, timeout, response-size cap and sanitized audit logging; never log Gateway API keys.

---

## 3. Quick Commands

```bash
# Editable install
pip install -e '.[dev]'

# Run all unit and integration tests (offline)
make agent-test          # or: pytest -q tests

# Run pipeline targets
make normalize
make search Q='SQL Injection'
make analyze-mock        # FakeLLM test run
make analyze             # Real OpenRouter run (requires .env LLM_API_KEY)
make validate-analysis   # Schema validation
```

---

## 4. Specialized Instructions

- For code diff review, severity scale, and review model escalation: see [`.agents/review.md`](.agents/review.md)
- For security boundaries, secret handling, and guardrails: see [`.agents/security.md`](.agents/security.md)
