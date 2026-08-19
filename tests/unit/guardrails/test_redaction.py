"""Che dữ liệu nhạy cảm — tiêu chí tuần 5 của đề bài."""

from project_sentinel.guardrails.redaction import (
    RedactionEvent,
    redact,
    redact_structure,
)


def test_email_is_redacted():
    out, events = redact("Lien he nguyen.van.a@example.com de biet them")
    assert "nguyen.van.a@example.com" not in out
    assert "[REDACTED_EMAIL]" in out
    assert RedactionEvent(kind="email", count=1) in events


def test_vietnamese_phone_is_redacted():
    out, _ = redact("Goi 0912345678 hoac +84912345678")
    assert "0912345678" not in out
    assert "[REDACTED_PHONE]" in out


def test_jwt_is_redacted():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.abcDEF-_123"
    out, _ = redact(f"Authorization: Bearer {jwt}")
    assert jwt not in out
    assert "[REDACTED_TOKEN]" in out


def test_openai_style_api_key_is_redacted():
    out, _ = redact("key=sk-abcdefghijklmnopqrstuvwxyz012345")
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in out
    assert "[REDACTED_API_KEY]" in out


def test_long_hex_secret_is_redacted():
    secret = "a" * 64
    out, _ = redact(f"SENTINEL_GATEWAY_API_KEY={secret}")
    assert secret not in out
    assert "[REDACTED_API_KEY]" in out


def test_password_value_is_redacted_but_key_name_survives():
    out, _ = redact('{"password": "SieuBiMat123"}')
    assert "SieuBiMat123" not in out
    assert "password" in out
    assert "[REDACTED_PASSWORD]" in out


def test_password_in_query_string_form_is_redacted():
    out, _ = redact("POST /login password=SieuBiMat123&next=/home")
    assert "SieuBiMat123" not in out


def test_card_number_is_redacted():
    out, _ = redact("The: 4111 1111 1111 1111")
    assert "4111" not in out
    assert "[REDACTED_PII]" in out


def test_cccd_twelve_digits_is_redacted():
    out, _ = redact("CCCD 001234567890 cua khach")
    assert "001234567890" not in out


def test_clean_text_is_returned_unchanged_with_no_events():
    text = "SQL Injection tai src/main/java/Login.java dong 42"
    out, events = redact(text)
    assert out == text
    assert events == []


def test_multiple_occurrences_are_counted():
    out, events = redact("a@x.com va b@y.com va c@z.com")
    email_events = [e for e in events if e.kind == "email"]
    assert email_events[0].count == 3


def test_empty_and_non_string_inputs_are_safe():
    assert redact("") == ("", [])
    assert redact(None)[0] is None


def test_redact_structure_walks_nested_dicts_and_lists():
    payload = {
        "user": {"email": "a@b.com", "note": "binh thuong"},
        "logs": ["lien he c@d.com", "khong co gi"],
    }
    out, events = redact_structure(payload)
    assert out["user"]["email"] == "[REDACTED_EMAIL]"
    assert "c@d.com" not in out["logs"][0]
    assert out["user"]["note"] == "binh thuong"
    assert sum(e.count for e in events if e.kind == "email") == 2


def test_redact_structure_does_not_touch_provenance_fields():
    """Hash provenance là bằng chứng chấm điểm; che nó đi là phá bằng chứng."""
    payload = {"prompt_sha256": "b" * 64, "note": "khoa la " + "c" * 64}
    out, _ = redact_structure(payload)
    assert out["prompt_sha256"] == "b" * 64
    assert "c" * 64 not in out["note"]


def test_redact_structure_preserves_non_string_scalars():
    out, _ = redact_structure({"count": 5, "ok": True, "nothing": None})
    assert out == {"count": 5, "ok": True, "nothing": None}
