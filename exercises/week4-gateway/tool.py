"""Python tool gửi request kiểm thử qua gateway.

Deliverable tuần 4: gửi GET, gửi POST kèm dữ liệu thử, đặt header, đọc status
code và một phần response. Có timeout và giới hạn kích thước đọc.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_GATEWAY_URL = "http://127.0.0.1:9000"
API_KEY_HEADER = "X-API-Key"
MAX_PREVIEW_CHARS = 512

# Bốn payload an toàn đề bài cho phép. Không có payload phá hoại nào ở đây.
SAFE_PAYLOADS = {
    "long_string": "A" * 1024,
    "special_chars": "!@#$%^&*()'\"<>;",
    "empty_value": "",
    "wrong_type": 12345,
}


@dataclass(frozen=True)
class Result:
    status_code: int | None
    body_preview: str
    elapsed_ms: float
    error: str | None


def send(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> Result:
    """Gửi một request qua gateway và trả về kết quả đã được giới hạn."""
    gateway_url = os.getenv("EXERCISE_GATEWAY_URL", DEFAULT_GATEWAY_URL)
    request_headers = dict(headers or {})
    request_headers[API_KEY_HEADER] = os.getenv("EXERCISE_API_KEY", "")

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        f"{gateway_url}{path}",
        data=data,
        headers=request_headers,
        method=method.upper(),
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_PREVIEW_CHARS * 4)
            return Result(
                status_code=response.status,
                body_preview=raw.decode("utf-8", errors="replace")[:MAX_PREVIEW_CHARS],
                elapsed_ms=round((time.monotonic() - started) * 1000.0, 2),
                error=None,
            )
    except urllib.error.HTTPError as err:
        raw = err.read(MAX_PREVIEW_CHARS * 4) if err.fp else b""
        return Result(
            status_code=err.code,
            body_preview=raw.decode("utf-8", errors="replace")[:MAX_PREVIEW_CHARS],
            elapsed_ms=round((time.monotonic() - started) * 1000.0, 2),
            error=None,
        )
    except TimeoutError as err:
        return Result(
            status_code=None,
            body_preview="",
            elapsed_ms=round((time.monotonic() - started) * 1000.0, 2),
            error=f"Timeout sau {timeout}s: {err}",
        )
    except urllib.error.URLError as err:
        reason = str(err.reason)
        label = "Timeout" if "timed out" in reason.lower() else "Connection error"
        return Result(
            status_code=None,
            body_preview="",
            elapsed_ms=round((time.monotonic() - started) * 1000.0, 2),
            error=f"{label}: {reason}",
        )


if __name__ == "__main__":
    for method, path in [
        ("GET", "/health"),
        ("GET", "/items"),
        ("POST", "/echo"),
        ("GET", "/admin"),
        ("GET", "/debug"),
    ]:
        payload = {"value": SAFE_PAYLOADS["long_string"]} if method == "POST" else None
        outcome = send(method, path, body=payload)
        print(f"{method:5} {path:10} -> {outcome.status_code}  {outcome.error or ''}")
