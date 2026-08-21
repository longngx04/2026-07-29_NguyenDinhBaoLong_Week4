"""Gateway phải enforce TOÀN BỘ policy, không chỉ key + method + path.

Trước khi sửa, thử với một Gateway key hợp lệ cho kết quả:

    GET /WebGoat/login?evil=1&x=../../etc/passwd  -> 302  (tới được WebGoat)
    GET /WebGoat/login + Cookie/X-Evil            -> 200
    POST /WebGoat/attack + body tự do             -> 302

Nghĩa là ai có Gateway key đều bỏ qua được safe-payload registry. Registry tồn tại
trong config từ đầu (`allowed_template_ids`) nhưng chưa bao giờ được thi hành —
`is_allowed()` nhận `template_id=None` nên nhánh kiểm bị bỏ qua hoàn toàn.

Các test này chạy qua **Nginx thật**, không qua Python, vì đó chính là điều cần
chứng minh: lớp hạ tầng tự nó chặn được, độc lập với mã Python.
"""

import http.client
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from project_sentinel.probe.tool import API_KEY_HEADER, GATEWAY_ORIGIN, TEMPLATE_HEADER

pytestmark = [pytest.mark.integration, pytest.mark.live_gateway]

REPO_ROOT = Path(__file__).resolve().parents[2]


