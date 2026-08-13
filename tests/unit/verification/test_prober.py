import json
from pathlib import Path
import jsonschema
import pytest

from project_sentinel.verification.fake import FakeProber
from project_sentinel.verification.models import (
    VerificationCandidate,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.prober import HTTPProber


@pytest.fixture
def result_schema():
    schema_path = Path("schemas/verification-result.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_candidate():
    return VerificationCandidate(
        candidate_id="cand-test-1",
        analysis_record_id="group-1",
        group_id="group-1",
        cwe="CWE-89",
        endpoint_id="ep_health",
        template_id="tmpl_health_get",
        method="GET",
        path="/WebGoat/actuator/health",
    )


def test_fake_prober_execution(sample_candidate, result_schema):
    prober = FakeProber()
    result = prober.execute_plan(sample_candidate)

    assert isinstance(result, VerificationResult)
    assert result.plan_id == sample_candidate.candidate_id
    assert result.group_id == sample_candidate.group_id
    assert result.status == VerificationStatus.VERIFIED_REACHABLE
    assert result.status_code == 200

    # Assert JSON schema validity
    result_dict = result.to_dict()
    jsonschema.validate(instance=result_dict, schema=result_schema)
