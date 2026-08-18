"""Bốn hành vi cốt lõi của gateway, đúng tiêu chí hoàn thành tuần 4."""

import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

EXERCISE_ROOT = Path(__file__).resolve().parents[1]
if str(EXERCISE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXERCISE_ROOT))

os.environ.setdefault("EXERCISE_API_KEY", "test-key-cho-bai-tap")

from gateway.main import app, load_allowlist  # noqa: E402
from app.main import app as target_app  # noqa: E402

VALID_KEY = os.environ["EXERCISE_API_KEY"]


@pytest.fixture(scope="session", autouse=True)
def upstream_server():
    """Start real target app on 127.0.0.1:8000 in background daemon thread if not already listening."""
    import uvicorn

    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=0.5)
        yield
        return
    except Exception:
        pass

    config = uvicorn.Config(target_app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield
    server.should_exit = True


@pytest.fixture
def client(monkeypatch):
    """Mỗi test có một gateway sạch, để bộ đếm rate limit không dính sang nhau."""
    from gateway import main

    main.RATE_STATE.clear()
    return TestClient(app)


def test_allowlisted_endpoint_with_valid_key_reaches_upstream(client):
    response = client.get("/health", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_api_key_returns_401(client):
    response = client.get("/health")
    assert response.status_code == 401
    assert "key" in response.json()["detail"].lower()


def test_wrong_api_key_returns_401(client):
    response = client.get("/health", headers={"X-API-Key": "sai-be-bet"})
    assert response.status_code == 401


def test_endpoint_outside_allowlist_returns_403(client):
    response = client.get("/admin", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 403
    assert "allowlist" in response.json()["detail"].lower()


def test_debug_endpoint_outside_allowlist_returns_403(client):
    assert client.get("/debug", headers={"X-API-Key": VALID_KEY}).status_code == 403


def test_method_not_in_allowlist_returns_403(client):
    """POST /health không có trong allowlist dù GET /health thì có."""
    response = client.post("/health", headers={"X-API-Key": VALID_KEY}, json={})
    assert response.status_code == 403


def test_allowlisted_post_reaches_upstream(client):
    response = client.post(
        "/echo", headers={"X-API-Key": VALID_KEY}, json={"value": "xin chao"}
    )
    assert response.status_code == 200
    assert response.json()["received"] == {"value": "xin chao"}


def test_exceeding_rate_limit_returns_429(client):
    limit = load_allowlist()["rate_limit_per_minute"]
    for _ in range(limit):
        assert client.get("/health", headers={"X-API-Key": VALID_KEY}).status_code == 200
    response = client.get("/health", headers={"X-API-Key": VALID_KEY})
    assert response.status_code == 429


def test_api_key_never_appears_in_the_request_log(client, tmp_path, monkeypatch):
    from gateway import main

    log_path = tmp_path / "requests.jsonl"
    monkeypatch.setattr(main, "LOG_PATH", log_path)
    client.get("/health", headers={"X-API-Key": VALID_KEY})

    contents = log_path.read_text(encoding="utf-8")
    assert VALID_KEY not in contents, "API key bị ghi vào log — vi phạm tiêu chí đề bài"
    assert '"path": "/health"' in contents
    assert '"status": 200' in contents


def test_query_string_is_forwarded_to_upstream(client):
    response = client.get(
        "/echo-query?limit=1&q=cam", headers={"X-API-Key": VALID_KEY}
    )
    assert response.status_code == 200
    assert response.json()["query"] == {"limit": "1", "q": "cam"}
