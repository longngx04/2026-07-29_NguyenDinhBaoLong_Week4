"""Mọi phụ thuộc của orchestrator được tiêm từ ngoài qua một chỗ duy nhất.

Nhờ vậy test thay được lệnh chậm bằng lệnh nhanh mà vẫn là tiến trình thật,
không cần thư viện mock nào.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RunContext:
    repo_root: Path
    runs_dir: Path
    allowlist_path: Path
    scan_command: list[str]
    normalize_command: list[str]
    gateway_api_key: str = field(default="", repr=False)
    llm_provider: Any | None = None

    @classmethod
    def default(cls, repo_root: str | Path | None = None) -> "RunContext":
        root = Path(repo_root) if repo_root else _repo_root()
        return cls(
            repo_root=root,
            runs_dir=root / "artifacts" / "runs",
            allowlist_path=root / "configs" / "gateway" / "endpoint-allowlist.json",
            scan_command=[str(root / "scripts" / "scan-opengrep.sh")],
            normalize_command=[sys.executable, "-m", "project_sentinel.ingestion.normalizer"],
            gateway_api_key=os.getenv("SENTINEL_GATEWAY_API_KEY", ""),
        )

    def replace(self, **changes: Any) -> "RunContext":
        return replace(self, **changes)
