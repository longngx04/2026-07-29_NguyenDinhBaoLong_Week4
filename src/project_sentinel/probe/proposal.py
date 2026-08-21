"""Kẹp đề xuất của LLM về đúng những gì allowlist cho phép.

Đầu ra của agent là dữ liệu không đáng tin. Không request nào được gửi nếu
không qua được hàm này.
"""

from __future__ import annotations

from dataclasses import dataclass

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.payload_kinds import PAYLOAD_KIND_TO_TYPE

REQUIRED_FIELDS = ("description", "endpoint_hint", "payload_kind", "rationale")
ALLOWED_METHODS = frozenset({"GET", "POST"})


@dataclass(frozen=True)
class SafeProbe:
    method: str
    path: str
    payload_kind: str | None


@dataclass(frozen=True)
class ProposalDecision:
    accepted: bool
    probe: SafeProbe | None
    reason: str


def _reject(reason: str) -> ProposalDecision:
    return ProposalDecision(accepted=False, probe=None, reason=reason)


def validate_objective(
    objective: dict | None, allowlist: Allowlist
) -> ProposalDecision:
    """Kiểm tra một verification_objective do agent sinh ra."""
    if objective is None:
        return _reject("Agent không đề xuất bước kiểm chứng nào.")
    if not isinstance(objective, dict):
        return _reject("verification_objective không phải object.")

    missing = [name for name in REQUIRED_FIELDS if not objective.get(name)]
    if missing:
        return _reject(f"Thiếu field bắt buộc: {', '.join(missing)}")

    kind = objective["payload_kind"]
    if not isinstance(kind, str):
        return _reject("payload_kind không phải chuỗi.")
    if kind not in PAYLOAD_KIND_TO_TYPE:
        return _reject(f"payload_kind '{kind}' không nằm trong 4 loại an toàn.")

    hint = objective["endpoint_hint"]
    if not isinstance(hint, str):
        return _reject("endpoint_hint không phải chuỗi.")
    parts = hint.split(" ")
    if len(parts) != 2:
        return _reject(f"endpoint_hint sai định dạng '<METHOD> <path>': {hint!r}")

    method, path = parts[0].upper(), parts[1]
    if method not in ALLOWED_METHODS:
        return _reject(f"Method '{method}' không được phép.")
    if not path.startswith("/") or "?" in path:
        return _reject(f"Path phải là đường dẫn tương đối không có query: {path!r}")

    if not allowlist.is_allowed(method, path):
        return _reject(f"'{method} {path}' không có trong allowlist Gateway.")

    # Enforce ca template ngay tu buoc de xuat, khong doi toi `send_probe`.
    # Kiem cang som cang tot: mot objective bi chan o day tro thanh loi validation
    # co retry, con bi chan o send_probe thi ca record da nam trong analysis.jsonl
    # nhu the hop le roi.
    if not allowlist.is_allowed(method, path, payload_kind=kind, enforce_template=True):
        return _reject(
            f"payload_kind '{kind}' chưa được review cho '{method} {path}'."
        )

    return ProposalDecision(
        accepted=True,
        probe=SafeProbe(method=method, path=path, payload_kind=kind),
        reason=f"'{method} {path}' đã được allowlist duyệt.",
    )
