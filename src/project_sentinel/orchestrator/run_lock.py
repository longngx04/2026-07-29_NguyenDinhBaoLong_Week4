"""Khoá liên tiến trình cho một lần chạy, cộng một khoá chiếm bền trên đĩa.

`resume_run` trước đây là: nạp state → kiểm `AWAITING_APPROVAL` → chạy phase hai.
Ba bước đó không nằm trong một giao dịch nào, nên hai lệnh resume đồng thời cùng
đọc `AWAITING_APPROVAL` rồi cùng gửi probe. Ép hai luồng cùng nạp state
trước khi chạy và đo được::

    concurrent_resume_probe_calls=2

UI sẽ làm xác suất đó tăng mạnh: double-click, retry của trình duyệt, hai tab,
reverse-proxy retry, hoặc hai worker.

`threading.Lock` không đủ: CLI và tiến trình nền của web là hai *tiến trình*.
`flock` là khoá của open file description, nên nó đúng cả giữa hai tiến trình
lẫn giữa hai luồng mở file riêng — và hệ điều hành tự nhả khi tiến trình chết.

Khoá là điều kiện cần chứ chưa đủ: khoá nhả khi tiến trình kết thúc, nên lần
resume thứ hai *sau đó* vẫn phải bị chặn. Đó là việc của khoá chiếm bền trên
đĩa (`probe-claim.json`) và của chính chuyển trạng thái được ghi dưới khoá.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_NAME = ".resume.lock"
CLAIM_NAME = "probe-claim.json"


@contextmanager
def run_lock(root: Path) -> Iterator[bool]:
    """Khoá độc quyền cho một lần chạy. KHÔNG chờ: bận thì trả về ``False``.

    Chờ là sai cho UI — một cú double-click sẽ giữ một request treo cho tới khi
    probe xong. Người gọi thứ hai cần biết ngay rằng nó không giành được lượt.
    """
    root.mkdir(parents=True, exist_ok=True)
    handle = os.open(root / LOCK_NAME, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


def idempotency_key(run_id: str, root: Path) -> str:
    """Khoá định danh một lượt phase hai: run_id + đúng quyết định đã ký.

    Buộc vào nội dung `decision.json` chứ không chỉ vào `run_id`: một quyết định
    khác là một lượt kiểm chứng khác, và phải được nhìn thấy là khác.
    """
    decision = root / "decision.json"
    payload = decision.read_bytes() if decision.exists() else b""
    digest = hashlib.sha256(run_id.encode("utf-8") + b"\0" + payload).hexdigest()
    return f"{run_id}:{digest[:32]}"


def read_claim(root: Path) -> dict[str, Any] | None:
    """Đọc khoá chiếm đã ghi. Bản ghi hỏng coi như chưa có khoá chiếm."""
    path = root / CLAIM_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_claim(root: Path, key: str) -> dict[str, Any]:
    """Ghi khoá chiếm một cách nguyên tử. Chỉ gọi khi đang giữ ``run_lock``."""
    claim = {
        "idempotency_key": key,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "claimed_by_pid": os.getpid(),
    }
    target = root / CLAIM_NAME
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(claim, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, target)
    return claim
