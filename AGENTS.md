# Project Sentinel — Agent Guidelines (`AGENTS.md`)

> [!IMPORTANT]
> **MANDATORY RULE FOR ALL CODING AGENTS (Antigravity, Cursor, Claude, Gemini, Codex):**
> Before executing any task, generating code, or modifying files, every agent MUST inspect and read all instruction files in the `.agents/` directory (`.agents/context.md`, `.agents/rules/*.md`, `.agents/security.md`, `.agents/workflow.md`, `.agents/review.md`).
> For Week 4 work, agents MUST also read the Week 4 section of `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`; the PDF outranks stale implementation assumptions.
>
> **AFTER finishing any task**, the agent MUST write one report file to `worklog/<YYYY-MM-DD>-<task-slug>.md` using [`worklog/_TEMPLATE.md`](worklog/_TEMPLATE.md) — what was done, how, real output, the task's function, and why that implementation was chosen. A task without its worklog file is not complete.
> The copy-paste task prompt enforcing this (read-proof gate → small steps → worklog) is [`.agents/rules/task_prompt_template.md`](.agents/rules/task_prompt_template.md).

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
│   └── llm/                      # LLM provider abstraction (OpenRouter)
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Pipeline & CLI end-to-end integration tests
│   └── fixtures/                 # Deterministic test inputs & expected outputs
├── data/knowledge-base/          # Security knowledge base (OWASP, tools, vulns)
├── configs/                      # Prompts, Gateway allowlist, and probe templates
├── schemas/                      # JSON Schemas for validation
├── artifacts/                    # Runtime-generated output (raw, normalized, analysis)
├── reports/                      # Immutable historical sprint reports
├── worklog/                      # Per-task agent reports (mandatory after every task)
├── benchmarks/targets/webgoat/   # OWASP WebGoat target (Git submodule)
├── infra/docker/scanner/         # Docker scanner build context
└── infra/docker/gateway/         # Week 4 API Gateway build context
```

---

## 2. Mandatory Rules & Invariants

1. **Behavior Preservation**: Refactoring or changes must preserve observable pipeline behavior and JSON Schema validity.
2. **Real Verification Only**: The repository contains no fake, mock, or stub implementation. Tests exercise the real Gateway, the real target, and the real LLM. A test that cannot reach its dependency fails; it never skips.
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
# Locked editable install
python -m pip install -r requirements.txt

# Run tests
make agent-test          # Real Gateway + WebGoat; excludes token-spending LLM tests
# With Gateway already up: pytest -m "not llm" -q tests
make llm-test            # Real LLM tests (requires LLM_API_KEY)
make gateway-live-test   # Real Gateway + WebGoat tests (requires Docker)

# Run pipeline targets
make normalize
make search Q='SQL Injection'
make analyze             # Real OpenRouter run (requires .env LLM_API_KEY)
make validate-analysis   # Schema validation
```

---

## 4. Specialized Instructions

- For code diff review, severity scale, and review model escalation: see [`.agents/review.md`](.agents/review.md)
- For security boundaries, secret handling, and guardrails: see [`.agents/security.md`](.agents/security.md)
