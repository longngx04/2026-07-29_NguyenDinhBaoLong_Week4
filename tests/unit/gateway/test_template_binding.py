"""Payload phải khớp một template đã được review, không chỉ khớp method + path.

`configs/gateway/endpoint-allowlist.json` khai `allowed_template_ids` từ đầu — ví dụ
`/WebGoat/attack` chỉ có `tmpl_attack_get` và `tmpl_attack_post_empty`. Nhưng
`send_probe` gọi `is_allowed(method, path)` với `template_id=None`, và nhánh kiểm
template có điều kiện `if template_id is not None` nên bị bỏ qua hoàn toàn.

Kết quả: hệ thống gửi `special_chars` tới một endpoint mà registry chỉ duyệt payload
rỗng. Safe-payload registry tồn tại nhưng chưa bao giờ được thi hành.
"""

from pathlib import Path

import pytest

from project_sentinel.gateway.allowlist import Allowlist

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


@pytest.fixture(scope="module")
def allowlist():
    return Allowlist.from_json(ALLOWLIST)


def test_every_reviewed_template_declares_method_and_payload(allowlist):
    """Template chỉ là một cái tên nếu nó không nói nó cho phép gửi cái gì."""
    for template_id, spec in allowlist.templates.items():
        assert spec.method in {"GET", "POST"}, template_id
        assert spec.payload_kind is None or isinstance(spec.payload_kind, str)


def test_resolving_a_probe_returns_the_reviewed_template(allowlist):
    assert allowlist.resolve_template("GET", "/WebGoat/login", None) == "tmpl_login_get"


def test_a_payload_kind_with_no_reviewed_template_is_refused(allowlist):
    """Đây là ca thật: special_chars tới /WebGoat/attack chưa từng được duyệt."""
    assert allowlist.resolve_template("POST", "/WebGoat/attack", "special_chars") is None
    assert not allowlist.is_allowed(
        "POST", "/WebGoat/attack", payload_kind="special_chars"
    )


def test_the_reviewed_post_payload_is_still_allowed(allowlist):
    template = allowlist.resolve_template("POST", "/WebGoat/attack", "empty_value")
    assert template == "tmpl_attack_post_empty"
    assert allowlist.is_allowed("POST", "/WebGoat/attack", payload_kind="empty_value")


def test_a_get_is_payload_agnostic_because_it_has_no_body(allowlist):
    """GET không có body, nên `payload_kind` của nó mô tả ý định quan sát.

    Template GET đã review khai `payload_kind: null` đúng vì thế. So khớp cùng một
    cách với POST sẽ làm mọi objective GET bị từ chối, dù chúng không gửi gì cả.

    GET kèm payload_kind VẪN cần người phê duyệt — xem `requires_approval`.
    """
    assert allowlist.is_allowed("GET", "/WebGoat/login", payload_kind="long_string")
    assert (
        allowlist.resolve_template("GET", "/WebGoat/login", "long_string")
        == "tmpl_login_get"
    )


def test_a_post_payload_is_never_payload_agnostic(allowlist):
    """POST CO body, nên payload phải khớp đúng template đã duyệt."""
    assert not allowlist.is_allowed(
        "POST", "/WebGoat/attack", payload_kind="special_chars"
    )
    assert allowlist.is_allowed("POST", "/WebGoat/attack", payload_kind="empty_value")


def test_a_path_with_a_query_string_is_never_allowed(allowlist):
    for path in ("/WebGoat/login?a=1", "/WebGoat/login?", "/WebGoat/attack?x=../.."):
        assert not allowlist.is_allowed("GET", path)


def test_unknown_method_and_path_still_refused(allowlist):
    assert not allowlist.is_allowed("PUT", "/WebGoat/login")
    assert not allowlist.is_allowed("GET", "/WebGoat/admin")


def test_template_ids_declared_on_an_endpoint_all_exist(allowlist):
    """Config không được trỏ tới một template không tồn tại."""
    for rule in allowlist.rules:
        for template_id in rule.allowed_template_ids:
            assert template_id in allowlist.templates, (
                f"{rule.endpoint_id} trỏ tới template không có: {template_id}"
            )
