"""Gateway đơn giản cho bài tập tuần 4.

Bốn việc, theo đúng thứ tự:
  1. Không có API key hợp lệ  → 401
  2. Không có trong allowlist → 403
  3. Vượt hạn mức request     → 429
  4. Còn lại                  → proxy sang upstream

Log ghi method, path, status, thời gian — KHÔNG BAO GIỜ ghi API key.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = BASE_DIR / "allowlist.json"
LOG_PATH = BASE_DIR / "requests.jsonl"

UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("EXERCISE_API_KEY", "")
UPSTREAM_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 65_536

RATE_STATE: dict[str, deque[float]] = defaultdict(deque)

app = FastAPI(title="Week 4 Exercise Gateway")


def load_allowlist() -> dict:
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def is_allowed(method: str, path: str) -> bool:
    for rule in load_allowlist()["endpoints"]:
        if rule["method"].upper() == method.upper() and rule["path"] == path:
            return True
    return False


def check_rate_limit(client_id: str) -> bool:
    """Cửa sổ trượt 60 giây. Trả False khi đã vượt hạn mức."""
    limit = load_allowlist()["rate_limit_per_minute"]
    now = time.monotonic()
    window = RATE_STATE[client_id]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def log_request(method: str, path: str, status: int, elapsed_ms: float) -> None:
    """Ghi một dòng audit. Cố ý không nhận tham số nào chứa được API key."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": method,
        "path": path,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.api_route("/{full_path:path}", methods=["GET", "POST"])
async def proxy(request: Request, full_path: str, x_api_key: str = Header(default="")):
    started = time.monotonic()
    path = "/" + full_path
    method = request.method

    def finish(status: int) -> None:
        log_request(method, path, status, (time.monotonic() - started) * 1000.0)

    current_api_key = os.getenv("EXERCISE_API_KEY", API_KEY)
    if not current_api_key or x_api_key != current_api_key:
        finish(401)
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai API key")

    if not is_allowed(method, path):
        finish(403)
        raise HTTPException(
            status_code=403, detail=f"'{method} {path}' không có trong allowlist"
        )

    if not check_rate_limit(x_api_key[:8]):
        finish(429)
        raise HTTPException(status_code=429, detail="Vượt hạn mức request mỗi phút")

    body = await request.body()
    current_upstream = os.getenv("UPSTREAM_URL", UPSTREAM_URL)
    query = request.url.query
    target_url = f"{current_upstream}{path}" + (f"?{query}" if query else "")
    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as http:
            upstream = await http.request(
                method,
                target_url,
                content=body or None,
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
            )
    except httpx.TimeoutException:
        finish(504)
        raise HTTPException(status_code=504, detail="Upstream timeout") from None
    except httpx.RequestError:
        finish(502)
        raise HTTPException(
            status_code=502, detail="Không kết nối được upstream"
        ) from None

    finish(upstream.status_code)
    content = upstream.content[:MAX_RESPONSE_BYTES]
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = {"raw": content.decode("utf-8", errors="replace")}
    return JSONResponse(status_code=upstream.status_code, content=payload)
