"""Shared test configuration and fixtures."""

import os
from pathlib import Path
import subprocess
import urllib.request
import pytest

from project_sentinel.verification.gateway_client import GATEWAY_ORIGIN

# Repository root is the parent of the tests/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
KNOWLEDGE_DIR = REPO_ROOT / "data" / "knowledge-base"
SCHEMAS_DIR = REPO_ROOT / "schemas"


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

    try:
        req = urllib.request.Request(
            f"{GATEWAY_ORIGIN}/WebGoat/actuator/health",
            headers={"X-Sentinel-API-Key": api_key},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status != 200:
                pytest.fail(f"Gateway returned HTTP {resp.status} on health check. Run `make gateway-up`.")
    except Exception as e:
        pytest.fail(
            f"Gateway is unreachable at {GATEWAY_ORIGIN}: {e}. "
            "Start containers with `make gateway-up`."
        )

    return api_key


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
    return api_key


@pytest.fixture
def gateway_access_log_tracker():
    def get_log_count() -> int:
        try:
            res = subprocess.run(
                ["docker", "compose", "logs", "--no-log-prefix", "gateway"],
                check=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return len([l for l in res.stdout.splitlines() if "method=" in l or "/WebGoat" in l])
        except Exception as exc:
            pytest.fail(f"Failed to read Gateway access logs from docker compose: {exc}")
    return get_log_count
