# Design Specification: Week 4 Verification Pipeline & Safe Execution Engine

**Date:** 2026-08-12  
**Status:** Approved  
**Branch:** `feat/week4`  
**Author:** Antigravity  

---

## 1. Goal & Product Context

Week 4 introduces the **Verification Candidate Planner & Safe Request Execution Engine** for Project Sentinel.

The pipeline processes analyzed findings records (`artifacts/analysis/security-analysis.jsonl`) produced by the Week 3 Security Analysis Agent and converts proposed verification steps into structured, non-destructive probe requests to determine reachability and reproducibility against the local WebGoat benchmark target (`http://127.0.0.1:8080/WebGoat/`).

---

## 2. Architecture & Data Flow

A two-stage deterministic architecture ensures strict separation of concerns, transparency, and safety:

```text
artifacts/analysis/security-analysis.jsonl
                │
                ▼
  [Stage 1] Verification Candidate Planner (src/project_sentinel/verification/planner.py)
                │  - Validates analyzed finding records
                │  - Extracts verification_steps & maps CWE/locations
                │  - Builds safe HTTP probe request definitions
                ▼
  artifacts/verification/verification-plan.json
                │  (Conforms to schemas/verification-plan.schema.json)
                ▼
  [Stage 2] Safe Target Prober (src/project_sentinel/verification/prober.py)
                │  - Production path: Safe HTTP Client (127.0.0.1:8080 loopback only)
                │  - Offline/CI path: FakeProber (Fixture-driven, 0 network calls)
                ▼
  Validation & Atomic JSONL Writer (src/project_sentinel/verification/validators.py)
                │  - Validates output records against JSON Schema & Provenance
                ▼
  artifacts/verification/verification-results.jsonl
```

---

## 3. Scope & Safety Boundaries

### In Scope
1. **Deterministic Planning:** Map `verification_steps`, CWEs (CWE-89, CWE-502, CWE-78), and source file locations into safe HTTP probe candidates.
2. **Schema Validation:** Define strict JSON Schemas:
   - `schemas/verification-plan.schema.json`
   - `schemas/verification-result.schema.json`
3. **Safe Target Isolation:** HTTP requests in production/live mode are strictly restricted to loopback host `127.0.0.1` and target WebGoat port `8080`.
4. **Offline Test Safety:** `FakeProber` enables 100% offline unit/integration testing without network or WebGoat dependency (`pytest -q tests`).
5. **CLI Integration:** Subcommands `verify` and `verify-mock` registered in `src/project_sentinel/cli.py` and `Makefile`.

### Out of Scope
1. **No Destructive Payloads:** Probes use non-destructive inspection requests (e.g. status checks, headers, parameter reflection) instead of system-modifying or data-wiping exploits.
2. **No Public Interface Scanning:** Strict rejection of any target hostname/IP other than `127.0.0.1` or `localhost`.
3. **No Interactive HITL UI:** User approval UI and interactive dashboard are reserved for Week 5.

---

## 4. Component Design

| Module | Location | Responsibilities |
| --- | --- | --- |
| **Models** | `src/project_sentinel/verification/models.py` | Dataclasses for `VerificationProbe`, `VerificationPlan`, `VerificationResult`. |
| **Planner** | `src/project_sentinel/verification/planner.py` | Transforms analyzed records into deterministic `VerificationPlan` objects. |
| **Prober Boundary** | `src/project_sentinel/verification/prober.py` | Base `BaseProber` interface and `HTTPProber` implementation for `127.0.0.1:8080`. |
| **Fake Prober** | `src/project_sentinel/verification/fake.py` | Mock `FakeProber` returning deterministic responses for offline unit tests. |
| **Validators** | `src/project_sentinel/verification/validators.py` | Post-execution JSON Schema and provenance validation. |
| **Pipeline** | `src/project_sentinel/verification/pipeline.py` | End-to-end execution manager and atomic file writer. |
| **CLI Commands** | `src/project_sentinel/cli.py` | CLI entry points (`verify` and `verify-mock`). |

---

## 5. Schemas & Data Contracts

### 5.1 Verification Plan Record (`schemas/verification-plan.schema.json`)
- `plan_id`: String (UUID or SHA256 deterministic ID)
- `analysis_record_id`: String (references input group ID)
- `group_id`: String
- `cwe`: String (e.g. `CWE-89`)
- `target_url`: String (must start with `http://127.0.0.1:8080/` or `http://localhost:8080/`)
- `probes`: Array of `VerificationProbe` items (method, path, headers, params, expected_indicator)

### 5.2 Verification Result Record (`schemas/verification-result.schema.json`)
- `result_id`: String
- `plan_id`: String
- `group_id`: String
- `status`: Enum (`VERIFIED_REACHABLE`, `UNREACHABLE`, `INCONCLUSIVE`, `FAILED`)
- `status_code`: Integer (HTTP status or null in offline mode)
- `evidence`: String (summary of response indicator matched)
- `execution_time_ms`: Float

---

## 6. Verification Commands

```bash
# Run offline unit/integration test suite
make agent-test

# Run mock verification pipeline using FakeProber
make verify-mock

# Run real verification pipeline against local WebGoat (requires docker compose up)
make verify
```

---

## 7. Acceptance Criteria

1. `schemas/verification-plan.schema.json` and `schemas/verification-result.schema.json` created and valid.
2. Planner generates valid probe definitions for all 21 analyzed finding groups.
3. `HTTPProber` strictly enforces `127.0.0.1:8080` target boundary and rejects external URLs.
4. `FakeProber` executes offline without network access, allowing all tests to pass in `make agent-test`.
5. CLI subcommands `verify` and `verify-mock` execute end-to-end without errors.
6. Report written atomically to `artifacts/verification/verification-results.jsonl`.
