"""Gateway giữ session DAST — ZAP không bao giờ thấy credential.

Lane DAST chặn đăng nhập bằng hai cơ chế (405 cho POST, xoá header của
caller). Thay vì nới chúng, Gateway tự lấy session và tự gắn cookie. Các
test dưới đây khoá đúng ranh giới đó.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY = REPO_ROOT / "infra/docker/gateway"
TEMPLATE = GATEWAY / "templates/default.conf.template"
SESSION_SCRIPT = GATEWAY / "docker-entrypoint.d/16-acquire-dast-session.envsh"
DOCKERFILE = GATEWAY / "Dockerfile"
LIMITS = GATEWAY / "nginx.conf"


def _dast_server() -> str:
    return TEMPLATE.read_text(encoding="utf-8").split("# DAST boundary", 1)[1]


def test_session_script_is_envsh_because_sh_cannot_export():
    # /docker-entrypoint.sh cua nginx SOURCE file .envsh va CHAY file .sh.
    # Dat sai duoi thi export khong toi duoc 20-envsubst-on-templates.sh va
    # cookie se rong — crawl chay an danh nhung van "thanh cong".
    assert SESSION_SCRIPT.suffix == ".envsh"
    assert SESSION_SCRIPT.exists()


def test_session_script_runs_after_local_resolvers_and_before_envsubst():
    prefix = int(SESSION_SCRIPT.name.split("-", 1)[0])
    assert 15 < prefix < 20, f"Thu tu {prefix} phai nam giua 15 va 20"


def test_dockerfile_makes_the_session_script_executable():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "16-acquire-dast-session.envsh" in text
    assert "chmod 0755" in text, "nginx bo qua file .envsh khong co exec bit"


def test_session_script_only_runs_in_dast_mode():
    text = SESSION_SCRIPT.read_text(encoding="utf-8")
    assert "SENTINEL_GATEWAY_MODE" in text
    assert "dast" in text


def test_session_script_fails_loudly_when_it_cannot_authenticate():
    text = SESSION_SCRIPT.read_text(encoding="utf-8")
    assert "exit 1" in text, (
        "Gateway DAST khong session se crawl an danh va van ra report — "
        "kieu hong te nhat vi no trong giong thanh cong"
    )


def test_gateway_injects_the_cookie_itself():
    server = _dast_server()
    assert 'proxy_set_header Cookie "JSESSIONID=${SENTINEL_DAST_SESSION}";' in server


def test_caller_headers_are_still_stripped():
    # Bat bien cu khong duoc mat: ZAP van khong gui duoc header nao qua.
    server = _dast_server()
    assert "proxy_pass_request_headers off;" in server


def test_logout_is_blocked_at_the_gateway():
    server = _dast_server()
    assert "location ^~ /WebGoat/logout" in server
    logout = server.split("location ^~ /WebGoat/logout", 1)[1][:120]
    assert "return 403" in logout
    assert "proxy_pass" not in logout


def test_logout_block_is_declared_before_the_general_webgoat_location():
    server = _dast_server()
    assert server.index("location ^~ /WebGoat/logout") < server.index(
        "location ^~ /WebGoat/ "
    ), "Nginx chon prefix dai nhat, nhung dat truoc cho nguoi doc thay ro y dinh"


def test_dast_log_format_records_the_query_string():
    text = LIMITS.read_text(encoding="utf-8")
    dast_format = text.split("log_format sentinel_dast_access", 1)[1]
    assert "query=$args" in dast_format, (
        "path=$uri khong mang query; ban do endpoint can ten tham so"
    )
    assert dast_format.index("path=$uri") < dast_format.index("query=$args"), (
        "test_gateway_log_proves_zap_requests_crossed_the_boundary parse "
        "`path=([^ ]+) ` nen field moi phai dat SAU path"
    )
