"""Sổ sự kiện guardrail, mỗi dòng một JSON.

Vừa là bằng chứng chấm điểm, vừa là nguồn cho màn hình Security events,
vừa là số liệu approve/reject của báo cáo cuối.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_sentinel.guardrails.redaction import redact_structure

EVENT_KINDS: frozenset[str] = frozenset(
    {"redaction", "injection", "approval", "allowlist_block"}
)


def append_event(log_path: str | Path, *, run_id: str, kind: str, detail: dict) -> None:
    """Ghi thêm một sự kiện guardrail. Nội dung detail được che trước khi ghi."""
    if kind not in EVENT_KINDS:
        raise ValueError(f"Loại sự kiện không được duyệt: {kind!r}")

    safe_detail, _ = redact_structure(dict(detail or {}))
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "kind": kind,
        "detail": safe_detail,
    }

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_events(log_path: str | Path) -> list[dict[str, Any]]:
    """Đọc toàn bộ sự kiện. File chưa tồn tại thì trả danh sách rỗng."""
    path = Path(log_path)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        # `json.loads("42")` và `json.loads("[1,2]")` đều thành công. Nhận bừa
        # thì downstream gọi `.get()` trên một int và lần chạy chết ở một chỗ
        # cách xa nguyên nhân. Chỉ JSON object mới là một sự kiện.
        if isinstance(entry, dict):
            events.append(entry)
    return events


def count_by_kind(events: list[dict[str, Any]]) -> dict[str, int]:
    """Đếm sự kiện theo loại, dùng cho bảng số liệu."""
    counts: dict[str, int] = {}
    for event in events:
        kind = event.get("kind", "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts
