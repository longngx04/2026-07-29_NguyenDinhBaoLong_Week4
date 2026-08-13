from __future__ import annotations
import json
import time
from pathlib import Path
from .models import GatewayErrorType


def log_request(
    log_path: str,
    method: str,
    path: str,
    payload_type: str | None,
    status_code: int | None,
    error_type: GatewayErrorType | None,
    elapsed_ms: float,
) -> None:
    """Chữ ký hàm CHỈ nhận field đã biết trước là an toàn — không có
    tham số headers/body nào ở đây, nên không có cách nào vô tình log
    API key."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": method,
        "path": path,
        "payload_type": payload_type,
        "status_code": status_code,
        "error_type": error_type.value if error_type else None,
        "elapsed_ms": round(elapsed_ms, 1),
    }
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
