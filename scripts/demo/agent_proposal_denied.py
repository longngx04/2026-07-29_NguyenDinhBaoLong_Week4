"""Đề xuất của agent bị allowlist chặn TRƯỚC khi có bất kỳ socket nào được mở.

Trước đây phần này của demo gọi `project_sentinel.verification.resolver` — một
package đã bị xoá khi kiến trúc chuyển sang `probe/`. Script vẫn công bố 14/14 pass
trong báo cáo Tuần 4 trong khi thực tế nó đã đỏ 5 mục.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from project_sentinel.gateway.allowlist import Allowlist  # noqa: E402
from project_sentinel.probe.proposal import validate_objective  # noqa: E402

ALLOWLIST = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"

# Ba dang de xuat sai khac nhau. Ca ba deu phai bi chan o phia Python.
DENIED_CASES = [
    ("endpoint khong duoc duyet", "POST /WebGoat/admin", "empty_value"),
    ("method sai cho endpoint dung", "POST /WebGoat/login", "empty_value"),
    ("payload chua duoc review", "POST /WebGoat/attack", "special_chars"),
]


def _objective(hint: str, payload_kind: str) -> dict:
    return {
        "description": "de xuat thu nghiem",
        "endpoint_hint": hint,
        "payload_kind": payload_kind,
        "rationale": "demo",
    }


def main() -> int:
    allowlist = Allowlist.from_json(ALLOWLIST)

    for label, hint, payload_kind in DENIED_CASES:
        decision = validate_objective(_objective(hint, payload_kind), allowlist)
        if decision.accepted:
            print(f"  KHONG CHAN DUOC: {label} ({hint}, {payload_kind})")
            return 1
        print(f"  bi chan dung: {label:<32} {hint}")

    # Doi chieu: mot de xuat DUOC duyet phai di qua, neu khong thi allowlist chi
    # dang chan tat ca va bai kiem tren khong chung minh duoc gi.
    accepted = validate_objective(
        _objective("POST /WebGoat/attack", "empty_value"), allowlist
    )
    if not accepted.accepted:
        print("  Allowlist dang chan CA de xuat hop le — cau hinh sai")
        return 1
    print("  de xuat da duoc review van di qua binh thuong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
