"""
Command-line interface for Project Sentinel.
Provides commands:
- analyze: run end-to-end security analysis pipeline
- validate: validate output JSONL records against schema
- probe: run canonical Week 4 IAM verification probe flow
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from project_sentinel.config import AppConfig
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.gateway.request_log import log_request
from project_sentinel.llm.factory import build_llm
from project_sentinel.analysis.pipeline import run_pipeline
from project_sentinel.analysis.validators import read_jsonl, validate_record_schema
from project_sentinel.verification.gateway_client import execute_candidate
from project_sentinel.verification.models import (
    VerificationCandidate,
    VerificationDecision,
    VerificationResult,
    VerificationStatus,
)
from project_sentinel.verification.proposer import generate_probe_proposal
from project_sentinel.verification.resolver import (
    load_endpoint_catalog,
    load_probe_objectives,
    resolve_proposal,
)
from project_sentinel.verification.templates import ProbeTemplateRegistry
from project_sentinel.verification.transport import RealTransport
from project_sentinel.verification.validators import validate_verification_result_schema


def _write_json_atomic(data: Any, target_file: Path) -> None:
    """Atomic write for JSON files using NamedTemporaryFile and os.replace."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_file.parent,
        delete=False,
    ) as tf:
        json.dump(data, tf, indent=2, ensure_ascii=False)
        tf.write("\n")
        temp_path = Path(tf.name)
    os.replace(temp_path, target_file)


def _append_jsonl_atomic(data: dict[str, Any], target_file: Path) -> None:
    """Append one record atomically to a JSONL file."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(data, ensure_ascii=False) + "\n"
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def _confine_path(path: Path, allowed_parent_dir: Path, arg_name: str) -> Path:
    """Ensure path is strictly confined inside allowed_parent_dir without escapes."""
    allowed_parent = allowed_parent_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_parent)
    except ValueError:
        raise ValueError(
            f"Path confinement violation: {arg_name} ({path}) must be located within {allowed_parent}"
        )
    return resolved


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # analyze sub-command
    analyze_parser = subparsers.add_parser("analyze", help="Run end-to-end security analysis pipeline")
    analyze_parser.add_argument("--input", type=Path, default=Path("artifacts/normalized/findings.json"), help="Input normalized findings JSON")
    analyze_parser.add_argument("--output", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Output security analysis JSONL")
    analyze_parser.add_argument("--summary", type=Path, default=Path("artifacts/analysis/run-summary.json"), help="Output run summary JSON")
    analyze_parser.add_argument("--target-root", type=Path, default=None, help="Target project root directory")
    analyze_parser.add_argument("--knowledge-dir", type=Path, default=Path("data/knowledge-base"), help="Knowledge base directory")

    # validate sub-command
    validate_parser = subparsers.add_parser("validate", help="Validate output JSONL file against JSON schema")
    validate_parser.add_argument("--input", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Input JSONL file")
    validate_parser.add_argument("--schema", type=Path, default=Path("schemas/security-analysis-record.schema.json"), help="JSON schema path")

    # probe sub-command (Week 4 IAM verification probe flow)
    probe_parser = subparsers.add_parser("probe", help="Run canonical IAM verification probe flow")
    probe_parser.add_argument("--objective-id", type=str, default="obj-health-check", help="Target operator objective ID")
    probe_parser.add_argument("--objectives", type=Path, default=Path("configs/verification/probe-objectives.json"), help="Path to probe objectives JSON")
    probe_parser.add_argument("--catalog", type=Path, default=Path("configs/verification/endpoint-catalog.json"), help="Path to endpoint catalog JSON")
    probe_parser.add_argument("--allowlist", type=Path, default=Path("configs/gateway/endpoint-allowlist.json"), help="Path to Gateway allowlist JSON")
    probe_parser.add_argument("--templates", type=Path, default=Path("configs/verification/probe-templates.json"), help="Path to probe templates JSON")
    probe_parser.add_argument("--output", type=Path, default=Path("artifacts/verification/probe-results.jsonl"), help="Output verification results JSONL")
    probe_parser.add_argument("--proposal-output", type=Path, default=Path("artifacts/verification/probe-proposals.jsonl"), help="Output probe proposals JSONL")
    probe_parser.add_argument("--summary", type=Path, default=Path("artifacts/verification/run-summary.json"), help="Output run summary JSON")
    probe_parser.add_argument("--log", type=Path, default=Path("artifacts/gateway/requests.log.jsonl"), help="Audit log path")

    args = parser.parse_args(argv)

    # If no subcommand given, default to analyze
    if args.command is None:
        args = parser.parse_args(["analyze"] + (argv if argv else []))

    if args.command == "validate":
        try:
            records = read_jsonl(args.input)
            if not records:
                print(f"Error: JSONL file '{args.input}' is empty", file=sys.stderr)
                return 4
            for idx, rec in enumerate(records, 1):
                is_valid, err = validate_record_schema(rec, args.schema)
                if not is_valid:
                    print(f"Error: Record {idx} in '{args.input}' failed schema validation: {err}", file=sys.stderr)
                    return 4
            print(f"Validated {len(records)} analysis records successfully.")
            return 0
        except FileNotFoundError as e:
            print(f"Error: File not found: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Error: Validation failed: {e}", file=sys.stderr)
            return 4

    if args.command == "probe":
        start_time = time.time()
        repo_root = Path(__file__).resolve().parents[2]
        verification_dir = (repo_root / "artifacts" / "verification").resolve()
        gateway_dir = (repo_root / "artifacts" / "gateway").resolve()
        verification_dir.mkdir(parents=True, exist_ok=True)
        gateway_dir.mkdir(parents=True, exist_ok=True)

        # 0. Enforce path confinement
        try:
            prop_out = _confine_path(args.proposal_output, verification_dir, "--proposal-output")
            res_out = _confine_path(args.output, verification_dir, "--output")
            sum_out = _confine_path(args.summary, verification_dir, "--summary")
            log_out = _confine_path(args.log, gateway_dir, "--log")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

        # 1. Load objective and configurations
        try:
            objectives = load_probe_objectives(args.objectives)
            matched_obj = next((o for o in objectives if o.get("objective_id") == args.objective_id), None)
            if not matched_obj:
                print(f"Error: Objective ID '{args.objective_id}' not found in {args.objectives}", file=sys.stderr)
                return 2
            catalog = load_endpoint_catalog(args.catalog)
            allowlist = Allowlist.from_json(args.allowlist)
            templates = ProbeTemplateRegistry.from_json(args.templates)
        except FileNotFoundError as e:
            print(f"Error: Required configuration file not found: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Error: Failed to load probe configuration: {e}", file=sys.stderr)
            return 2

        # 2. Check Gateway credentials
        gateway_api_key = os.getenv("SENTINEL_GATEWAY_API_KEY")
        if not gateway_api_key:
            env_file = Path(".env")
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("SENTINEL_GATEWAY_API_KEY="):
                        gateway_api_key = line.split("=", 1)[1].strip()
                        break
        if not gateway_api_key:
            print("Error: SENTINEL_GATEWAY_API_KEY is not set in environment or .env", file=sys.stderr)
            return 3

        # 3. Build LLM provider
        try:
            app_config = AppConfig.from_env()
            llm = build_llm(app_config)
        except Exception as e:
            print(f"Error: LLM provider configuration failed: {e}", file=sys.stderr)
            return 3

        # 4. Generate proposal via real LLM
        try:
            proposal_outcome = generate_probe_proposal(llm, catalog, matched_obj)
        except Exception as e:
            print(f"Error: LLM provider invocation failed: {e}", file=sys.stderr)
            return 3

        if proposal_outcome.status.value == "PROVIDER_FAILURE":
            print(f"Error: LLM provider failure: {proposal_outcome.error_reason}", file=sys.stderr)
            return 3

        proposal_dict = (
            proposal_outcome.proposal
            if proposal_outcome.is_valid and proposal_outcome.proposal
            else {
                "objective_id": args.objective_id,
                "status": proposal_outcome.status.value,
                "error_reason": proposal_outcome.error_reason,
            }
        )

        try:
            _append_jsonl_atomic(proposal_dict, prop_out)
        except (PermissionError, OSError) as e:
            print(f"Error: Output I/O failure: {e}", file=sys.stderr)
            return 5

        if not proposal_outcome.is_valid:
            print(f"Error: Proposal validation failed: {proposal_outcome.error_reason}", file=sys.stderr)
            return 4

        # 5. Resolve proposal
        cand = resolve_proposal(proposal_dict, catalog, allowlist, templates)

        # 6. Execute candidate
        if cand.decision == VerificationDecision.PLANNED and isinstance(cand, VerificationCandidate):
            transport = RealTransport()
            result = execute_candidate(
                cand,
                transport,
                allowlist,
                templates,
                gateway_api_key,
                log_path=str(log_out),
            )
        elif cand.decision == VerificationDecision.NOT_APPLICABLE:
            result = VerificationResult(
                result_id=f"res-{uuid4().hex[:12]}",
                plan_id=cand.candidate_id,
                status=VerificationStatus.INCONCLUSIVE,
                evidence=f"Objective not applicable: {cand.reason}",
            )
            log_request(
                str(log_out),
                request_id=f"req-{uuid4().hex[:12]}",
                candidate_id=cand.candidate_id,
                objective_id=cand.objective_id,
                proposal_id=cand.proposal_id,
                endpoint_id=None,
                template_id=None,
                method=None,
                path=None,
                payload_type=None,
                status=result.status.value,
                status_code=None,
                elapsed_ms=0.0,
                response_bytes_observed=0,
                truncated=False,
                response_preview=None,
                error_class=None,
                error_reason=None,
                policy_decision="NOT_APPLICABLE",
            )
        else:
            reason = getattr(cand, "reason", "Candidate not plannable")
            result = VerificationResult(
                result_id=f"res-{uuid4().hex[:12]}",
                plan_id=getattr(cand, "candidate_id", "cand-unplannable"),
                status=VerificationStatus.DENIED,
                evidence=f"Candidate not plannable: {reason}",
                error_class="ResolverRejection",
                error_reason=reason,
            )
            log_request(
                str(log_out),
                request_id=f"req-{uuid4().hex[:12]}",
                candidate_id=getattr(cand, "candidate_id", "cand-unplannable"),
                objective_id=getattr(cand, "objective_id", args.objective_id),
                proposal_id=getattr(cand, "proposal_id", proposal_dict.get("proposal_id")),
                endpoint_id=getattr(cand, "endpoint_id", None),
                template_id=getattr(cand, "template_id", None),
                method=getattr(cand, "method", None),
                path=getattr(cand, "path", None),
                payload_type=getattr(cand, "payload_type", None),
                status=result.status.value,
                status_code=None,
                elapsed_ms=0.0,
                response_bytes_observed=0,
                truncated=False,
                response_preview=None,
                error_class=result.error_class,
                error_reason=reason,
                policy_decision="DENIED",
            )

        res_dict = result.to_dict()
        try:
            validate_verification_result_schema(res_dict)
            _append_jsonl_atomic(res_dict, res_out)
        except (PermissionError, OSError) as e:
            print(f"Error: Output I/O failure: {e}", file=sys.stderr)
            return 5
        except Exception as e:
            print(f"Error: Result schema validation failed: {e}", file=sys.stderr)
            return 4

        elapsed = time.time() - start_time
        summary = {
            "objective_id": args.objective_id,
            "proposal_id": proposal_dict.get("proposal_id"),
            "candidate_id": getattr(cand, "candidate_id", "cand-unplannable"),
            "decision": cand.decision.value if hasattr(cand.decision, "value") else str(cand.decision),
            "result_id": result.result_id,
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "status_code": result.status_code,
            "elapsed_seconds": round(elapsed, 2),
        }
        try:
            _write_json_atomic(summary, sum_out)
        except (PermissionError, OSError) as e:
            print(f"Error: Output I/O failure: {e}", file=sys.stderr)
            return 5

        # Check for Gateway reachability or auth failures
        if result.status is VerificationStatus.UNREACHABLE or result.status is VerificationStatus.FAILED:
            print(f"Error: Verification transport failure: {result.evidence}", file=sys.stderr)
            return 3
        if result.status is VerificationStatus.DENIED and result.status_code in {401, 403}:
            print(f"Error: Gateway denied credentials: HTTP {result.status_code}", file=sys.stderr)
            return 3

        preview_display = json.dumps(result.response_preview, ensure_ascii=True)
        print(
            f"Verification complete: status={summary['status']}, "
            f"status_code={summary['status_code']}, "
            f"response_preview={preview_display}, output written to {res_out}"
        )
        return 0

    # analyze command
    try:
        config = AppConfig.from_env(
            input_findings_path=args.input,
            output_jsonl_path=args.output,
            summary_path=args.summary,
            knowledge_dir=args.knowledge_dir,
            target_root=args.target_root
        )
        run_pipeline(config)
        return 0
    except (FileNotFoundError, ValueError) as e:
        err_str = str(e)
        if "LLM_API_KEY" in err_str or "LLM_PROVIDER" in err_str or "Provider" in err_str or "OpenRouter" in err_str:
            print(f"Error: {e}", file=sys.stderr)
            return 3
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected pipeline error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
