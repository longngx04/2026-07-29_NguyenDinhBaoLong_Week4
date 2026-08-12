# Week 4 Verification Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triển khai Verification Candidate Planner & Safe Request Execution Engine để tự động chuyển `verification_steps` từ `artifacts/analysis/security-analysis.jsonl` thành các probe HTTP an toàn và ghi kết quả xác minh nguyên tử ra `artifacts/verification/verification-results.jsonl`.

**Architecture:** Kiến trúc 2 giai đoạn xác định (Stage 1: Planner -> Stage 2: Safe Prober). Stage 1 tạo `artifacts/verification/verification-plan.json` theo schema. Stage 2 chạy `HTTPProber` (chỉ gửi request tới `127.0.0.1:8080`) hoặc `FakeProber` (offline unit test boundary) và ghi `verification-results.jsonl`.

**Tech Stack:** Python 3.12, `jsonschema`, `urllib.request` / `http.client` (stdlib), `pytest`.

## Global Constraints

- **Offline Test Safety:** Tất cả unit test (`make agent-test`) phải chạy 100% offline sử dụng `FakeProber`.
- **Target Boundary Isolation:** Probe thật chỉ cho phép gửi tới host `127.0.0.1` và port `8080` (`http://127.0.0.1:8080/WebGoat/`).
- **No Destructive Exploits:** Không sinh hoặc gửi payload gây thay đổi trạng thái hệ thống hoặc xóa dữ liệu.
- **Behavior Preservation:** Bảo toàn schema validation và atomic file writing.

---

### Task 1: Data Models & Schemas

**Files:**
- Create: `schemas/verification-plan.schema.json`
- Create: `schemas/verification-result.schema.json`
- Create: `src/project_sentinel/verification/__init__.py`
- Create: `src/project_sentinel/verification/models.py`
- Test: `tests/unit/verification/test_models.py`

**Interfaces:**
- Consumes: `src/project_sentinel/models.py` (`SecurityAnalysisRecord`)
- Produces: `VerificationProbe`, `VerificationPlan`, `VerificationResult` dataclasses

- [ ] **Step 1: Write failing test for dataclasses and JSON serialization**

```python
from project_sentinel.verification.models import VerificationProbe, VerificationPlan, VerificationResult

def test_verification_models_roundtrip():
    probe = VerificationProbe(
        probe_id="probe-1",
        method="GET",
        path="/WebGoat/start.mvc",
        headers={"User-Agent": "ProjectSentinel-Probe/1.0"},
        params={},
        expected_status=200
    )
    plan = VerificationPlan(
        plan_id="plan-1",
        analysis_record_id="group-1",
        group_id="group-1",
        cwe="CWE-89",
        target_url="http://127.0.0.1:8080/WebGoat/start.mvc",
        probes=[probe]
    )
    assert plan.plan_id == "plan-1"
    assert len(plan.probes) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_models.py -v`  
Expected: FAIL (ModuleNotFoundError / ImportError)

- [ ] **Step 3: Implement schemas and dataclasses**

Create `schemas/verification-plan.schema.json`, `schemas/verification-result.schema.json`, and `src/project_sentinel/verification/models.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add schemas/src/ tests/unit/verification/
git commit -m "feat(verification): add verification dataclasses and JSON schemas"
```

---

### Task 2: Deterministic Verification Planner

**Files:**
- Create: `src/project_sentinel/verification/planner.py`
- Test: `tests/unit/verification/test_planner.py`

**Interfaces:**
- Consumes: `SecurityAnalysisRecord` from Week 3 analysis output
- Produces: `build_verification_plan(record: SecurityAnalysisRecord) -> VerificationPlan`

- [ ] **Step 1: Write failing test for planner logic**

