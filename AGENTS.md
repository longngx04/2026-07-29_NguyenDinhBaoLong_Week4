# Project Sentinel — Agent Guidelines (`AGENTS.md`)

> [!IMPORTANT]
> **MANDATORY RULE FOR ALL CODING AGENTS (Claude, Antigravity, OpenCode):**
> Before executing any task, generating code, or modifying files, every agent MUST inspect and read all instruction files in the `.agents/` directory (`.agents/context.md`, `.agents/rules/*.md`, `.agents/security.md`, `.agents/workflow.md`, `.agents/review.md`).
>
> **AFTER finishing any task**, the agent MUST write one report file to `worklog/<YYYY-MM-DD>-<task-slug>.md` using [`worklog/_TEMPLATE.md`](worklog/_TEMPLATE.md) — what was done, how, real output, the task's function, and why that implementation was chosen. A task without its worklog file is not complete.
> The copy-paste task prompt enforcing this (read-proof gate → small steps → worklog) is [`.agents/rules/task_prompt_template.md`](.agents/rules/task_prompt_template.md).
>
> **Two tasks often run in parallel on two branches.** Before touching any file, run
> `git branch --show-current` and `git status --short`. If the branch is not the one named in
> your task, or the tree contains files belonging to another task, STOP and ask — never switch
> branches, never `git add -A`, never move or delete another task's files. See §4 below.

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
│   ├── probe/                    # Safe probe tool: allowlist, payloads, transport
│   └── llm/                      # LLM provider abstraction (OpenRouter)
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Pipeline & CLI end-to-end integration tests
│   └── fixtures/                 # Deterministic test inputs & expected outputs
├── exercises/week4-gateway/      # Bài tập gateway độc lập
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

## 4. Parallel Work on Multiple Branches

The operator often runs **two tasks at once on two different branches**. A single
working tree can only be on one branch, so mixing tasks in one checkout silently
strands one task's files on the other task's branch. Follow these rules.

1. **Confirm your branch before touching anything.**

   ```bash
   git branch --show-current   # must match the branch named in YOUR task
   git status --short          # anything listed that is not yours belongs to another task
   ```

   If the current branch is not yours, stop and ask — do not switch or commit.

2. **One branch, one directory.** Use a git worktree instead of `git switch`:

   ```bash
   git worktree add .worktrees/<short-task-name> -b feat/<branch-name>
   git worktree add .worktrees/<short-task-name> <existing-branch>   # existing branch
   git worktree list
   git worktree remove .worktrees/<short-task-name>                  # when merged/done
   ```

   `.worktrees/` is already in `.gitignore`. Never create worktrees elsewhere in the repo.

3. **Running tests inside a worktree requires `PYTHONPATH`.** The venv installs
   `project_sentinel` as an editable install whose `.pth` file points at the **main**
   checkout's `src/`, so a worktree would import the wrong copy:

   ```bash
   PYTHONPATH="$PWD/src" /path/to/main-checkout/.venv/bin/python -m pytest tests/... -q
   ```

4. **Stage files explicitly. `git add -A` and `git add .` are forbidden** whenever the
   tree holds work from more than one task. List every path, then verify before committing:

   ```bash
   git add <path> <path> ...
   git diff --cached --name-status   # read this; every entry must belong to your task
   ```

5. **Do not delete or move another task's files** to make your tests pass or your tree
   clean, and do not commit them "to get them out of the way".

6. **Empty `__init__.py` files still count.** They are easy to lose when moving files
   between trees, and Python 3 namespace packages hide the loss from tests. Confirm every
   package directory your task creates is present in `git diff --cached --name-status`.

---

## 5. Specialized Instructions

- For code diff review, severity scale, and review model escalation: see [`.agents/review.md`](.agents/review.md)
- For security boundaries, secret handling, and guardrails: see [`.agents/security.md`](.agents/security.md)
