"""
Main analysis pipeline for Security Analysis Agent.
Coordinates loading, deduplication, evidence extraction, knowledge retrieval, LLM analysis,
post-LLM validation, atomic JSONL writing, and run summary output.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
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


def _load_allowlist(config: AppConfig) -> tuple[Optional[Allowlist], Optional[str]]:
    """Nạp allowlist một lần. Trả (allowlist, lý do suy giảm nếu có).

    Không để lỗi đọc file làm sập cả lần chạy phân tích: bước propose vẫn còn
    một lần kiểm nữa ở phía sau, và Gateway là lớp thứ ba — nên *biên giới mạng*
    vẫn an toàn.

    Nhưng im lặng bỏ qua thì không được. Không đọc được allowlist nghĩa là
    `invalid_objective_count` sẽ luôn bằng 0 vì không có gì để so, chứ không
    phải vì Agent làm đúng. Một con số đúng vì tình cờ là một con số nói dối.
    Lần chạy vẫn tiếp tục, nhưng nó tự khai là PARTIAL và nói rõ lý do.
    """
    try:
        return Allowlist.from_json(config.allowlist_path), None
    except (OSError, ValueError) as exc:
        return None, (
            f"Không nạp được endpoint allowlist ({config.allowlist_path}): "
            f"{type(exc).__name__}: {exc}. verification_objective KHÔNG được "
            "kiểm trong lần chạy này."
        )


def _allowed_endpoints_hint(allowlist: Optional[Allowlist]) -> str:
    """Liệt kê ĐÚNG các tổ hợp được duyệt, để feedback retry nói được điều gì cụ thể.

    Feedback cũ chỉ nói "objective bị allowlist từ chối" — đúng nhưng vô dụng:
    Agent không biết cái gì mới hợp lệ nên lần thử lại cũng sai như lần đầu.
    """
    if allowlist is None:
        return ""
    combinations: list[str] = []
    for rule in allowlist.rules:
        for template_id in rule.allowed_template_ids:
            template = allowlist.templates.get(template_id)
            if template is None or template.method != rule.method:
                continue
            kind = template.payload_kind
            combinations.append(
                f'{{"endpoint_hint": "{rule.method} {rule.path}", '
                f'"payload_kind": {json.dumps(kind)}}}'
            )
    if not combinations:
        return ""
    return (
        " Chỉ các tổ hợp sau được duyệt, dùng nguyên văn một trong số chúng "
        "hoặc đặt verification_objective = null: " + "; ".join(sorted(set(combinations)))
    )


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
    """Kết quả phân tích một nhóm (lần đầu + lần thử lại nếu có).

    `invalid_output_count` đếm số nhóm CÒN hỏng sau khi thử lại, còn
    `invalid_responses_observed` đếm số phản hồi hỏng đã thực sự nhận. Hai con
    số đó khác nhau, và trước đây chúng bị gộp làm một: retry thành công thì
    code đặt `invalid_output_count = 0`, nên một nhóm hỏng-rồi-sửa-được trông
    hệt như một nhóm chưa bao giờ hỏng. Chi phí LLM và dấu vết audit vì thế
    biến mất.
    """
    record: Optional[Dict[str, Any]]
    prompt_sha256: str
    llm_call_count: int = 0
    retry_count: int = 0
    invalid_output_count: int = 0
    invalid_responses_observed: int = 0
    calibrated: bool = False
    group_key: str = ""
    unsafe_output_count: int = 0
    unsafe_responses_observed: int = 0
    invalid_objective_count: int = 0
    valid_objective_count: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    def add_tokens(self, result: Any) -> None:
        """Cộng token của MỌI lần gọi, kể cả lần thử lại.

        Token của retry trước đây không được cộng, nên báo cáo chi phí thấp hơn
        thực tế đúng bằng phần đắt nhất: những nhóm phải gọi hai lần.
        """
        for field_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(result, field_name, None)
            if value is None:
                continue
            current = getattr(self, field_name)
            setattr(self, field_name, (current or 0) + value)


def _analyze_one_group(
    group: Any, config: AppConfig, provider: Any, allowlist: Optional[Allowlist] = None
) -> _GroupOutcome:
    """Phân tích một nhóm, kiểm phản hồi và thử lại đúng một lần nếu hỏng."""
    analysis_res = analyze_finding_group(group, config, provider=provider)
    lr = analysis_res.llm_result

    outcome = _GroupOutcome(
        record=None,
        prompt_sha256=analysis_res.prompt_payload.prompt_sha256,
        llm_call_count=1,
        group_key=getattr(group, "group_key", ""),
    )
    outcome.add_tokens(lr)

    # Check for initial LLM execution error
    if lr.error or not lr.parsed_response:
        outcome.invalid_output_count = 1
        outcome.invalid_responses_observed = 1
        return outcome

    record_dict = lr.parsed_response
    errors = _validate_response(record_dict, group, analysis_res, config, allowlist)

    if not errors.any():
        measured = _extract_measured_reachability(group, record_dict)
        outcome.record, calibration = calibrate_record(
            record_dict, measured_reachability=measured
        )
        outcome.calibrated = calibration.applied
        outcome.valid_objective_count = (
            1 if record_dict.get("verification_objective") is not None else 0
        )
        return outcome

    outcome.invalid_responses_observed = 1
    outcome.unsafe_responses_observed = 1 if errors.unsafe else 0

    if config.validation_max_retries < 1:
        return _settle(outcome, record_dict, errors, allowlist, group=group)

    outcome.retry_count = 1
    feedback_prompt = (
        f"{analysis_res.prompt_payload.system_prompt}\n\n[System Note: Your previous "
        f"output failed validation: {errors.feedback(allowlist)}. Correct all "
        "schema/provenance errors and return valid JSON only.]"
    )
    retry_res = analyze_finding_group(
        group, config, provider=provider, system_prompt_override=feedback_prompt
    )
    outcome.llm_call_count += 1
    rlr = retry_res.llm_result
    outcome.add_tokens(rlr)

    if not rlr.parsed_response:
        outcome.invalid_responses_observed += 1
        return _settle(outcome, record_dict, errors, allowlist, group=group)

    retry_errors = _validate_response(
        rlr.parsed_response, group, retry_res, config, allowlist
    )
    if retry_errors.any():
        outcome.invalid_responses_observed += 1
        outcome.unsafe_responses_observed += 1 if retry_errors.unsafe else 0
    return _settle(outcome, rlr.parsed_response, retry_errors, allowlist, group=group)



@dataclass
class _ResponseErrors:
    """Mọi lý do một phản hồi bị coi là không hợp lệ, tách theo loại."""
    schema: Optional[str] = None
    provenance: List[str] = field(default_factory=list)
    unsafe: List[str] = field(default_factory=list)
    objective: Optional[str] = None

    def any(self) -> bool:
        return bool(self.schema or self.provenance or self.unsafe or self.objective)

    def blocks_the_record(self) -> bool:
        """Objective sai KHÔNG làm mất cả record; ba loại còn lại thì có.

        `verification_objective` là trường tùy chọn. Vứt cả phần phân tích vì
        một đề xuất kiểm chứng sai là đổi một lỗi nhỏ lấy một mất mát lớn.
        """
        return bool(self.schema or self.provenance or self.unsafe)

    def feedback(self, allowlist: Optional[Allowlist]) -> str:
        parts = [msg for msg in (self.schema, "; ".join(self.provenance) or None) if msg]
        if self.unsafe:
            parts.append(f"Output chứa nội dung không an toàn: {'; '.join(self.unsafe)}")
        if self.objective:
            # Nói ĐÚNG cái gì hợp lệ, không chỉ nói cái vừa gửi là sai.
            parts.append(self.objective + _allowed_endpoints_hint(allowlist))
        return "; ".join(parts)


def _validate_response(
    record_dict: Dict[str, Any],
    group: Any,
    analysis_res: Any,
    config: AppConfig,
    allowlist: Optional[Allowlist],
) -> _ResponseErrors:
    """Chạy toàn bộ kiểm tra hậu-LLM trên một phản hồi."""
    is_schema_valid, schema_err = validate_record_schema(record_dict, config.schema_path)
    is_zap = any(getattr(f, "tool", "") == "zap" for f in (getattr(group, "findings", []) or []))
    input_locations = [
        {"url": location.file}
        if (is_zap or location.file.startswith("http://") or location.file.startswith("https://"))
        else {"file": location.file, "line": location.line}
        for location in group.locations
    ]
    is_prov_valid, prov_errs = validate_provenance(
        record_dict=record_dict,
        input_group_finding_ids=group.source_finding_ids,
        input_locations=input_locations,
        input_knowledge_paths=[hit["path"] for hit in analysis_res.packet.knowledge_hits],
        input_cwes=group.cwe,
        input_owasps=group.owasp,
        input_source_evidence=analysis_res.packet.source_evidence,
        input_group_key=getattr(group, "group_key", None),
        input_knowledge_hits=analysis_res.packet.knowledge_hits,
    )

    return _ResponseErrors(
        schema=None if is_schema_valid else schema_err,
        provenance=[] if is_prov_valid else prov_errs,
        unsafe=list(scan_unsafe_output(record_dict)),
        objective=_objective_error(record_dict, allowlist),
    )


def _extract_measured_reachability(group: Any, record_dict: Dict[str, Any]) -> Optional[str]:
    raw_findings = getattr(group, "findings", []) or []
    source_ids = set(record_dict.get("source_finding_ids") or [])
    if not source_ids:
        return None
    strengths: set[str] = set()
    for f in raw_findings:
        f_id = getattr(f, "id", None) or (f.get("id") if isinstance(f, dict) else None)
        if f_id and f_id in source_ids:
            re_block = getattr(f, "runtime_evidence", None)
            if re_block is None and isinstance(f, dict):
                re_block = f.get("runtime_evidence")
            if isinstance(re_block, dict):
                strength = re_block.get("strength")
                if strength:
                    strengths.add(str(strength))

    if strengths & {"reachable", "reachable_and_alerted"}:
        return "proven"
    if strengths & {"route_known_not_reached"}:
        return "not_proven"
    return None


def _settle(
    outcome: _GroupOutcome,
    record_dict: Dict[str, Any],
    errors: _ResponseErrors,
    allowlist: Optional[Allowlist],
    group: Any = None,
) -> _GroupOutcome:
    """Chốt kết quả cuối của một nhóm sau khi đã hết lượt thử lại."""
    if errors.blocks_the_record():
        outcome.invalid_output_count = 1
        outcome.unsafe_output_count = 1 if errors.unsafe else 0
        return outcome

    if errors.objective is not None:
        # Không mất record, nhưng đề xuất sai vẫn phải hiện lên trong số liệu
        # thay vì bị im lặng lọc muộn ở bước propose.
        record_dict["verification_objective"] = None
        outcome.invalid_objective_count = 1
    elif record_dict.get("verification_objective") is not None:
        outcome.valid_objective_count = 1

    measured = _extract_measured_reachability(group, record_dict) if group is not None else None
    outcome.record, calibration = calibrate_record(
        record_dict, measured_reachability=measured
    )
    outcome.calibrated = calibration.applied
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
        # Khong co nhom nao thi khong co gi de kiem, nhung van phai noi that
        # allowlist co nap duoc hay khong thay vi khai bua la co.
        empty_allowlist, empty_allowlist_problem = _load_allowlist(config)
        write_jsonl_atomic([], config.output_jsonl_path)
        runtime_ms = round((time.time() - start_time) * 1000, 2)
        summary_dict: Dict[str, Any] = {
            "schema_version": "1.0",
            "completeness": "COMPLETE" if empty_allowlist_problem is None else "PARTIAL",
            "input_finding_count": 0,
            "group_count": 0,
            "output_record_count": 0,
            "missing_group_keys": [],
            "llm_call_count": 0,
            "retry_count": 0,
            "invalid_output_count": 0,
            "unresolved_groups": 0,
            "invalid_responses_observed": 0,
            "calibrated_record_count": 0,
            "unsafe_output_count": 0,
            "unsafe_responses_observed": 0,
            "invalid_objective_count": 0,
            "valid_objective_count": 0,
            "objective_validity_rate": None,
            "allowlist_loaded": empty_allowlist is not None,
            "degraded_reasons": (
                [empty_allowlist_problem] if empty_allowlist_problem else []
            ),
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
    invalid_responses_observed = 0
    calibrated_record_count = 0
    unsafe_output_count = 0
    unsafe_responses_observed = 0
    invalid_objective_count = 0
    valid_objective_count = 0
    missing_group_keys: List[str] = []
    degraded_reasons: List[str] = []
    total_prompt_tokens: Optional[int] = None
    total_completion_tokens: Optional[int] = None
    total_llm_tokens: Optional[int] = None
    last_prompt_sha256: str = ""

    # Groups are independent, and each outcome is aggregated below in input order,
    # so concurrency changes wall-clock runtime only, never the emitted records.
    allowlist, allowlist_problem = _load_allowlist(config)
    if allowlist_problem is not None:
        degraded_reasons.append(allowlist_problem)
    outcomes = _analyze_groups(groups, config, provider, allowlist)

    for outcome in outcomes:
        llm_call_count += outcome.llm_call_count
        retry_count += outcome.retry_count
        invalid_output_count += outcome.invalid_output_count
        invalid_responses_observed += outcome.invalid_responses_observed
        calibrated_record_count += 1 if outcome.calibrated else 0
        unsafe_output_count += outcome.unsafe_output_count
        unsafe_responses_observed += outcome.unsafe_responses_observed
        invalid_objective_count += outcome.invalid_objective_count
        valid_objective_count += outcome.valid_objective_count
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

    # Khong goi la thanh cong tron ven khi mot nhom hop le mat record, hoac khi
    # mot lop kiem tra da bi tat vi loi cau hinh.
    completeness = (
        "COMPLETE" if not missing_group_keys and not degraded_reasons else "PARTIAL"
    )

    summary_dict = {
        "schema_version": "1.0",
        "completeness": completeness,
        "input_finding_count": input_finding_count,
        "group_count": group_count,
        "output_record_count": output_record_count,
        "missing_group_keys": missing_group_keys,
        "llm_call_count": llm_call_count,
        "retry_count": retry_count,
        # `unresolved_*` = con hong sau khi da thu lai. `*_observed` = tong so
        # phan hoi hong da that su nhan. Gop hai nghia nay lam mot lam bien mat
        # ca chi phi retry lan dau vet audit cua nhung phan hoi da bi tu choi.
        "invalid_output_count": max(0, invalid_output_count),
        "unresolved_groups": max(0, invalid_output_count),
        "invalid_responses_observed": invalid_responses_observed,
        "calibrated_record_count": calibrated_record_count,
        "unsafe_output_count": unsafe_output_count,
        "unsafe_responses_observed": unsafe_responses_observed,
        "invalid_objective_count": invalid_objective_count,
        "valid_objective_count": valid_objective_count,
        "objective_validity_rate": (
            round(valid_objective_count / output_record_count, 4)
            if output_record_count
            else None
        ),
        "allowlist_loaded": allowlist is not None,
        "degraded_reasons": degraded_reasons,
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
