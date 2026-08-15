"""Verification pipeline helpers for Project Sentinel Week 4."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Union


def write_json_atomic(data: Any, output_path: Union[str, Path]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        temp_name = handle.name
        json.dump(data, handle, indent=2, ensure_ascii=False)
    Path(temp_name).replace(path)
