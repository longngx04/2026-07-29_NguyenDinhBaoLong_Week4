"""Sinh lại bản đã lọc của bộ nhãn recall từ bản gốc của mentor.

Bản gốc được dựng trên một phiên bản WebGoat khác, nên vài mục trỏ tới file không
tồn tại trong bản đang ghim. Giữ chúng lại thì chúng thành false negative vĩnh viễn
và làm recall xấu đi một cách sai sự thật.

Kết quả lọc được **commit** để bộ chấm chạy được từ một `git archive HEAD`: archive
không mang theo submodule, và trước đây điều đó làm 7 test đỏ trên fresh clone.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eval.recall import DEFAULT_RECALL_TRUTH, DEFAULT_TARGET_ROOT, RAW_RECALL_TRUTH


def _submodule_commit() -> str:
    try:
        output = subprocess.run(
            ["git", "submodule", "status", "benchmarks/targets/webgoat"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return "khong-ro"
    return output[0].lstrip("+-") if output else "khong-ro"


def main() -> int:
    from eval.recall import load_vulnerabilities

    if not Path(DEFAULT_TARGET_ROOT).exists():
        raise SystemExit(
            f"Không thấy submodule WebGoat tại {DEFAULT_TARGET_ROOT}. "
            "Chạy: git submodule update --init --recursive"
        )

    rows = load_vulnerabilities(RAW_RECALL_TRUTH, target_root=DEFAULT_TARGET_ROOT)
    payload = {
        "schema_version": "1.0",
        "derived_from": "mentor/webgoat-vulnerabilities.jsonl",
        "webgoat_submodule_commit": _submodule_commit(),
        "note": (
            "Danh sach da LOC: chi giu muc tro toi file co that trong ban WebGoat "
            "dang ghim. Duoc commit de bo cham chay duoc tu mot `git archive HEAD`. "
            "Sinh lai bang: make refresh-recall-truth"
        ),
        "count": len(rows),
        "vulnerabilities": rows,
    }
    Path(DEFAULT_RECALL_TRUTH).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Đã ghi {len(rows)} mục vào {DEFAULT_RECALL_TRUTH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
