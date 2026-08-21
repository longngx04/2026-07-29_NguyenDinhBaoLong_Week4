"""Những thứ mọi bước đều dùng: kiểu lỗi, ghi artifact, chạy lệnh ngoài."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from project_sentinel.guardrails.redaction import redact_structure
from project_sentinel.orchestrator.run_log import append_log

SUBPROCESS_TIMEOUT_SECONDS = 900


class StepFailure(Exception):
    """Một bước không hoàn thành được, kèm lý do cho người đọc."""


def _write_json_artifact(path: Path, payload: dict) -> None:
    """Ghi JSON sau nút thắt redaction bắt buộc của orchestrator."""
    safe_payload, _ = redact_structure(payload)
    path.write_text(
        json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _run_command(
    command: list[str], *, cwd: Path, step: str, root: str | Path
) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            # stdin cua tien trinh nay THUOC VE nguoi van hanh: cong phe duyet
            # doc cau tra loi tu do. Khong chuyen huong thi lenh ngoai ke thua
            # stdin va co the doc het, va toi luc hoi phe duyet chi con EOF —
            # bi dien giai thanh TU CHOI. Mac dinh fail-safe che mat loi nay,
            # nen no van an toan nhung duong phe duyet cua nguoi that khong
            # dung duoc: `printf 'approve\n' | cli run` luon ra TU CHOI.
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise StepFailure(f"Bước {step} quá hạn {SUBPROCESS_TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise StepFailure(f"Bước {step} không chạy được lệnh: {exc}") from exc

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:]
        raise StepFailure(f"Bước {step} thất bại (mã {result.returncode}): {tail}")

    if result.stdout and result.stdout.strip():
        append_log(root, step=step, level="info", message=result.stdout.strip())


__all__ = [
    "SUBPROCESS_TIMEOUT_SECONDS",
    "StepFailure",
    "_run_command",
    "_write_json_artifact",
]
