"""
Unit tests for verification dataclasses and JSON schema validation.
"""

import json
from pathlib import Path
import jsonschema
import pytest

from project_sentinel.verification.models import (
    VerificationProbe,
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
)


def test_verification_models_roundtrip():
    probe = VerificationProbe(
        probe_id="probe-1",
        method="GET",
        path="/WebGoat/start.mvc",
        headers={"User-Agent": "ProjectSentinel-Probe/1.0"},
        params={},
        expected_status=200,
    )
    plan = VerificationPlan(
        plan_id="plan-1",
        analysis_record_id="group-1",
        group_id="group-1",
        cwe="CWE-89",
        target_url="http://127.0.0.1:8080/WebGoat/start.mvc",
        probes=[probe],
    )
    assert plan.plan_id == "plan-1"
    assert len(plan.probes) == 1
    assert plan.probes[0].probe_id == "probe-1"

    # Test dictionary serialization & deserialization
    plan_dict = plan.to_dict()
    reconstructed_plan = VerificationPlan.from_dict(plan_dict)
    assert reconstructed_plan == plan

    result = VerificationResult(
        result_id="res-1",
        plan_id="plan-1",
        group_id="group-1",
        status=VerificationStatus.VERIFIED_REACHABLE,
        status_code=200,
        evidence="HTTP 200 OK received from target endpoint",
        execution_time_ms=12.5,
    )
    assert result.result_id == "res-1"
    assert result.status == VerificationStatus.VERIFIED_REACHABLE

    result_dict = result.to_dict()
    reconstructed_result = VerificationResult.from_dict(result_dict)
    assert reconstructed_result.result_id == result.result_id
    assert reconstructed_result.status == "VERIFIED_REACHABLE"


def test_verification_plan_schema_validation():
    schema_path = Path("schemas/verification-plan.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    probe = VerificationProbe(
        probe_id="probe-1",
        method="GET",
        path="/WebGoat/start.mvc",
        headers={"User-Agent": "ProjectSentinel-Probe/1.0"},
        params={},
        expected_status=200,
    )
    plan = VerificationPlan(
        plan_id="plan-1",
        analysis_record_id="group-1",
        group_id="group-1",
        cwe="CWE-89",
        target_url="http://127.0.0.1:8080/WebGoat/start.mvc",
        probes=[probe],
    )

    plan_dict = plan.to_dict()
    # Should validate cleanly against schema
    jsonschema.validate(instance=plan_dict, schema=schema)


def test_verification_result_schema_validation():
    schema_path = Path("schemas/verification-result.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    result = VerificationResult(
        result_id="res-1",
        plan_id="plan-1",
        group_id="group-1",
        status=VerificationStatus.VERIFIED_REACHABLE,
        status_code=200,
        evidence="Matched indicator",
        execution_time_ms=5.0,
    )

    result_dict = result.to_dict()
    # Should validate cleanly against schema
    jsonschema.validate(instance=result_dict, schema=schema)
