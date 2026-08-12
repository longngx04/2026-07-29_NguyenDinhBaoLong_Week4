"""
End-to-end integration tests for verification candidate planner & prober pipeline.
"""

import json
from pathlib import Path
import pytest

from project_sentinel.analysis.validators import read_jsonl
from project_sentinel.cli import main
from project_sentinel.verification.pipeline import run_verification_pipeline
from project_sentinel.verification.validators import (
    validate_verification_plan_schema,
    validate_verification_result_schema,
)


def test_verification_pipeline_fake(tmp_path):
    input_file = Path("artifacts/analysis/security-analysis.jsonl")
    plan_file = tmp_path / "verification-plan.json"
    results_file = tmp_path / "verification-results.jsonl"

    count = run_verification_pipeline(
        input_path=str(input_file),
        plan_output_path=str(plan_file),
        results_output_path=str(results_file),
        provider="fake",
    )

    assert count > 0
    assert plan_file.exists()
    assert results_file.exists()

    # Validate plan JSON format and schema
    plans_data = json.loads(plan_file.read_text(encoding="utf-8"))
    assert isinstance(plans_data, list)
    assert len(plans_data) == count
    for plan in plans_data:
        validate_verification_plan_schema(plan)

    # Validate results JSONL format and schema
    results = read_jsonl(results_file)
    assert len(results) == count
    for res in results:
        validate_verification_result_schema(res)


def test_verification_pipeline_empty_input(tmp_path):
    empty_input = tmp_path / "empty.jsonl"
    empty_input.write_text("", encoding="utf-8")

    plan_file = tmp_path / "plan.json"
    results_file = tmp_path / "results.jsonl"

    count = run_verification_pipeline(
        input_path=str(empty_input),
        plan_output_path=str(plan_file),
        results_output_path=str(results_file),
        provider="fake",
    )

    assert count == 0
    assert plan_file.exists()
    assert results_file.exists()


def test_cli_verify_mock(tmp_path):
    input_file = Path("artifacts/analysis/security-analysis.jsonl")
    plan_file = tmp_path / "plan.json"
    results_file = tmp_path / "results.jsonl"

    argv = [
        "verify-mock",
        "--input", str(input_file),
        "--plan-output", str(plan_file),
        "--results-output", str(results_file),
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert plan_file.exists()
    assert results_file.exists()


def test_cli_verify_with_fake_provider(tmp_path):
    input_file = Path("artifacts/analysis/security-analysis.jsonl")
    plan_file = tmp_path / "plan.json"
    results_file = tmp_path / "results.jsonl"

    argv = [
        "verify",
        "--provider", "fake",
        "--input", str(input_file),
        "--plan-output", str(plan_file),
        "--results-output", str(results_file),
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert plan_file.exists()
    assert results_file.exists()


def test_cli_verify_nonexistent_input():
    argv = ["verify-mock", "--input", "nonexistent-analysis.jsonl"]
    exit_code = main(argv)
    assert exit_code == 2
