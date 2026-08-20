"""Nhật ký toàn trình của một lần chạy.

Mọi dòng đi qua bộ che trước khi chạm đĩa — đây là một trong các nút thắt
bảo đảm tiêu chí "dữ liệu nhạy cảm không xuất hiện trong log".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_sentinel.guardrails.redaction import redact_structure

LOG_LEVELS: frozenset[str] = frozenset({"info", "warn", "error"})
LOG_FILENAME = "run.log.jsonl"
MAX_MESSAGE_BYTES = 2048
RESERVED_FIELDS: frozenset[str] = frozenset({"ts", "step", "level", "message"})


def append_log(
    root: str | Path, *, step: str, level: str, message: str, **extra: Any
) -> None:
    """Ghi thêm một dòng nhật ký cho lần chạy."""
    if level not in LOG_LEVELS:
        raise ValueError(f"Mức log không hợp lệ: {level!r}")

    conflicts = RESERVED_FIELDS & set(extra)
    if conflicts:
        raise ValueError(f"Không được ghi đè trường hệ thống: {sorted(conflicts)}")

    if not isinstance(message, str):
        raise ValueError(f"message phải là chuỗi, nhận được {type(message).__name__}")

    payload, _ = redact_structure(
        {"step": step, "level": level, "message": message, **extra}
    )

    encoded = payload["message"].encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        payload["message"] = (
            encoded[:MAX_MESSAGE_BYTES].decode("utf-8", errors="ignore") + "…[cat]"
        )

    record = {"ts": datetime.now(timezone.utc).isoformat(), **payload}

    path = Path(root) / LOG_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_log(root: str | Path) -> list[dict[str, Any]]:
    path = Path(root) / LOG_FILENAME
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries
