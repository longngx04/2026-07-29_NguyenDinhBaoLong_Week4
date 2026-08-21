"""
Main analysis pipeline for Security Analysis Agent.
Coordinates loading, deduplication, evidence extraction, knowledge retrieval, LLM analysis,
post-LLM validation, atomic JSONL writing, and run summary output.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from project_sentinel.analysis.analyzer import analyze_finding_group
from project_sentinel.analysis.calibration import calibrate_record
from project_sentinel.analysis.output_safety import scan_unsafe_output
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.proposal import validate_objective
from project_sentinel.config import AppConfig
from project_sentinel.analysis.grouping import group_findings
from project_sentinel.ingestion.input_loader import load_findings
from project_sentinel.llm.factory import build_llm
from project_sentinel.analysis.validators import validate_provenance, validate_record_schema, write_jsonl_atomic


def _write_json_atomic(data: Dict[str, Any], target_path: Path) -> None:
    """Write dictionary to JSON file atomically via rename."""
    import tempfile
    import os
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # delete=False + try/finally la co chu y: file tam phai song sot sau khi dong
    # de os.replace() doi ten no thanh file dich. Context manager se xoa mat.
    temp_file = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w", delete=False, dir=target_path.parent, encoding="utf-8", suffix=".tmp"
    )
    temp_path = Path(temp_file.name)
    try:
        json.dump(data, temp_file, indent=2, ensure_ascii=False)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        temp_path.replace(target_path)
    except Exception:
        temp_file.close()
        if temp_path.exists():
            temp_path.unlink()
        raise


def _load_allowlist(config: AppConfig) -> Optional[Allowlist]:
    """Nạp allowlist một lần. Không đọc được thì trả None và bỏ qua bước kiểm.

    Không để lỗi đọc file làm sập cả lần chạy phân tích: bước propose vẫn còn một
    lần kiểm nữa ở phía sau, và Gateway là lớp thứ ba.
    """
    try:
        return Allowlist.from_json(config.allowlist_path)
    except (OSError, ValueError):
        return None


def _objective_error(record: Dict[str, Any], allowlist: Optional[Allowlist]) -> Optional[str]:
    """Kiểm `verification_objective` NGAY sau LLM, không đợi tới bước propose.

    Prompt bắt Agent chỉ chọn endpoint có thật trong `allowed_endpoints`, nhưng
    6/18 objective trong lần chạy đã commit vẫn nằm ngoài allowlist. Bước propose
    có chặn chúng, nên không request nào thoát ra — nhưng record vẫn được ghi vào
    `analysis.jsonl` như thể hợp lệ, và không ai đếm được Agent sai bao nhiêu.

    Kiểm ở đây biến chuyện đó thành một lỗi validation có retry và có số liệu.
    """
    objective = record.get("verification_objective")
    if objective is None or allowlist is None:
        return None
    decision = validate_objective(objective, allowlist)
    if decision.accepted:
        return None
    return f"verification_objective bị allowlist từ chối: {decision.reason}"


@dataclass
class _GroupOutcome:
    """Aggregated result of analyzing a single finding group (initial attempt + optional retry)."""
    record: Optional[Dict[str, Any]]
    prompt_sha256: str
    llm_call_count: int = 0
    retry_count: int = 0
    invalid_output_count: int = 0
    calibrated: bool = False
    group_key: str = ""
    unsafe_output_count: int = 0
    invalid_objective_count: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


def _analyze_one_group(
    group: Any, config: AppConfig, provider: Any, allowlist: Optional[Allowlist] = None
) -> _GroupOutcome:
    """Analyze one finding group, validating the response and retrying once on failure."""
    analysis_res = analyze_finding_group(group, config, provider=provider)
    lr = analysis_res.llm_result

    outcome = _GroupOutcome(
        record=None,
        prompt_sha256=analysis_res.prompt_payload.prompt_sha256,
        llm_call_count=1,
        group_key=getattr(group, "group_key", ""),
        prompt_tokens=lr.prompt_tokens,
        completion_tokens=lr.completion_tokens,
        total_tokens=lr.total_tokens,
    )

    # Check for initial LLM execution error
    if lr.error or not lr.parsed_response:
        outcome.invalid_output_count = 1
        return outcome

    record_dict = lr.parsed_response

    # Post-LLM Schema Validation
    is_schema_valid, schema_err = validate_record_schema(record_dict, config.schema_path)

    # Post-LLM Provenance Validation
    is_prov_valid, prov_errs = validate_provenance(
        record_dict=record_dict,
        input_group_finding_ids=group.source_finding_ids,
        input_locations=[{"file": l.file, "line": l.line} for l in group.locations],
        input_knowledge_paths=[h["path"] for h in analysis_res.packet.knowledge_hits],
        input_cwes=group.cwe,
        input_owasps=group.owasp,
        input_source_evidence=analysis_res.packet.source_evidence,
        input_group_key=getattr(group, "group_key", None),
        input_knowledge_hits=analysis_res.packet.knowledge_hits,
    )

    unsafe = scan_unsafe_output(record_dict)

    # Objective sai KHONG lam mat ca record. `verification_objective` la truong tuy
    # chon; vut ca phan phan tich vi mot de xuat kiem chung sai la doi mot loi nho
    # lay mot mat mat lon. Thay no bang null va DEM lai — de xuat sai van hien len
    # trong so lieu thay vi bi im lang loc muon o buoc propose.
    objective_err = _objective_error(record_dict, allowlist)
    if objective_err is not None:
        record_dict["verification_objective"] = None
        outcome.invalid_objective_count = 1

    if is_schema_valid and is_prov_valid and not unsafe:
        outcome.record, calibration = calibrate_record(record_dict)
        outcome.calibrated = calibration.applied
        return outcome

    outcome.invalid_output_count = 1
    outcome.unsafe_output_count = 1 if unsafe else 0
    # Retry once with validation feedback if validation retries permitted
    if config.validation_max_retries < 1:
        return outcome

    outcome.retry_count = 1
    feedback_err = "; ".join(
        [msg for msg in (schema_err, "; ".join(prov_errs) or None) if msg]
        + ([f"Output chứa nội dung không an toàn: {'; '.join(unsafe)}"] if unsafe else [])
    )
    feedback_prompt = f"{analysis_res.prompt_payload.system_prompt}\n\n[System Note: Your previous output failed validation: {feedback_err}. Correct all schema/provenance errors and return valid JSON only.]"

    retry_res = analyze_finding_group(group, config, provider=provider, system_prompt_override=feedback_prompt)
    outcome.llm_call_count += 1

    rlr = retry_res.llm_result
    if rlr.parsed_response:
        r_schema_valid, _ = validate_record_schema(rlr.parsed_response, config.schema_path)
        r_prov_valid, _ = validate_provenance(
            record_dict=rlr.parsed_response,
            input_group_finding_ids=group.source_finding_ids,
            input_locations=[{"file": l.file, "line": l.line} for l in group.locations],
            input_knowledge_paths=[h["path"] for h in retry_res.packet.knowledge_hits],
            input_cwes=group.cwe,
            input_owasps=group.owasp,
            input_source_evidence=retry_res.packet.source_evidence,
            input_group_key=getattr(group, "group_key", None),
            input_knowledge_hits=retry_res.packet.knowledge_hits,
        )
        r_unsafe = scan_unsafe_output(rlr.parsed_response)
        if _objective_error(rlr.parsed_response, allowlist) is not None:
            rlr.parsed_response["verification_objective"] = None
            outcome.invalid_objective_count = 1
        if r_schema_valid and r_prov_valid and not r_unsafe:
            outcome.record, calibration = calibrate_record(rlr.parsed_response)
            outcome.calibrated = calibration.applied
            outcome.invalid_output_count = 0
            outcome.unsafe_output_count = 0

    return outcome


def _analyze_groups(
    groups: List[Any], config: AppConfig, provider: Any, allowlist: Optional[Allowlist] = None
) -> List[_GroupOutcome]:
    """Analyze all groups, returning outcomes in the same order as the input groups."""
    workers = min(max(1, config.llm_concurrency), len(groups))
    if workers == 1:
        return [_analyze_one_group(group, config, provider, allowlist) for group in groups]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # executor.map preserves input order regardless of completion order.
        return list(
            executor.map(
                lambda group: _analyze_one_group(group, config, provider, allowlist), groups
            )
        )


def run_pipeline(config: AppConfig) -> Dict[str, Any]:
    """Execute the complete security analysis pipeline end-to-end.
    
    Returns:
        Run summary dictionary.
    """
    start_time = time.time()

    # 1. Load input findings
    finding_file = load_findings(config.input_findings_path)
    findings = finding_file.findings
    input_finding_count = len(findings)

    # 2. Group findings deterministically
    groups = group_findings(findings, near_dup_line_threshold=config.near_dup_line_threshold)
    group_count = len(groups)

    if group_count == 0:
        write_jsonl_atomic([], config.output_jsonl_path)
        runtime_ms = round((time.time() - start_time) * 1000, 2)
        summary_dict = {
            "schema_version": "1.0",
            "completeness": "COMPLETE",
            "input_finding_count": 0,
            "group_count": 0,
            "output_record_count": 0,
            "missing_group_keys": [],
            "llm_call_count": 0,
            "retry_count": 0,
            "invalid_output_count": 0,
            "calibrated_record_count": 0,
            "unsafe_output_count": 0,
            "invalid_objective_count": 0,
            "runtime_ms": runtime_ms,
            "token_usage": {
                "prompt": None,
                "completion": None,
                "total": None
            },
            "model": config.model_name,
            "prompt_sha256": ""
        }
        _write_json_atomic(summary_dict, config.summary_path)
        return summary_dict

    # 3. Instantiate provider
    provider = build_llm(config)

    records: List[Dict[str, Any]] = []
    llm_call_count = 0
    retry_count = 0
    invalid_output_count = 0
    calibrated_record_count = 0
    unsafe_output_count = 0
    invalid_objective_count = 0
    missing_group_keys: List[str] = []
    total_prompt_tokens: Optional[int] = None
    total_completion_tokens: Optional[int] = None
    total_llm_tokens: Optional[int] = None
    last_prompt_sha256: str = ""

    # Groups are independent, and each outcome is aggregated below in input order,
    # so concurrency changes wall-clock runtime only, never the emitted records.
    allowlist = _load_allowlist(config)
    outcomes = _analyze_groups(groups, config, provider, allowlist)

    for outcome in outcomes:
        llm_call_count += outcome.llm_call_count
        retry_count += outcome.retry_count
        invalid_output_count += outcome.invalid_output_count
        calibrated_record_count += 1 if outcome.calibrated else 0
        unsafe_output_count += outcome.unsafe_output_count
        invalid_objective_count += outcome.invalid_objective_count
        last_prompt_sha256 = outcome.prompt_sha256

        if outcome.prompt_tokens is not None:
            total_prompt_tokens = (total_prompt_tokens or 0) + outcome.prompt_tokens
        if outcome.completion_tokens is not None:
            total_completion_tokens = (total_completion_tokens or 0) + outcome.completion_tokens
        if outcome.total_tokens is not None:
            total_llm_tokens = (total_llm_tokens or 0) + outcome.total_tokens

        if outcome.record is not None:
            records.append(outcome.record)
        else:
            # Mot nhom hop le khong sinh ra record nghia la mot phan ket qua bien
            # mat. Truoc day chuyen nay chi hien len duoi dang "20 record cho 21
            # nhom" va nguoi doc phai tu tru. Nay no co ten.
            missing_group_keys.append(outcome.group_key or "(khong ro group_key)")

    output_record_count = len(records)
    
    # 4. Write atomic JSONL output
    write_jsonl_atomic(records, config.output_jsonl_path)

    # 5. Build and write run summary
    runtime_ms = round((time.time() - start_time) * 1000, 2)
    model_name = config.model_name

    # Khong goi la thanh cong tron ven khi mot nhom hop le mat record.
    completeness = "COMPLETE" if not missing_group_keys else "PARTIAL"

    summary_dict = {
        "schema_version": "1.0",
        "completeness": completeness,
        "input_finding_count": input_finding_count,
        "group_count": group_count,
        "output_record_count": output_record_count,
        "missing_group_keys": missing_group_keys,
        "llm_call_count": llm_call_count,
        "retry_count": retry_count,
        "invalid_output_count": max(0, invalid_output_count),
        "calibrated_record_count": calibrated_record_count,
        "unsafe_output_count": unsafe_output_count,
        "invalid_objective_count": invalid_objective_count,
        "runtime_ms": runtime_ms,
        "token_usage": {
            "prompt": total_prompt_tokens,
            "completion": total_completion_tokens,
            "total": total_llm_tokens
        },
        "model": model_name,
        "prompt_sha256": last_prompt_sha256
    }

    _write_json_atomic(summary_dict, config.summary_path)

    return summary_dict
