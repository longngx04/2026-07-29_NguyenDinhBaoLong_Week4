"""Mọi phụ thuộc của orchestrator được tiêm từ ngoài qua một chỗ duy nhất.

Nhờ vậy test thay được lệnh chậm bằng lệnh nhanh mà vẫn là tiến trình thật,
không cần thư viện mock nào.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


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
    probe_override: dict[str, Any] | None = None
    dast_command: list[str] = field(default_factory=list)

    @classmethod
    def default(cls, repo_root: str | Path | None = None) -> "RunContext":
        root = Path(repo_root) if repo_root else _repo_root()
        runs_dir = Path(
            os.getenv("SENTINEL_RUNS_DIR", str(root / "artifacts" / "runs"))
        )
        default_scan_command = [str(root / "scripts" / "scan-opengrep.sh")]
        scan_override = os.getenv("SENTINEL_SCAN_COMMAND", "").strip()
        if scan_override:
            override_path = Path(scan_override)
            if override_path.is_file() and os.access(override_path, os.X_OK):
                scan_command = [scan_override]
            else:
                logger.warning(
                    "Bỏ qua SENTINEL_SCAN_COMMAND: giá trị phải là đường dẫn "
                    "tới một file executable"
                )
                scan_command = default_scan_command
        else:
            scan_command = default_scan_command

        # DAST la tuy chon: khong co script thi run van chay, chi thieu DAST.
        dast_script = root / "scripts" / "scan-zap.sh"
        dast_override = os.getenv("SENTINEL_DAST_COMMAND", "").strip()
        if dast_override:
            override = Path(dast_override)
            if override.is_file() and os.access(override, os.X_OK):
                dast_command = [dast_override]
            else:
                logger.warning(
                    "Bo qua SENTINEL_DAST_COMMAND: gia tri phai la duong dan "
                    "toi mot file executable"
                )
                dast_command = []
        elif dast_script.is_file() and os.access(dast_script, os.X_OK):
            dast_command = [str(dast_script)]
        else:
            dast_command = []

        return cls(
            repo_root=root,
            runs_dir=runs_dir,
            allowlist_path=root / "configs" / "gateway" / "endpoint-allowlist.json",
            scan_command=scan_command,
            normalize_command=[sys.executable, "-m", "project_sentinel.ingestion.normalizer"],
            gateway_api_key=os.getenv("SENTINEL_GATEWAY_API_KEY", ""),
            dast_command=dast_command,
        )


    def replace(self, **changes: Any) -> "RunContext":
        return replace(self, **changes)
