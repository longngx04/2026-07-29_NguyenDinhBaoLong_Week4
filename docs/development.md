# Project Sentinel — Development & Operational Guide

This document covers local setup, test execution, command references, and artifact lifecycle.

---

## 1. Setup & Installation

### Prerequisites
- Python >= 3.10 (3.12 recommended)
- Docker & Docker Compose v2 (optional for scanner/WebGoat execution)

### Editable Installation

```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install editable package with dev dependencies
pip install -e '.[dev]'

# Verify package installation
python3 -c 'import project_sentinel; print(project_sentinel.__file__)'
```

---

## 2. Common Make Commands

| Command | Action | Key Options |
| --- | --- | --- |
| `make scan` | Runs OpenGrep using the isolated `compose.scan.yml` stack | Does not require Gateway or `SENTINEL_GATEWAY_API_KEY` |
| `make agent-test` | Runs all pytest unit & integration tests offline | `LLM_PROVIDER=fake` |
| `make normalize` | Normalizes OpenGrep raw scan into findings schema | Inputs: `artifacts/raw/opengrep.json` |
| `make search Q='...'` | Searches the knowledge base | e.g. `make search Q='SQL Injection'` |
| `make analyze-mock` | Runs full analysis pipeline on fixture using `FakeLLM` | No API key required |
| `make analyze` | Runs analysis pipeline using real OpenRouter provider | Requires `.env` with `LLM_API_KEY` |
| `make validate-analysis` | Validates generated JSONL against JSON Schema | Target: `artifacts/analysis/security-analysis.jsonl` |

---

## 3. Artifact Lifecycle & Rules

- **Active Runtime Output**: All active analysis runs write to `artifacts/` (`artifacts/raw/`, `artifacts/normalized/`, `artifacts/analysis/`).
- **Historical Reports**: Weekly sprint reports (`reports/week-01/`, `reports/week-02/`, `reports/week-03/`) are immutable historical records. Running commands must never overwrite historical report evidence.
- **Git Tracking**: `.gitignore` ignores dynamic runtime output while preserving committed baseline artifacts (`findings.json`, `security-analysis.jsonl`, `run-summary.json`).
