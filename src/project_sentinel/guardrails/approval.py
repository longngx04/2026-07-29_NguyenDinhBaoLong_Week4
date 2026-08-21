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
        """Dựng quyết định từ JSON đã parse. Sai kiểu thì hỏng, không đoán.

        `bool()` KHÔNG dùng được ở đây. Trong Python `bool("false")` là `True`, nên
        một UI hay một script ghi `{"approved": "false"}` — ý định TỪ CHỐI — sẽ được
        cổng hiểu là ĐỒNG Ý và request thật sự được gửi đi. Đây là ranh giới
        người-máy, nên nó fail closed: chỉ đúng literal JSON `true`/`false` được
        chấp nhận, mọi kiểu khác làm cả file vô hiệu.

        Từ chối cả file thay vì diễn giải thành `False` là có chủ ý: một quyết định
        không đọc được không phải là một quyết định từ chối, nó là một quyết định
        hỏng, và người vận hành cần biết điều đó.
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"decision.json phải là JSON object, nhận được {type(data).__name__}"
            )
        if "approved" not in data:
            raise ValueError("decision.json thiếu trường 'approved'")

        approved = data["approved"]
        # isinstance(True, int) là True trong Python, nên phải kiểm bool trước.
        if not isinstance(approved, bool):
            raise ValueError(
                "Trường 'approved' phải là JSON boolean true/false, nhận được "
                f"{type(approved).__name__} ({approved!r}). "
                "Không suy diễn kiểu ở cổng phê duyệt."
            )

        for field_name in ("decided_at", "decided_by"):
            if not isinstance(data.get(field_name), str) or not data[field_name].strip():
                raise ValueError(
                    f"decision.json cần '{field_name}' là chuỗi không rỗng"
                )

        fingerprint = data.get("request_fingerprint", "")
        if not isinstance(fingerprint, str):
            raise ValueError("'request_fingerprint' phải là chuỗi")

        return cls(
            approved=approved,
            decided_at=data["decided_at"],
            decided_by=data["decided_by"],
            request_fingerprint=fingerprint,
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
    """Đọc quyết định từ đĩa. Không có file nghĩa là chưa quyết định.

    File hỏng thì ném lỗi chứ không trả `None`: `None` nghĩa là "chưa ai quyết định"
    và bước probe sẽ chờ tiếp, còn một file sai kiểu nghĩa là "có ai đó đã quyết
    định nhưng ta không đọc được" — hai chuyện khác nhau, không được gộp.
    """
    source = Path(path)
    if not source.exists():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"decision.json không phải JSON hợp lệ: {exc}") from exc
    return ApprovalDecision.from_dict(payload)


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
