"""Khoá các bất biến mạng và bố cục của Docker Compose."""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_scan_compose_file_is_merged_away():
    assert not (REPO_ROOT / "compose.scan.yml").exists(), (
        "compose.scan.yml phải được gộp vào docker-compose.yml"
    )


def test_all_services_exist(compose):
    assert set(compose["services"]) == {
        "scanner",
        "webgoat",
        "gateway",
        "gateway-dast",
        "zap",
        "web",
    }


def test_service_profiles(compose):
    services = compose["services"]
    assert services["scanner"]["profiles"] == ["scan"]
    assert services["webgoat"]["profiles"] == ["target", "dast"]
    assert services["gateway"]["profiles"] == ["target"]
    assert services["gateway-dast"]["profiles"] == ["dast"]
    assert services["zap"]["profiles"] == ["dast"]
    assert services["web"]["profiles"] == ["app"]


def test_webgoat_is_never_published_on_host(compose):
    assert "ports" not in compose["services"]["webgoat"], (
        "WebGoat là ứng dụng cố ý có lỗ hổng; không bao giờ được mở ra host"
    )


def test_only_gateway_binds_loopback(compose):
    assert compose["services"]["gateway"]["ports"] == ["127.0.0.1:9080:8080"]
    assert "ports" not in compose["services"]["gateway-dast"]
    assert "ports" not in compose["services"]["zap"]


def test_every_host_port_binds_loopback_only(compose):
    for name, service in compose["services"].items():
        for mapping in service.get("ports", []):
            assert str(mapping).startswith("127.0.0.1:"), (
                f"Service {name} bind {mapping} — mapping không có prefix "
                "127.0.0.1: sẽ bind mọi interface theo mặc định của Docker"
            )


def test_no_required_env_var_breaks_scan_profile(compose):
    for name, service in compose["services"].items():
        for entry in service.get("environment", []):
            assert ":?" not in str(entry), (
                f"Service {name} environment {entry} dùng interpolation bắt buộc (:?); "
                "Compose interpolate toàn bộ file trước khi lọc profile, "
                "nên sẽ làm chết make scan khi thiếu key"
            )


GATEWAY_DIR = REPO_ROOT / "infra" / "docker" / "gateway"
REQUIRE_KEY_SCRIPT = GATEWAY_DIR / "docker-entrypoint.d" / "00-require-key.sh"


def test_gateway_image_refuses_empty_api_key():
    dockerfile = (GATEWAY_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "docker-entrypoint.d" in dockerfile, (
        "Dockerfile gateway phải COPY entrypoint guard vào /docker-entrypoint.d/ "
        "để container fail loud khi SENTINEL_GATEWAY_API_KEY rỗng"
    )
    assert REQUIRE_KEY_SCRIPT.exists(), (
        "Thiếu docker-entrypoint.d/00-require-key.sh — key rỗng sẽ làm nginx map "
        "chấp nhận request không header (auth bypass)"
    )
    script = REQUIRE_KEY_SCRIPT.read_text(encoding="utf-8")
    assert "SENTINEL_GATEWAY_API_KEY" in script, (
        "Script guard phải kiểm tra biến SENTINEL_GATEWAY_API_KEY"
    )
    assert "exit 1" in script, (
        "Script guard phải thoát 1 khi key rỗng để container chết hẳn"
    )


def test_web_service_binds_loopback_only(compose):
    assert compose["services"]["web"]["ports"] == ["127.0.0.1:8000:8000"]


def test_web_service_does_not_receive_the_llm_key_by_default(compose):
    environment = compose["services"]["web"].get("environment", [])
    joined = " ".join(str(item) for item in environment)
    assert "LLM_API_KEY=sk-" not in joined, "Không hard-code khoá vào compose"


def test_zap_targets_the_dast_gateway_not_webgoat(compose):
    zap = compose["services"]["zap"]
    assert "gateway-dast" in zap["depends_on"]
    assert "webgoat" not in zap["depends_on"]
    environment = "\n".join(str(item) for item in zap["environment"])
    assert "ZAP_AUTH_HEADER=X-Sentinel-DAST-Key" in environment
    assert "ZAP_AUTH_HEADER_VALUE=" in environment


def test_zap_image_is_version_pinned(compose):
    image = compose["services"]["zap"]["image"]
    assert image.startswith("ghcr.io/zaproxy/zaproxy@sha256:")
    assert len(image.rsplit(":", 1)[1]) == 64


def test_dast_gateway_is_internal_and_readiness_uses_its_key(compose):
    gateway = compose["services"]["gateway-dast"]
    assert gateway["expose"] == ["8081"]
    assert "ports" not in gateway
    health = " ".join(str(item) for item in gateway["healthcheck"]["test"])
    assert "X-Sentinel-DAST-Key" in health
    assert "127.0.0.1:8081/WebGoat/actuator/health" in health
    assert "localhost:8081" not in health, "BusyBox resolves localhost to ::1"
