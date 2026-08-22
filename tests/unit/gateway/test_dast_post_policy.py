"""Lane DAST cho POST, nhưng ZAP không chọn được gì cả.

ZAP chỉ nêu một path. Nếu path đó có trong allowlist thì lane tự dựng toàn bộ
request: method, header, body đều là hằng số của lane. Đây là quyết định tin
cậy HẸP HƠN lane probe của Agent, nơi caller còn chọn được template.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "infra/docker/gateway/templates/default.conf.template"
ALLOWLIST = REPO_ROOT / "configs/gateway/dast-allowlist.json"


def _dast_server() -> str:
    return TEMPLATE.read_text(encoding="utf-8").split("# DAST boundary", 1)[1]


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _allowlist() -> list[dict]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["endpoints"]


def test_post_is_gated_by_the_canonical_body_map():
    """"Không có body chính tắc" và "không được POST" phải là CÙNG một điều.

    Hai danh sách riêng thì sẽ có ngày quên đồng bộ một bên.
    """
    text = _template_text()
    assert "map $uri $sentinel_dast_post_body" in text
    assert 'map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok' in text
    server = _dast_server()
    assert "$sentinel_dast_method_ok = 0" in server
    assert "return 405" in server


def test_the_method_map_denies_by_default():
    text = _template_text()
    block = text.split('map "$request_method:$sentinel_dast_post_body"', 1)[1]
    block = block.split("}", 1)[0]
    assert "default 0;" in block, "Thiếu default 0 nghĩa là mở mặc định"
    assert '"~^POST:.+"' in block, "POST chỉ hợp lệ khi body chính tắc khác rỗng"


def test_every_allowlisted_path_appears_in_the_nginx_body_map():
    """Hai bên suy ra ĐỘC LẬP, nên phải có test đối chiếu chúng.

    Sinh nginx từ JSON sẽ biến hai lớp kiểm thành một lớp — đó là lý do việc
    đồng bộ được kiểm bằng test chứ không bằng script sinh mã.
    """
    text = _template_text()
    body_map = text.split("map $uri $sentinel_dast_post_body", 1)[1].split("}", 1)[0]
    for entry in _allowlist():
        assert f'"{entry["path"]}"' in body_map, (
            f"{entry['path']} có trong dast-allowlist.json nhưng thiếu trong map nginx"
        )
        assert f'"{entry["canonical_body"]}"' in body_map, (
            f"{entry['path']}: body trong map nginx không khớp canonical_body"
        )


def test_the_nginx_body_map_advertises_nothing_beyond_the_allowlist():
    """Chiều ngược lại: map nginx không được có path mà JSON chưa duyệt."""
    text = _template_text()
    body_map = text.split("map $uri $sentinel_dast_post_body", 1)[1].split("}", 1)[0]
    allowed = {entry["path"] for entry in _allowlist()}
    for line in body_map.splitlines():
        stripped = line.strip()
        if not stripped.startswith('"/WebGoat/'):
            continue
        path = stripped.split('"')[1]
        assert path in allowed, (
            f"{path} có trong map nginx nhưng KHÔNG có trong dast-allowlist.json"
        )


def test_the_lane_dictates_the_body_not_the_caller():
    server = _dast_server()
    assert "proxy_set_body $sentinel_dast_post_body;" in server
    assert "proxy_pass_request_body off;" in server, (
        "Bỏ dòng này là cho ZAP gửi body tới WebGoat"
    )


def test_caller_headers_are_still_stripped():
    assert "proxy_pass_request_headers off;" in _dast_server()


def test_body_size_is_bounded():
    """Lane đọc rồi vứt body của ZAP, nhưng vẫn phải có trần."""
    server = _dast_server()
    assert "client_max_body_size 8k;" in server
