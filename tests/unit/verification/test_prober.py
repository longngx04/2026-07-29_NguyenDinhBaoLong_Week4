"""
Unit tests for verification probers (HTTPProber and FakeProber).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

import jsonschema
import pytest

from project_sentinel.verification.fake import FakeProber
from project_sentinel.verification.models import (
    VerificationPlan,
    VerificationProbe,
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
def sample_plan():
    probe = VerificationProbe(
        probe_id="probe-1",
        method="GET",
        path="/start.mvc",
        headers={"User-Agent": "TestProbe/1.0"},
        params={"inspect": "reachability"},
        expected_status=200,
        expected_indicator="WebGoat",
    )
    return VerificationPlan(
        plan_id="plan-test-1",
        analysis_record_id="group-1",
        group_id="group-1",
        cwe="CWE-89",
        target_url="http://127.0.0.1:8080/WebGoat/start.mvc",
        probes=[probe],
    )


def test_fake_prober_execution(sample_plan, result_schema):
    prober = FakeProber()
    result = prober.execute_plan(sample_plan)

    assert isinstance(result, VerificationResult)
    assert result.plan_id == sample_plan.plan_id
    assert result.group_id == sample_plan.group_id
    assert result.status == VerificationStatus.VERIFIED_REACHABLE
    assert result.status_code == 200
    assert "FakeProber" in result.evidence or "offline" in result.evidence.lower()

    # Assert JSON schema validity
    result_dict = result.to_dict()
    jsonschema.validate(instance=result_dict, schema=result_schema)


def test_http_prober_boundary_rejection(result_schema):
    prober = HTTPProber()
    invalid_urls = [
        "http://example.com/WebGoat/start.mvc",
        "https://google.com",
        "http://10.0.0.1:8080/WebGoat",
        "http://127.0.0.1:9090/WebGoat",
        "http://localhost:3000/WebGoat",
        "ftp://127.0.0.1:8080/WebGoat",
    ]

    for invalid_url in invalid_urls:
        plan = VerificationPlan(
            plan_id="plan-bad-url",
            analysis_record_id="group-1",
            group_id="group-1",
            cwe="CWE-89",
            target_url=invalid_url,
            probes=[],
        )
        result = prober.execute_plan(plan)

        assert result.status == VerificationStatus.FAILED
        assert result.status_code is None
        assert "boundary" in result.evidence.lower() or "not permitted" in result.evidence.lower()

        # Assert JSON schema validity
        jsonschema.validate(instance=result.to_dict(), schema=result_schema)


def test_http_prober_allowed_boundary_mocked(sample_plan, result_schema):
    prober = HTTPProber(timeout=2.0)

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = b"<html><body>Welcome to WebGoat</body></html>"

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = prober.execute_plan(sample_plan)

        assert mock_urlopen.called
        assert result.status == VerificationStatus.VERIFIED_REACHABLE
        assert result.status_code == 200
        assert "WebGoat" in result.evidence
        jsonschema.validate(instance=result.to_dict(), schema=result_schema)


def test_http_prober_unreachable_connection_error(sample_plan, result_schema):
    prober = HTTPProber(timeout=1.0)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        result = prober.execute_plan(sample_plan)

        assert result.status == VerificationStatus.UNREACHABLE
        assert result.status_code is None
        assert "unreachable" in result.evidence.lower() or "connection refused" in result.evidence.lower()
        jsonschema.validate(instance=result.to_dict(), schema=result_schema)
