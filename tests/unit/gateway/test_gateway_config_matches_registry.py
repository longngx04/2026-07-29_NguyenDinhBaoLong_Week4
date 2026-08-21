"""Config Nginx phải là bản sao trung thực của safe-payload registry Python.

Lớp enforce thứ hai chỉ có giá trị khi nó nói *cùng một* chính sách với lớp thứ
nhất. Nginx không đọc được Python, nên ba `map` trong `default.conf.template`
là chép tay từ `configs/gateway/endpoint-allowlist.json` và
`gateway/payloads.py`. Chép tay thì sẽ lệch — trừ khi có test này.

Sửa một bên mà quên bên kia sẽ làm test này đỏ, chứ không âm thầm mở lại đúng
lỗ hổng "tên template hợp lệ + body tùy ý" mà nó vừa đóng.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.payload_kinds import payload_value_for
from project_sentinel.probe.tool import PAYLOAD_FIELD

REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_TEMPLATE = REPO_ROOT / "infra/docker/gateway/templates/default.conf.template"
ALLOWLIST_JSON = REPO_ROOT / "configs/gateway/endpoint-allowlist.json"


def _map_entries(variable: str) -> dict[str, str]:
    """Đọc các cặp key/value của một khối `map ... $variable { ... }`."""
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")
    match = re.search(
        r"^map\s+\S+\s+%s\s*\{(.*?)^\}" % re.escape(variable),
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Không tìm thấy khối map cho {variable}"

    entries: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("default"):
            continue
        key_match = re.match(r'^"(?P<key>[^"]*)"\s+(?P<value>.*);$', line)
        assert key_match is not None, f"Dòng map không đọc được: {line!r}"
        entries[key_match.group("key")] = key_match.group("value").strip()
    return entries


def _canonical_body(payload_kind: str | None) -> str:
    """Đúng chuỗi mà `send_probe` sẽ đặt vào body cho payload_kind này."""
    if payload_kind is None:
        return ""
    return json.dumps(
        {PAYLOAD_FIELD: payload_value_for(payload_kind)}, ensure_ascii=False
    )


@pytest.fixture(scope="module")
def templates() -> dict[str, object]:
    return Allowlist.from_json(ALLOWLIST_JSON).templates


def test_every_reviewed_template_is_bound_to_its_method_in_nginx(templates):
    """`tmpl_attack_post_empty` dùng cho GET là tổ hợp chưa từng được review."""
    entries = _map_entries("$sentinel_tmpl_method_ok")
    expected = {
        f"{template_id}:{template.method}"  # type: ignore[attr-defined]
        for template_id, template in templates.items()
    }
    assert set(entries) == expected
    assert set(entries.values()) == {"1"}


def test_nginx_accepts_exactly_the_canonical_body_length(templates):
    """Content-Length nào khác body chính tắc đều là body chưa được review."""
    entries = _map_entries("$sentinel_body_len_ok")

    expected: set[str] = set()
    for template_id, template in templates.items():
        kind = template.payload_kind  # type: ignore[attr-defined]
        if kind is None:
            # Không payload thì chỉ được phép không có body: header vắng mặt
            # ($content_length rỗng) hoặc khai báo 0.
            expected.add(f"{template_id}:")
            expected.add(f"{template_id}:0")
        else:
            body = _canonical_body(kind)
            expected.add(f"{template_id}:{len(body.encode('utf-8'))}")

    assert set(entries) == expected
    assert set(entries.values()) == {"1"}


def test_nginx_rebuilds_the_exact_body_python_would_have_sent(templates):
    """Body upstream do Gateway dựng lại, phải khớp từng byte với Python."""
    entries = _map_entries("$sentinel_canonical_body")

    expected = {
        template_id: _canonical_body(template.payload_kind)  # type: ignore[attr-defined]
        for template_id, template in templates.items()
        if template.payload_kind is not None  # type: ignore[attr-defined]
    }
    assert set(entries) == set(expected)
    for template_id, body in expected.items():
        # Nginx bọc giá trị trong nháy đơn; body chính tắc là JSON dùng nháy kép
        # nên không có xung đột trích dẫn nào cần thoát.
        assert entries[template_id] == f"'{body}'"
        assert "'" not in body


def test_the_client_body_never_reaches_upstream():
    """Body cùng độ dài nhưng khác nội dung vẫn không được chuyển tiếp."""
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")
    assert "proxy_set_body $sentinel_canonical_body;" in text


def test_headers_are_allowlisted_not_blocklisted():
    """Xóa vài header cụ thể không phải allowlist: header lạ vẫn đi qua."""
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")
    assert "proxy_pass_request_headers off;" in text


def test_chunked_bodies_cannot_skip_the_length_check():
    """Chunked không có Content-Length nên nó đi vòng được $sentinel_body_len_ok."""
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")
    assert "if ($http_transfer_encoding) { return 400; }" in text


def test_every_location_checks_all_three_policy_maps():
    """Một location quên một check là một đường vòng. Đếm cho chắc."""
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")
    locations = re.findall(
        r"location = (/WebGoat/\S+) \{(.*?)\n    \}", text, re.DOTALL
    )
    assert len(locations) == 3, "Số location proxy đã thay đổi"
    for path, body in locations:
        for check in (
            "$sentinel_key_valid = 0",
            "$args",
            "$sentinel_tmpl_method_ok = 0",
            "$sentinel_body_len_ok = 0",
        ):
            assert check in body, f"{path} thiếu kiểm tra {check}"


def test_the_forced_headers_are_values_the_allowlist_reviewed():
    """Gateway tự đặt Accept/User-Agent, nên giá trị đó phải nằm trong policy.

    Trước đây Nginx chuyển tiếp `$http_accept`/`$http_user_agent` của caller,
    nghĩa là `allowed_request_headers` trong allowlist chưa bao giờ được thi
    hành. Nay Gateway đặt cứng — và giá trị đặt cứng phải là giá trị đã duyệt,
    không phải một giá trị ai đó gõ vào config.
    """
    allowlist = Allowlist.from_json(ALLOWLIST_JSON)
    text = NGINX_TEMPLATE.read_text(encoding="utf-8")

    reviewed_accept: set[str] = set()
    reviewed_agents: set[str] = set()
    for rule in allowlist.rules:
        reviewed_accept.update(rule.allowed_request_headers.get("accept", ()))
        reviewed_agents.update(rule.allowed_request_headers.get("user-agent", ()))

    for value in re.findall(r'proxy_set_header Accept "([^"]+)";', text):
        assert value in reviewed_accept, f"Accept '{value}' chưa được review"

    forced_agents = set(re.findall(r'proxy_set_header User-Agent "([^"]+)";', text))
    assert forced_agents, "Gateway phải đặt User-Agent, không lấy của caller"
    assert forced_agents <= reviewed_agents, (
        f"User-Agent chưa được review: {forced_agents - reviewed_agents}"
    )
