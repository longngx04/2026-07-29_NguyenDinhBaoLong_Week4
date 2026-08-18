"""Python tool gửi request qua gateway — deliverable của tuần 4."""

import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import uvicorn

EXERCISE_ROOT = Path(__file__).resolve().parents[1]
if str(EXERCISE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXERCISE_ROOT))

API_KEY = os.environ.setdefault("EXERCISE_API_KEY", "test-key-cho-bai-tap")

from app.main import app as target_app  # noqa: E402
from gateway.main import app as gateway_app  # noqa: E402
from tool import Result, send  # noqa: E402


def _wait_until_ready(url: str, headers: dict[str, str] | None = None, timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    req = urllib.request.Request(url, headers=headers or {})
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(req, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.05)
    return False


@pytest.fixture(scope="session")
def gateway_process():
    """Start real upstream app on 8000 and gateway on 9000."""
    app_server = None
    if not _wait_until_ready("http://127.0.0.1:8000/health", timeout_s=0.2):
        app_config = uvicorn.Config(target_app, host="127.0.0.1", port=8000, log_level="error")
        app_server = uvicorn.Server(app_config)
        app_thread = threading.Thread(target=app_server.run, daemon=True)
        app_thread.start()
        if not _wait_until_ready("http://127.0.0.1:8000/health", timeout_s=5.0):
            pytest.fail("Target app không sẵn sàng trên cổng 8000 sau 5s")

    gw_server = None
    if not _wait_until_ready("http://127.0.0.1:9000/health", headers={"X-API-Key": API_KEY}, timeout_s=0.2):
        gw_config = uvicorn.Config(gateway_app, host="127.0.0.1", port=9000, log_level="error")
        gw_server = uvicorn.Server(gw_config)
        gw_thread = threading.Thread(target=gw_server.run, daemon=True)
        gw_thread.start()
        if not _wait_until_ready("http://127.0.0.1:9000/health", headers={"X-API-Key": API_KEY}, timeout_s=5.0):
            pytest.fail("Gateway không sẵn sàng trên cổng 9000 sau 5s")

    yield "http://127.0.0.1:9000"

    if gw_server:
        gw_server.should_exit = True
    if app_server:
        app_server.should_exit = True


def test_result_carries_status_and_bounded_preview():
    result = Result(status_code=200, body_preview="x" * 10, elapsed_ms=1.0, error=None)
    assert result.status_code == 200
    assert result.error is None


def test_send_sets_the_api_key_header_and_returns_status(gateway_process):
    result = send("GET", "/health")
    assert result.status_code == 200
    assert "ok" in result.body_preview


def test_send_reports_403_for_endpoint_outside_allowlist(gateway_process):
    result = send("GET", "/admin")
    assert result.status_code == 403


def test_send_can_post_a_body(gateway_process):
    result = send("POST", "/echo", body={"value": "chuoi dai" * 10})
    assert result.status_code == 200
    assert "chuoi dai" in result.body_preview


def test_send_handles_connection_error_without_raising(monkeypatch):
    monkeypatch.setenv("EXERCISE_GATEWAY_URL", "http://127.0.0.1:59999")
    result = send("GET", "/health")
    assert result.status_code is None
    assert result.error is not None
    assert "connect" in result.error.lower() or "refus" in result.error.lower()


def test_send_handles_timeout_without_raising(gateway_process):
    result = send("GET", "/health", timeout=0.001)
    assert result.status_code is None
    assert result.error is not None
    assert "timeout" in result.error.lower() or "timed out" in result.error.lower()


def test_body_preview_is_bounded(gateway_process):
    """Response dài hơn ngưỡng phải bị cắt đúng 512 ký tự."""
    from tool import SAFE_PAYLOADS
    result = send("POST", "/echo", body={"value": SAFE_PAYLOADS["long_string"]})
    assert result.status_code == 200
    assert len(result.body_preview) == 512

