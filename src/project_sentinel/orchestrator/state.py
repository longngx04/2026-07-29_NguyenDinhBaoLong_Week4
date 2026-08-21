"""Trạng thái một lần chạy, bền trên đĩa.

Không giữ trạng thái trong bộ nhớ tiến trình: CLI và web là hai tiến trình
khác nhau, nên `state.json` là nguồn sự thật duy nhất cho cả hai.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STEP_NAMES: tuple[str, ...] = (
    "scan", "normalize", "analyze", "propose",
    "approval", "probe", "scrub", "report", "finalize",
)

VALID_STATUSES = frozenset({"pending", "running", "done", "failed", "skipped"})
_TERMINAL = frozenset({"DONE", "REJECTED", "FAILED"})


class RunState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    NORMALIZING = "NORMALIZING"
    ANALYZING = "ANALYZING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PROBING = "PROBING"
    SCRUBBING = "SCRUBBING"
    REPORTING = "REPORTING"
    DONE = "DONE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

    def is_terminal(self) -> bool:
        return self.value in _TERMINAL


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepRecord:
    index: int
    name: str
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: float = 0.0
    detail: dict[str, Any] | None = None


@dataclass
class RunRecord:
    run_id: str
    root: Path
    state: RunState = RunState.IDLE
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    steps: list[StepRecord] = field(default_factory=list)
    error: str | None = None

    def step(self, name: str) -> StepRecord:
        for item in self.steps:
            if item.name == name:
                return item
        raise KeyError(f"Không có bước tên {name!r}")

    def mark_step(
        self, name: str, status: str, detail: dict[str, Any] | None = None
    ) -> StepRecord:
        if status not in VALID_STATUSES:
            raise ValueError(f"Trạng thái bước không hợp lệ: {status!r}")
        target = self.step(name)
        now = _now()

        if status == "running":
            target.started_at = now
            target.finished_at = None
        elif status in {"done", "failed", "skipped"}:
            target.finished_at = now
            if target.started_at:
                started = datetime.fromisoformat(target.started_at)
                target.elapsed_ms = round(
                    (datetime.fromisoformat(now) - started).total_seconds() * 1000.0, 2
                )

        target.status = status
        if detail is not None:
            target.detail = detail
        self.updated_at = now
        return target

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "steps": [asdict(step) for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], root: Path) -> "RunRecord":
        known = {f.name for f in dataclasses.fields(StepRecord)}
        return cls(
            run_id=data["run_id"],
            root=root,
            state=RunState(data["state"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            error=data.get("error"),
            steps=[
                StepRecord(**{k: v for k, v in item.items() if k in known})
                for item in data["steps"]
            ],
        )


def new_run(runs_dir: str | Path) -> RunRecord:
    """Tạo một lần chạy mới cùng thư mục của nó."""
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = base
    root = Path(runs_dir) / run_id
    suffix = 1
    while root.exists():
        run_id = f"{base[:-1]}-{suffix}Z"
        root = Path(runs_dir) / run_id
        suffix += 1
    root.mkdir(parents=True)
    return RunRecord(
        run_id=run_id,
        root=root,
        steps=[StepRecord(index=i, name=name) for i, name in enumerate(STEP_NAMES, 1)],
    )


def save_run(record: RunRecord) -> None:
    record.root.mkdir(parents=True, exist_ok=True)
    target = record.root / "state.json"
    payload = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w", dir=target.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(payload)
        temp_name = handle.name
    os.replace(temp_name, target)


def _confined_run_root(runs_dir: str | Path, run_id: str) -> Path:
    """Giai duong dan lan chay va bat buoc no nam HAN trong runs_dir.

    `list_runs`/`load_run` truoc day di theo symlink, nen mot symlink dat trong
    `runs/` doc duoc file bat ky ma tien trinh co quyen. `_confine_path()` da ton
    tai trong CLI nhung khong duoc dung o day.
    """
    base = Path(runs_dir).resolve()
    root = (base / run_id).resolve()
    if root != base and base not in root.parents:
        raise ValueError(
            f"run_id '{run_id}' tro ra ngoai thu muc lan chay {base}"
        )
    if root.parent != base:
        raise ValueError(f"run_id '{run_id}' khong phai mot lan chay truc tiep")
    return root


def load_run(runs_dir: str | Path, run_id: str) -> RunRecord:
    root = _confined_run_root(runs_dir, run_id)
    data = json.loads((root / "state.json").read_text(encoding="utf-8"))
    return RunRecord.from_dict(data, root)


def list_runs(runs_dir: str | Path) -> list[str]:
    """Danh sách run_id, mới nhất trước (theo created_at trong state.json)."""
    base = Path(runs_dir)
    if not base.is_dir():
        return []
    entries = []
    resolved_base = base.resolve()
    for item in base.iterdir():
        # Symlink khong bao gio la mot lan chay. Bo qua im lang o day la dung:
        # `list_runs` chi liet ke thu co that, con `load_run` moi la cho bao loi.
        if item.is_symlink() or not item.is_dir():
            continue
        if item.resolve().parent != resolved_base:
            continue
        state_file = item / "state.json"
        if not state_file.exists():
            continue
        try:
            created = json.loads(state_file.read_text(encoding="utf-8"))["created_at"]
        except (ValueError, KeyError, OSError):
            created = ""  # bản ghi hỏng thì xếp cuối, không làm sập hàm
        entries.append((created, item.name))
    return [name for _, name in sorted(entries, reverse=True)]


