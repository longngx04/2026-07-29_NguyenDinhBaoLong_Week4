"""Shared test configuration and fixtures."""

import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import pytest

from project_sentinel.probe.tool import GATEWAY_ORIGIN

# Repository root is the parent of the tests/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
KNOWLEDGE_DIR = REPO_ROOT / "data" / "knowledge-base"
SCHEMAS_DIR = REPO_ROOT / "schemas"


class _RedactedSecret(str):
    """String-compatible secret whose pytest/debug representation is always redacted."""

    def __repr__(self) -> str:
        return "'[REDACTED_SECRET]'"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def knowledge_dir() -> Path:
    return KNOWLEDGE_DIR


@pytest.fixture
def schema_path() -> Path:
    return SCHEMAS_DIR / "security-analysis-record.schema.json"


def _get_compose_gateway_container_id() -> str:
    """Resolve and return the container ID of the Docker Compose `gateway` service if running."""
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        pytest.fail(f"Failed to check Docker Compose status: {e}. Start containers with `make gateway-up`.")

    if res.returncode != 0:
        pytest.fail("Docker Compose check failed. Start containers with `make gateway-up`.")

    running_services = set(res.stdout.splitlines())
    if "gateway" not in running_services or "webgoat" not in running_services:
        pytest.fail(
            "Docker Compose services 'gateway' and 'webgoat' must both be running. "
            "Start containers with `make gateway-up`."
        )

    try:
        id_res = subprocess.run(
            ["docker", "compose", "ps", "-q", "gateway"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as e:
        pytest.fail(f"Failed to resolve Gateway container ID: {e}. Start containers with `make gateway-up`.")

    if id_res.returncode != 0:
        pytest.fail("Failed to resolve Gateway container ID. Start containers with `make gateway-up`.")

    container_id = id_res.stdout.strip().splitlines()[0] if id_res.stdout.strip() else ""
    if not container_id:
        pytest.fail("Gateway container ID is empty. Start containers with `make gateway-up`.")

    return container_id


@pytest.fixture(scope="session")
def gateway_ready() -> str:
    api_key = os.getenv("SENTINEL_GATEWAY_API_KEY")
    if not api_key:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("SENTINEL_GATEWAY_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        pytest.fail(
            "SENTINEL_GATEWAY_API_KEY is required for Gateway tests. "
            "Set it in .env or environment, and start containers with `make gateway-up`."
        )

    # 1. Verify Docker Compose services 'gateway' and 'webgoat' are running.
    # Goi vi tac dung phu: ham nay pytest.fail neu container chua chay.
    _get_compose_gateway_container_id()

    # 2. HTTP readiness: verify request WITHOUT API key returns HTTP 401
    try:
        req_unauth = urllib.request.Request(
            f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
            method="GET",
        )
        with urllib.request.urlopen(req_unauth, timeout=3.0) as resp:
            pytest.fail(f"Unauthenticated request returned HTTP {resp.status} (expected 401). Start containers with `make gateway-up`.")
    except urllib.error.HTTPError as e:
        if e.code != 401:
            pytest.fail(f"Unauthenticated request returned HTTP {e.code} (expected 401). Start containers with `make gateway-up`.")
    except Exception as e:
        pytest.fail(f"Gateway at {GATEWAY_ORIGIN} is unreachable: {e}. Start containers with `make gateway-up`.")

    # 3. HTTP readiness: verify request WITH API key reaches WebGoat successfully.
    try:
        req_auth = urllib.request.Request(
            f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
            headers={
                "X-Sentinel-API-Key": api_key,
                # Gateway nay enforce ca template, khong chi key + method + path.
                # Health check phai khai template da duoc review giong het moi
                # caller khac, neu khong no nhan 403.
                "X-Sentinel-Template": "tmpl_health_get",
            },
            method="GET",
        )
        with urllib.request.urlopen(req_auth, timeout=3.0) as resp:
            if resp.status != 200:
                pytest.fail(f"Authenticated request returned HTTP {resp.status} (expected 200). Start containers with `make gateway-up`.")
    except urllib.error.HTTPError as e:
        pytest.fail(f"Authenticated request returned HTTP {e.code} (expected 200). Start containers with `make gateway-up`.")
    except Exception as e:
        pytest.fail(f"Gateway at {GATEWAY_ORIGIN} is unreachable: {e}. Start containers with `make gateway-up`.")

    return _RedactedSecret(api_key)


@pytest.fixture(scope="session")
def llm_ready() -> str:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("LLM_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        pytest.fail(
            "LLM_API_KEY is required for live LLM tests (make llm-test). "
            "Set it in environment or .env."
        )
    return _RedactedSecret(api_key)


@pytest.fixture
def gateway_access_log_tracker():
    container_id = _get_compose_gateway_container_id()

    def snapshot_log_count() -> int:
        curr_id = _get_compose_gateway_container_id()
        if curr_id != container_id:
            pytest.fail("Gateway container disappeared or was replaced during test execution.")

        try:
            res = subprocess.run(
                ["docker", "logs", container_id],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                pytest.fail(f"Failed to read logs for Gateway container {container_id}.")
            lines = res.stdout.splitlines() + res.stderr.splitlines()
            return len([l for l in lines if "method=" in l or "/WebGoat" in l or "HTTP/1." in l])
        except Exception as exc:
            pytest.fail(f"Failed to read Gateway access logs for container {container_id}: {exc}")

    return snapshot_log_count
