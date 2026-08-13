"""
Pipeline coordinator for verification candidate generation and GatewayClient execution.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, List, Union

from project_sentinel.analysis.validators import read_jsonl, write_jsonl_atomic
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.models import SecurityAnalysisRecord
from project_sentinel.verification.gateway_client import execute_candidate
from project_sentinel.verification.planner import build_verification_plans
from project_sentinel.verification.transport import FakeTransport, RealTransport
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
    target_base_url: str = "http://127.0.0.1:9080",
    allowlist_path: Union[str, Path] = "configs/gateway/allowlist.yaml",
) -> int:
    """Run the end-to-end verification pipeline using VerificationCandidates and GatewayClient.

    Args:
        input_path: Path to Week 3 analyzed records JSONL file.
        plan_output_path: Output path for verification plans/candidates JSON.
        results_output_path: Output path for verification results JSONL.
        provider: Transport provider ("fake" or "http"/"real").
        target_base_url: Base URL for target Gateway endpoint (default 127.0.0.1:9080).
        allowlist_path: Path to YAML allowlist configuration.

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

    # Load Allowlist
    allowlist_file = Path(allowlist_path)
    if allowlist_file.exists():
        allowlist = Allowlist.from_yaml(str(allowlist_file))
    else:
        # Fallback allowlist if config file missing
        from project_sentinel.gateway.allowlist import AllowlistRule
        allowlist = Allowlist([
            AllowlistRule(method="GET", path="/WebGoat/actuator/health", match="exact"),
            AllowlistRule(method="GET", path="/WebGoat/attack", match="prefix"),
            AllowlistRule(method="POST", path="/WebGoat/attack", match="prefix"),
        ])

    # Generate verification candidates
    candidates = build_verification_plans(records, target_base_url=target_base_url)
    candidate_dicts: List[Any] = []
    for cand in candidates:
        cand_dict = cand.to_dict()
        validate_verification_plan_schema(cand_dict)
        candidate_dicts.append(cand_dict)

    _write_json_atomic(candidate_dicts, plan_output_path)

    # Resolve API Key
    api_key = os.environ.get("SENTINEL_API_KEY", "test-sentinel-key")

    # Instantiate transport provider
    if provider == "fake":
        transport = FakeTransport()
    else:
        transport = RealTransport()

    # Execute GatewayClient for each candidate and collect results
    results_dicts: List[Any] = []
    for cand in candidates:
        result = execute_candidate(
            candidate=cand,
            transport=transport,
            allowlist=allowlist,
            api_key=api_key,
            base_url=target_base_url,
        )
        res_dict = result.to_dict()
        validate_verification_result_schema(res_dict)
        results_dicts.append(res_dict)

    write_jsonl_atomic(results_dicts, results_output_path)

    return len(candidates)
