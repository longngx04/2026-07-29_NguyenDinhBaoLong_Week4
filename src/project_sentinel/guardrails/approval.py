"""Cổng phê duyệt của con người trước khi gửi request rủi ro.

send_probe nhận đối tượng ApprovalDecision trong bộ nhớ để kiểm tra tính hợp lệ
và ràng buộc fingerprint với request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from project_sentinel.probe.payload_kinds import payload_value_for
from project_sentinel.probe.proposal import SafeProbe

APPROVE_WORD = "approve"


def request_fingerprint(probe: SafeProbe) -> str:
    """Dấu vân tay của ĐÚNG request sẽ được gửi: method + path + payload thật."""
    payload = ""
    if probe.payload_kind is not None:
        payload = json.dumps(
            {"value": payload_value_for(probe.payload_kind)},
            ensure_ascii=False,
            sort_keys=True,
        )
    raw = f"{probe.method.upper()}|{probe.path}|{payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalRequest:
    run_id: str
    method: str
    endpoint: str
    payload: str
    purpose: str
    risk_reason: str
    request_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    decided_at: str
    decided_by: str
    request_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalDecision":
        return cls(
            approved=bool(data["approved"]),
            decided_at=str(data["decided_at"]),
            decided_by=str(data["decided_by"]),
            request_fingerprint=str(data.get("request_fingerprint", "")),
        )


def requires_approval(probe: SafeProbe) -> bool:
    """POST, hoặc bất kỳ payload đặc biệt nào, đều cần người duyệt."""
    return probe.method.upper() == "POST" or probe.payload_kind is not None


def build_request(run_id: str, probe: SafeProbe, purpose: str) -> ApprovalRequest:
    """Dựng phiếu duyệt hiển thị đúng payload thật sẽ được gửi đi."""
    payload = ""
    if probe.payload_kind is not None:
        payload = json.dumps(
            {"value": payload_value_for(probe.payload_kind)},
            ensure_ascii=False,
            sort_keys=True,
        )

    if probe.method.upper() == "POST":
        risk = "Request POST có thể làm thay đổi trạng thái phía ứng dụng."
    else:
        risk = f"Payload đặc biệt loại '{probe.payload_kind}' dùng để dò hành vi xử lý đầu vào."

    return ApprovalRequest(
        run_id=run_id,
        method=probe.method.upper(),
        endpoint=probe.path,
        payload=payload,
        purpose=purpose,
        risk_reason=risk,
        request_fingerprint=request_fingerprint(probe),
    )


def write_decision(path: str | Path, decision: ApprovalDecision) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(decision.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_decision(path: str | Path) -> ApprovalDecision | None:
    source = Path(path)
    if not source.exists():
        return None
    return ApprovalDecision.from_dict(json.loads(source.read_text(encoding="utf-8")))


def prompt_cli(
    request: ApprovalRequest,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> ApprovalDecision:
    """Hỏi người vận hành qua dòng lệnh. Mọi câu trả lời khác 'approve' là từ chối."""
    output_fn("")
    output_fn("═══ CẦN PHÊ DUYỆT TRƯỚC KHI GỬI REQUEST ═══")
    output_fn(f"  Endpoint  : {request.method} {request.endpoint}")
    output_fn(f"  Payload   : {request.payload or '(không có)'}")
    output_fn(f"  Mục đích  : {request.purpose}")
    output_fn(f"  Rủi ro    : {request.risk_reason}")
    output_fn("")

    try:
        answer = (
            input_fn("Gõ 'approve' để đồng ý, bất kỳ phím nào khác để từ chối: ") or ""
        ).strip()
        approved = answer.casefold() == APPROVE_WORD
    except (EOFError, KeyboardInterrupt):
        output_fn("→ KHÔNG ĐỌC ĐƯỢC CÂU TRẢ LỜI — coi như TỪ CHỐI")
        approved = False

    output_fn("→ ĐÃ DUYỆT" if approved else "→ ĐÃ TỪ CHỐI — không request nào được gửi")
    return ApprovalDecision(
        approved=approved,
        decided_at=datetime.now(timezone.utc).isoformat(),
        decided_by="cli-operator",
        request_fingerprint=request.request_fingerprint,
    )
