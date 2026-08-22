"""Bước 4–5: agent đề xuất request kiểm chứng, rồi cổng phê duyệt chặn lại.

Đề xuất của agent KHÔNG được tin: mọi field thực thi được đều bị đối chiếu lại
với allowlist ở phía Python trước khi có bất kỳ request nào tồn tại.
"""

from __future__ import annotations

import json
from typing import Any

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.guardrails.approval import build_request, requires_approval
from project_sentinel.guardrails.events import append_event
from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.run_log import append_log
from project_sentinel.orchestrator.state import RunRecord, RunState
from project_sentinel.orchestrator.steps.common import (
    StepFailure,
    _write_json_artifact,
)
from project_sentinel.probe.proposal import SafeProbe, validate_objective

def _choose_objective(
    candidates: list[tuple[str | None, tuple[str, ...], dict[str, Any]]],
    allowlist: Allowlist,
):
    """Chọn đề xuất ít xâm lấn nhất trong số được allowlist duyệt.

    Mọi objective hợp lệ hiện đều là POST vì lane probe không cho phép GET
    mang payload. Khi có nhiều đề xuất hợp lệ, ưu tiên loại payload ít xâm
    lấn hơn (`empty_value` trước `long_string`). Không có đề xuất nào được
    duyệt thì trả về cái đầu tiên, để lý do bị chặn vẫn được ghi lại.

    Trả về `(analysis_id, finding_ids, objective, decision)`.
    """
    evaluated = [
        (analysis_id, finding_ids, objective, validate_objective(objective, allowlist))
        for analysis_id, finding_ids, objective in candidates
    ]
    accepted = [item for item in evaluated if item[3].accepted]
    if accepted:
        return next(
            (
                item
                for item in accepted
                # probe luôn khác None khi decision.accepted, nhưng viết rõ ra
                # để bất biến này được kiểm tra thay vì chỉ được tin.
                if item[3].probe is not None
                and item[3].probe.payload_kind == "empty_value"
            ),
            accepted[0],
        )
    if evaluated:
        return evaluated[0]
    return None, (), None, validate_objective(None, allowlist)


def step_propose(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 4 — lấy đề xuất của agent và kẹp nó về đúng allowlist."""
    source = record.root / "analysis.jsonl"
    if not source.exists():
        raise StepFailure(
            "Không có analysis.jsonl để lấy đề xuất; bước analyze chưa chạy"
        )

    record.mark_step("propose", "running")

    # (analysis_id, finding_ids, objective) — finding_ids đi cùng đề xuất để
    # proposal.json nói được nó định kiểm chứng finding nào, không chỉ nhóm nào.
    candidates: list[tuple[str | None, tuple[str, ...], dict[str, Any]]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StepFailure(
                f"analysis.jsonl chứa dòng JSON không hợp lệ: {exc}"
            ) from exc
        if not isinstance(entry, dict):
            raise StepFailure("analysis.jsonl chứa dòng không phải JSON object")
        if entry.get("verification_objective"):
            raw_ids = entry.get("source_finding_ids")
            entry_finding_ids = (
                tuple(str(item) for item in raw_ids if isinstance(item, str) and item)
                if isinstance(raw_ids, list)
                else ()
            )
            candidates.append(
                (
                    entry.get("analysis_id"),
                    entry_finding_ids,
                    entry["verification_objective"],
                )
            )

    try:
        allowlist = Allowlist.from_json(ctx.allowlist_path)
    except (OSError, ValueError) as exc:
        raise StepFailure(
            f"Không đọc được allowlist {ctx.allowlist_path}: {exc}"
        ) from exc

    finding_ids: tuple[str, ...]
    if ctx.probe_override is not None:
        analysis_id = "operator-override"
        finding_ids = ()
        objective = ctx.probe_override
        decision = validate_objective(objective, allowlist)
    else:
        analysis_id, finding_ids, objective, decision = _choose_objective(
            candidates, allowlist
        )
    accepted_count = sum(
        1 for _, _, item in candidates if validate_objective(item, allowlist).accepted
    )

    append_log(
        record.root,
        step="propose",
        level="info",
        message="Bắt đầu chọn đề xuất kiểm chứng",
        objectives_found=len(candidates),
        objectives_accepted=accepted_count,
        chosen_analysis_id=analysis_id,
        chosen_method=decision.probe.method if decision.probe else None,
    )

    payload = {
        "accepted": decision.accepted,
        "reason": decision.reason,
        "probe": (
            {
                "method": decision.probe.method,
                "path": decision.probe.path,
                "payload_kind": decision.probe.payload_kind,
            }
            if decision.probe
            else None
        ),
        "source_analysis_id": analysis_id,
        "source_finding_ids": list(finding_ids),
        "objective": objective,
        "objectives_found": len(candidates),
        "operator_override": ctx.probe_override is not None,
        "objectives_accepted": accepted_count,
    }
    (record.root / "proposal.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if objective is not None and not decision.accepted:
        append_event(
            record.root / "events.jsonl",
            run_id=record.run_id,
            kind="allowlist_block",
            detail={
                "endpoint_hint": objective.get("endpoint_hint")
                if isinstance(objective, dict)
                else None,
                "reason": decision.reason,
            },
        )
        append_log(
            record.root,
            step="propose",
            level="warn",
            message=f"Đề xuất bị chặn: {decision.reason}",
        )
    else:
        append_log(
            record.root,
            step="propose",
            level="info",
            message=decision.reason,
        )

    record.mark_step("propose", "done", detail={"accepted": decision.accepted})
    return record



def _load_proposal(record: RunRecord) -> dict:
    source = record.root / "proposal.json"
    if not source.exists():
        raise StepFailure("Không có proposal.json; bước propose chưa chạy")
    try:
        proposal = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StepFailure(f"Không đọc được proposal.json: {exc}") from exc
    if not isinstance(proposal, dict):
        raise StepFailure("proposal.json không phải JSON object")
    return proposal


def step_approval(record: RunRecord, ctx: RunContext) -> RunRecord:
    """Bước 5 — dừng lại chờ người duyệt, nếu request thuộc loại rủi ro."""
    proposal = _load_proposal(record)

    if not proposal.get("accepted") or not proposal.get("probe"):
        record.mark_step(
            "approval", "skipped", detail={"reason": "Không có probe được duyệt"}
        )
        append_log(
            record.root,
            step="approval",
            level="info",
            message="Bỏ qua phê duyệt: không có probe hợp lệ",
        )
        return record

    try:
        probe = SafeProbe(**proposal["probe"])
    except (TypeError, ValueError) as exc:
        raise StepFailure(f"Probe trong proposal.json không hợp lệ: {exc}") from exc

    if not requires_approval(probe):
        record.mark_step(
            "approval", "skipped", detail={"reason": "GET trơn, không cần duyệt"}
        )
        append_log(
            record.root,
            step="approval",
            level="info",
            message="Bỏ qua phê duyệt: request không rủi ro",
        )
        return record

    objective = proposal.get("objective")
    if not isinstance(objective, dict):
        objective = {}
    purpose = objective.get("description") or "Kiểm chứng finding"
    request = build_request(record.run_id, probe, purpose=purpose)
    _write_json_artifact(record.root / "approval-request.json", request.to_dict())

    record.state = RunState.AWAITING_APPROVAL
    record.mark_step("approval", "running")
    append_log(
        record.root,
        step="approval",
        level="info",
        message="Chờ người vận hành phê duyệt",
    )
    return record


__all__ = ["_load_proposal", "step_approval", "step_propose"]