```python
from project_sentinel.models import SecurityAnalysisRecord
from project_sentinel.verification.planner import build_verification_plan

def test_build_verification_plan():
    record = SecurityAnalysisRecord(
        group_id="group-1",
        source_finding_ids=["finding-1"],
        cwe="CWE-89",
        owasp="A03:2021-Injection",
        scanner_severity="high",
        analysis_severity="high",
        confidence="MEDIUM",
        confidence_rationale="Sink present",
        title="SQL Injection in WebGoat",
        description="Potential SQL Injection",
        locations=[{"path": "webgoat-container/src/main/java/org/owasp/webgoat/session/LessonTracker.java", "start_line": 40}],
        verification_steps=["Send GET probe to WebGoat status endpoint"],
        remediation_steps=["Use PreparedStatement"],
        knowledge_refs=[],
        limitations=[],
        system_prompt_sha256="abc123sha256"
    )
    plan = build_verification_plan(record)
    assert plan.analysis_record_id == "group-1"
    assert plan.cwe == "CWE-89"
    assert len(plan.probes) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_planner.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement planner**

Implement `src/project_sentinel/verification/planner.py` mapping analysis record fields and `verification_steps` into safe probe definitions.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_planner.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/project_sentinel/verification/planner.py tests/unit/verification/test_planner.py
git commit -m "feat(verification): implement deterministic verification candidate planner"
```

---

### Task 3: Prober Interface & Offline FakeProber Boundary

**Files:**
- Create: `src/project_sentinel/verification/prober.py`
- Create: `src/project_sentinel/verification/fake.py`
- Test: `tests/unit/verification/test_prober.py`

**Interfaces:**
- Consumes: `VerificationPlan`
- Produces: `execute_plan(plan: VerificationPlan) -> VerificationResult`

- [ ] **Step 1: Write failing test for FakeProber and boundary check**

```python
from project_sentinel.verification.fake import FakeProber
from project_sentinel.verification.planner import build_verification_plan

def test_fake_prober_execution():
    prober = FakeProber()
    # Execute fake probe
    # Assert result status is VERIFIED_REACHABLE or UNREACHABLE without network access
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_prober.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement BaseProber, HTTPProber (with 127.0.0.1 strict check), and FakeProber**

Implement `src/project_sentinel/verification/prober.py` and `fake.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest tests/unit/verification/test_prober.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/project_sentinel/verification/prober.py src/project_sentinel/verification/fake.py tests/unit/verification/test_prober.py
git commit -m "feat(verification): implement HTTPProber boundary and offline FakeProber"
```

---

### Task 4: Pipeline Coordinator, Validation & CLI Entry Points

**Files:**
- Create: `src/project_sentinel/verification/validators.py`
- Create: `src/project_sentinel/verification/pipeline.py`
- Modify: `src/project_sentinel/cli.py`
- Modify: `Makefile`
- Test: `tests/integration/test_verification_pipeline.py`

**Interfaces:**
- Consumes: CLI args `--input`, `--output`, `--plan-output`, `--provider`
- Produces: End-to-end execution writing `artifacts/verification/verification-plan.json` and `artifacts/verification/verification-results.jsonl`

- [ ] **Step 1: Write failing integration test for end-to-end verification CLI**

```python
from project_sentinel.verification.pipeline import run_verification_pipeline

def test_verification_pipeline_fake(tmp_path):
    plan_file = tmp_path / "verification-plan.json"
    results_file = tmp_path / "verification-results.jsonl"
    count = run_verification_pipeline(
        input_path="artifacts/analysis/security-analysis.jsonl",
        plan_output_path=str(plan_file),
        results_output_path=str(results_file),
        provider="fake"
    )
    assert count > 0
    assert plan_file.exists()
    assert results_file.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest tests/integration/test_verification_pipeline.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement verification validators, pipeline coordinator, CLI subcommands (`verify`, `verify-mock`), and Makefile targets**

Implement pipeline, CLI entry points, and Makefile targets (`verify`, `verify-mock`).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest tests/integration/test_verification_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/project_sentinel/ Makefile tests/integration/
git commit -m "feat(verification): complete verification pipeline, CLI entry points, and Makefile targets"
```
