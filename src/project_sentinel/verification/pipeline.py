"""
Pipeline coordinator for verification plan generation and prober execution.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, List, Union

from project_sentinel.analysis.validators import read_jsonl, write_jsonl_atomic
from project_sentinel.models import SecurityAnalysisRecord
from project_sentinel.verification.fake import FakeProber
from project_sentinel.verification.planner import DEFAULT_TARGET_BASE, build_verification_plans
from project_sentinel.verification.prober import BaseProber, HTTPProber
from project_sentinel.verification.validators import (
    validate_verification_plan_schema,
    validate_verification_result_schema,
)


def _write_json_atomic(data: Any, output_path: Union[str, Path]) -> None:
    """Write data as JSON to output_path atomically."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tf:
        temp_name = tf.name
        json.dump(data, tf, indent=2, ensure_ascii=False)
    Path(temp_name).replace(path)


def run_verification_pipeline(
    input_path: Union[str, Path],
    plan_output_path: Union[str, Path],
    results_output_path: Union[str, Path],
    provider: str = "fake",
    target_base_url: str = DEFAULT_TARGET_BASE,
) -> int:
    """
    Run the end-to-end verification pipeline.

    Args:
        input_path: Path to Week 3 analyzed records JSONL file.
        plan_output_path: Output path for verification plans JSON.
        results_output_path: Output path for verification results JSONL.
        provider: Prober provider ("fake" or "http").
        target_base_url: Base URL for target verification probes.

    Returns:
        Number of processed records.
    """
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    raw_records = read_jsonl(input_p)
    if not raw_records:
        _write_json_atomic([], plan_output_path)
        write_jsonl_atomic([], results_output_path)
        return 0

    records = [SecurityAnalysisRecord.from_dict(r) for r in raw_records]

    # Generate verification plans
    plans = build_verification_plans(records, target_base_url=target_base_url)
    plan_dicts: List[Any] = []
    for plan in plans:
        plan_dict = plan.to_dict()
        validate_verification_plan_schema(plan_dict)
        plan_dicts.append(plan_dict)

    _write_json_atomic(plan_dicts, plan_output_path)

    # Instantiate prober based on provider
    prober: BaseProber
    if provider == "fake":
        prober = FakeProber()
    else:
        prober = HTTPProber()

    # Execute prober and collect results
    results_dicts: List[Any] = []
    for plan in plans:
        result = prober.execute_plan(plan)
        res_dict = result.to_dict()
        validate_verification_result_schema(res_dict)
        results_dicts.append(res_dict)

    write_jsonl_atomic(results_dicts, results_output_path)

    return len(plans)
