"""DAST listener must remain a bounded, internal, read-only Gateway surface."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "infra/docker/gateway/templates/default.conf.template"
ENTRYPOINT = (
    REPO_ROOT
    / "infra/docker/gateway/docker-entrypoint.d/00-require-key.sh"
)


def _dast_server() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    return text.split("# DAST boundary", 1)[1]


def test_dast_listener_has_a_separate_key_and_port():
    text = TEMPLATE.read_text(encoding="utf-8")
    server = _dast_server()
    assert "$sentinel_dast_key_valid" in text
    assert "listen 8081;" in server
    assert "$sentinel_dast_key_valid = 0" in server


def test_dast_listener_only_forwards_read_only_methods():
    server = _dast_server()
    assert "$request_method !~ ^(GET|HEAD)$" in server
    assert "proxy_pass_request_body off;" in server
    assert 'proxy_set_header Content-Length "";' in server
    assert "$content_length" in server
    assert "$http_transfer_encoding" in server


def test_dast_listener_only_proxies_the_webgoat_prefix():
    server = _dast_server()
    assert "location ^~ /WebGoat/" in server
    assert "proxy_pass http://webgoat:8080;" in server
    assert "location /" in server and "return 403;" in server


def test_dast_root_is_a_static_bootstrap_not_an_upstream_proxy():
    server = _dast_server()
    root = server.split("location = /", 1)[1].split("location ^~", 1)[0]
    assert "return 200" in root
    assert "/WebGoat/login" in root
    assert "proxy_pass" not in root


def test_dast_gateway_strips_caller_headers():
    server = _dast_server()
    assert "proxy_pass_request_headers off;" in server
    assert "X-Sentinel-DAST-Key" not in server


def test_dast_mode_fails_loudly_without_a_key():
    script = ENTRYPOINT.read_text(encoding="utf-8")
    assert "SENTINEL_GATEWAY_MODE" in script
    assert "SENTINEL_DAST_API_KEY" in script
    assert "exit 1" in script