class _StopAtRedirect(urllib.request.HTTPRedirectHandler):
    """Không đi theo redirect: mã trạng thái của *Gateway* mới là thứ cần đo.

    WebGoat trả 302 tới một host chỉ tồn tại bên trong mạng Docker, nên đi theo
    redirect biến một `302 đã qua được Gateway` thành `Connection refused` và
    che mất kết quả thật.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_NO_REDIRECT = urllib.request.build_opener(_StopAtRedirect)


def _status(
    path: str,
    *,
    api_key: str,
    template: str | None = None,
    method: str = "GET",
    data: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
) -> int:
    headers = {API_KEY_HEADER: api_key}
    if template is not None:
        headers[TEMPLATE_HEADER] = template
    headers.update(extra_headers or {})
    request = urllib.request.Request(
        f"{GATEWAY_ORIGIN}{path}", method=method, data=data, headers=headers
    )
    try:
        with _NO_REDIRECT.open(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


# --- các bypass cũ, nay phải bị chặn ---------------------------------------


def test_a_query_string_is_refused_at_the_gateway(gateway_ready):
    """Query string chưa bao giờ nằm trong policy nào."""
    assert (
        _status(
            "/WebGoat/login?evil=1&x=../../etc/passwd",
            api_key=str(gateway_ready),
            template="tmpl_login_get",
        )
        == 400
    )


def test_a_request_without_a_template_is_refused(gateway_ready):
    assert _status("/WebGoat/login", api_key=str(gateway_ready)) == 403


def test_a_template_valid_elsewhere_is_refused_here(gateway_ready):
    """`tmpl_health_get` hợp lệ ở endpoint health, không hợp lệ ở login."""
    assert (
        _status(
            "/WebGoat/login", api_key=str(gateway_ready), template="tmpl_health_get"
        )
        == 403
    )


def test_a_post_body_without_a_reviewed_template_is_refused(gateway_ready):
    assert (
        _status(
            "/WebGoat/attack",
            api_key=str(gateway_ready),
            method="POST",
            data=b'{"tuy":"y"}',
            extra_headers={"Content-Type": "application/json"},
        )
        == 403
    )


def test_an_oversized_body_is_refused(gateway_ready):
    assert (
        _status(
            "/WebGoat/attack",
            api_key=str(gateway_ready),
            template="tmpl_attack_post_empty",
            method="POST",
            data=b"x" * 4000,
            extra_headers={"Content-Type": "application/json"},
        )
        == 413
    )


# --- bypass phát hiện ở vòng review 82/100: template hợp lệ + body tùy ý ---


def test_a_reviewed_template_does_not_licence_an_unreviewed_body(gateway_ready):
    """Đúng request đã được dùng để chứng minh bypass, nay phải bị chặn.

        POST /WebGoat/attack
        X-Sentinel-Template: tmpl_attack_post_empty
        body: {"unreviewed":"benign-canary"}      -> trước: 302 (tới WebGoat)

    `X-Sentinel-Template` là header do caller tự đặt, nên nó không bao giờ là
    bằng chứng rằng body đã qua safe-payload registry.
    """
    assert (
        _status(
            "/WebGoat/attack",
            api_key=str(gateway_ready),
            template="tmpl_attack_post_empty",
            method="POST",
            data=b'{"unreviewed":"benign-canary"}',
            extra_headers={"Content-Type": "application/json"},
        )
        == 403
    )


def test_a_body_of_the_canonical_length_is_still_rewritten(gateway_ready):
    """Cùng độ dài, khác nội dung: kiểm Content-Length một mình KHÔNG đủ.

    `{"evil": "x"}` dài đúng 13 byte như `{"value": ""}`, nên nó qua được
    $sentinel_body_len_ok. Cái chặn nó là `proxy_set_body`: Gateway vứt body của
    caller và dựng lại body chính tắc từ tên template, nên byte chưa được review
    không bao giờ tới WebGoat.

    Bằng chứng byte-level nằm ở
    tests/unit/gateway/test_gateway_config_matches_registry.py — WebGoat không
    có endpoint nào phản chiếu lại body để khẳng định từ ngoài.
    """
    canonical_length = len(b'{"value": ""}')
    forged = b'{"evil": "x"}'
    assert len(forged) == canonical_length

    # 302 là redirect của chính WebGoat: request đã qua được Gateway. Nội dung
    # đi lên upstream là body chính tắc chứ không phải `forged`.
    assert (
        _status(
            "/WebGoat/attack",
            api_key=str(gateway_ready),
            template="tmpl_attack_post_empty",
            method="POST",
            data=forged,
            extra_headers={"Content-Type": "application/json"},
        )
        == 302
    )


def test_a_post_template_cannot_be_used_for_a_get(gateway_ready):
    """`tmpl_attack_post_empty` là template POST. GET là tổ hợp chưa review."""
    assert (
        _status(
            "/WebGoat/attack",
            api_key=str(gateway_ready),
            template="tmpl_attack_post_empty",
            method="GET",
        )
        == 403
    )


def test_a_template_without_a_payload_cannot_carry_a_body(gateway_ready):
    """`tmpl_login_get` khai `payload_kind: null` — nó không được gửi gì cả."""
    assert (
        _status(
            "/WebGoat/login",
            api_key=str(gateway_ready),
            template="tmpl_login_get",
            method="GET",
            data=b'{"a":1}',
        )
        == 403
    )


def test_a_chunked_body_cannot_skip_the_length_check(gateway_ready):
    """Chunked không có Content-Length, nên nó đi vòng được map độ dài."""
    connection = http.client.HTTPConnection("127.0.0.1", 9080, timeout=10)
    try:
        connection.putrequest(
            "POST", "/WebGoat/attack", skip_accept_encoding=True, skip_host=True
        )
        connection.putheader("Host", "127.0.0.1:9080")
        connection.putheader(API_KEY_HEADER, str(gateway_ready))
        connection.putheader(TEMPLATE_HEADER, "tmpl_attack_post_empty")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        connection.send(b'1e\r\n{"unreviewed":"benign-canary"}\r\n0\r\n\r\n')
        assert connection.getresponse().status == 400
    finally:
        connection.close()


# --- đường hợp lệ vẫn phải chạy --------------------------------------------


def test_the_reviewed_path_still_works(gateway_ready):
    assert (
        _status(
            "/WebGoat/login", api_key=str(gateway_ready), template="tmpl_login_get"
        )
        == 200
    )


# --- các chặn cũ vẫn phải còn ----------------------------------------------


def test_a_missing_key_is_still_refused_first(gateway_ready):
    request = urllib.request.Request(f"{GATEWAY_ORIGIN}/WebGoat/login")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == 401


def test_an_unlisted_path_is_still_refused(gateway_ready):
    assert (
        _status(
            "/WebGoat/admin", api_key=str(gateway_ready), template="tmpl_login_get"
        )
        == 403
    )


def test_an_unlisted_method_is_still_refused(gateway_ready):
    assert (
        _status(
            "/WebGoat/login",
            api_key=str(gateway_ready),
            template="tmpl_login_get",
            method="PUT",
        )
        == 405
    )


# --- config Python và Nginx phải nói cùng một chính sách -------------------


def test_python_and_nginx_agree_on_the_reviewed_templates():
    """Hai lớp phải liệt kê CÙNG tập template, nếu không chúng không còn là hai
    lần kiểm cùng một chính sách."""
    import json
    import re

    config = json.loads(
        (REPO_ROOT / "configs/gateway/endpoint-allowlist.json").read_text(
            encoding="utf-8"
        )
    )
    python_templates = {t["template_id"] for t in config["templates"]}
    nginx = (
        REPO_ROOT / "infra/docker/gateway/templates/default.conf.template"
    ).read_text(encoding="utf-8")
    nginx_templates = set(re.findall(r'"(tmpl_[a-z0-9_]+)"\s+1;', nginx))
    assert python_templates == nginx_templates, (
        f"Chỉ Python biết: {python_templates - nginx_templates}; "
        f"chỉ Nginx biết: {nginx_templates - python_templates}"
    )
