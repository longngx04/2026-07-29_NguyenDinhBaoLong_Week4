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


def test_redact_structure_preserves_non_string_scalars():
    out, _ = redact_structure({"count": 5, "ok": True, "nothing": None})
    assert out == {"count": 5, "ok": True, "nothing": None}


# ── Tests từ commit 99b2f00 (Tuples, Sets, Cycle detection) ────────────────

def test_redact_structure_handles_tuples_and_sets():
    payload = {"t": ("a@b.com", "x"), "s": {"a@b.com"}}
    out, events = redact_structure(payload)
    assert isinstance(out["t"], tuple)
    assert out["t"] == ("[REDACTED_EMAIL]", "x")
    assert isinstance(out["s"], set)
    assert out["s"] == {"[REDACTED_EMAIL]"}
    assert sum(e.count for e in events if e.kind == "email") == 2


def test_redact_structure_handles_self_referential_cycle():
    d = {"name": "test"}
    d["self"] = d
    out, _ = redact_structure(d)
    assert out["name"] == "test"
    assert out["self"] == "[CYCLE]"


# ── Tests cho các trường hợp biên và kiểm chứng lỗi ───────────────────────

def test_git_commit_sha_and_sha256_hashes_are_not_redacted():
    """Hash 40/64 hex trần KHÔNG được che nhầm thành API key."""
    commit_sha = "5f2e4a9c1b8d7e6f3a2c9b4d8e1f7a3c5b9d2e6f"
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    text = f"commit {commit_sha} va sha256:{sha256_hash}"
    out, events = redact(text)
    assert commit_sha in out, "Git commit SHA 40 hex không được bị che"
    assert sha256_hash in out, "SHA256 64 hex không được bị che"
    assert not any(e.kind == "api_key" for e in events)


def test_contextual_hex_secret_is_redacted():
    """Hex secret đi kèm ngữ cảnh bí mật PHẢI được che."""
    for key_name in ["api_key", "secret", "token", "SENTINEL_GATEWAY_API_KEY"]:
        hex_val = "f" * 32
        out, events = redact(f"{key_name}={hex_val}")
        assert hex_val not in out, f"Secret {key_name}={hex_val} phải bị che"
        assert "[REDACTED_API_KEY]" in out


def test_skip_keys_walks_nested_structures():
    """skip_keys chỉ bỏ qua node nếu là scalar, không bỏ qua cả cây con."""
    payload = {
        "request_id": {
            "email": "a@b.com",
            "pw": "sk-abcdefghijklmnopqrstuvwxyz012345",
        }
    }
    out, events = redact_structure(payload)
    assert out["request_id"]["email"] == "[REDACTED_EMAIL]"
    assert out["request_id"]["pw"] == "[REDACTED_API_KEY]"
    assert len(events) >= 2


def test_password_field_name_variants_and_spaced_values():
    """Bắt các biến thể pwd, pass, passwd và giá trị có dấu cách khi dùng =."""
    for variant in ["pwd=SieuBiMat123", "pass: SieuBiMat123", "passwd=SieuBiMat123", "password: SieuBiMat123"]:
        out, _ = redact(variant)
        assert "SieuBiMat123" not in out, f"Biến thể {variant} không che được mật khẩu"
        assert "[REDACTED_PASSWORD]" in out

    # Giá trị có khoảng trắng với dấu =
    spaced = "password = Sieu Bi Mat cua he thong"
    out_spaced, _ = redact(spaced)
    assert "Sieu Bi Mat cua he thong" not in out_spaced
    assert "[REDACTED_PASSWORD]" in out_spaced


def test_password_pattern_does_not_swallow_prose_descriptions():
    """Mẫu password với dấu : không được nuốt trọn câu văn xuôi mô tả."""
    prose = "Reset password: click here to continue"
    out_prose, _ = redact(prose)
    assert "here to continue" in out_prose
    assert out_prose == "Reset password: [REDACTED_PASSWORD] here to continue"

    finding_prose = "Hardcoded password: found in Login.java line 42"
    out_finding, _ = redact(finding_prose)
    assert "in Login.java line 42" in out_finding


def test_vietnamese_phone_formats_with_spaces_and_dashes():
    """Bắt các cách viết số điện thoại có dấu cách, gạch ngang và tiền tố 84."""
    for phone in ["0912 345 678", "+84 912 345 678", "84912345678", "0912-345-678"]:
        out, _ = redact(f"Lien he {phone}")
        assert phone not in out, f"Số điện thoại {phone} không bị che"
        assert "[REDACTED_PHONE]" in out


def test_phone_pattern_does_not_flag_decimals_or_line_numbers():
    """Mẫu phone không được ăn nhầm số thập phân trong log hoặc số dòng trong code."""
    for text in [
        "elapsed_ms 0.123456789",
        "version 0.1.2.3.4.5.6.7.8.9",
        "SQL Injection tai src/main/java/Login.java dong 42",
    ]:
        out, events = redact(text)
        assert out == text, f"Chuỗi {text!r} bị che nhầm thành {out!r}"
        assert not any(e.kind == "phone" for e in events)


def test_dict_keys_are_kept_intact_to_avoid_key_collisions():
    """Che khóa sẽ làm hai khóa khác nhau gộp về cùng một chuỗi và nuốt mất
    một cặp dữ liệu. Khóa của finding là tên trường, không chứa PII."""
    out, _ = redact_structure({"a@b.com": 1, "c@d.com": 2})
    assert len(out) == 2
    assert out == {"a@b.com": 1, "c@d.com": 2}


def test_pii_pattern_does_not_flag_build_ids_or_byte_counts():
    """Mẫu CCCD 12 số bắt đầu bằng 0 không được ăn nhầm build id hay byte count."""
    text = "build 202608190001 va so luong byte: 123456789012"
    out, events = redact(text)
    assert "202608190001" in out
    assert "123456789012" in out
    assert not any(e.kind == "pii" for e in events)


def test_redact_merges_multiple_events_of_same_kind():
    """redact() phải gộp các sự kiện cùng loại thành 1 RedactionEvent duy nhất với count tổng."""
    text = "key=sk-abcdefghijklmnopqrstuvwxyz012345 va api_key=" + "a" * 40
    out, events = redact(text)
    api_key_events = [e for e in events if e.kind == "api_key"]
    assert len(api_key_events) == 1
    assert api_key_events[0].count == 2


def test_very_long_password_value_is_fully_redacted():
    """Mật khẩu dài hơn 64 ký tự không được để sót một mảnh nào."""
    out, _ = redact("password=" + "X" * 100)
    assert "X" not in out
    assert "[REDACTED_PASSWORD]" in out


def test_redacting_twice_does_not_invent_a_second_redaction():
    """Che hai lần là chuyện thật (egress rồi tới log). Lần hai không có gì mới.

    Nếu mẫu bắt lại chính placeholder của mình, số liệu guardrail sẽ báo có
    redaction ở nơi không hề có dữ liệu nhạy cảm nào.
    """
    once, first = redact("password: SieuBiMat123")
    twice, second = redact(once)

    assert once == twice
    assert [(event.kind, event.count) for event in first] == [("password", 1)]
    assert second == [], f"Che lần hai bịa ra sự kiện: {second}"


def test_no_pattern_re_matches_its_own_placeholder():
    """Mọi loại đều phải idempotent về CẢ nội dung LẪN số liệu."""
    samples = [
        'password: SieuBiMat123',
        'pwd=SieuBiMat123',
        'email=nguoi.dung@example.com',
        'api_key: 0123456789abcdef0123456789abcdef',
        'token=eyJhbGciOi.AAAABBBBCCCC.DDDDEEEEFFFF',
        'lien he 0912345678',
    ]
    for sample in samples:
        once, _ = redact(sample)
        twice, second = redact(once)
        assert once == twice, f"Không idempotent: {sample!r}"
        assert second == [], f"{sample!r} sinh sự kiện thừa ở lần hai: {second}"
