"""Secret-safe JSONL audit logging for verification executions."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_request(log_path: str, **fields: Any) -> None:
    """Append one bounded audit record without accepting headers or bodies."""
    forbidden = {"headers", "body", "api_key", "authorization", "cookie"}
    if forbidden.intersection(key.casefold() for key in fields):
        raise ValueError("Sensitive request fields are forbidden in the audit log")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        handle.write(existing)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        temp_name = handle.name
    os.replace(temp_name, path)
