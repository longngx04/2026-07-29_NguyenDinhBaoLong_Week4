"""Mọi dòng audit đều bị che trước khi chạm đĩa."""

import json

import pytest

from project_sentinel.gateway.request_log import MAX_AUDIT_PREVIEW_BYTES, log_request
from project_sentinel.guardrails.redaction import redact


def _read_one(path) -> dict:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_email_in_response_preview_is_redacted(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    log_request(
        str(log_path),
        method="GET",
        path="/WebGoat/attack",
        response_preview="Xin chao nguyen.van.a@example.com",
    )
    record = _read_one(log_path)
    assert "nguyen.van.a@example.com" not in json.dumps(record)
    assert "[REDACTED_EMAIL]" in record["response_preview"]


def test_api_key_leaked_into_error_reason_is_redacted(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    secret = "b" * 64
    log_request(
        str(log_path),
        method="GET",
        path="/WebGoat/attack",
        error_reason=f"Upstream rejected key {secret}",
    )
    assert secret not in log_path.read_text(encoding="utf-8")


def test_phone_number_in_preview_is_redacted(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    log_request(str(log_path), method="GET", path="/x", response_preview="Goi 0912345678")
    assert "0912345678" not in log_path.read_text(encoding="utf-8")


def test_request_id_provenance_survives_redaction(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    log_request(str(log_path), request_id="req-abcdef123456", method="GET", path="/x")
    assert _read_one(log_path)["request_id"] == "req-abcdef123456"


def test_clean_fields_are_written_unchanged(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    log_request(str(log_path), method="POST", path="/WebGoat/attack", status_code=200)
    record = _read_one(log_path)
    assert record["method"] == "POST"
    assert record["path"] == "/WebGoat/attack"
    assert record["status_code"] == 200


def test_unreviewed_field_names_are_still_rejected(tmp_path):
    """Bộ che không được làm mất lớp kiểm tra tên field đã có."""
    with pytest.raises(ValueError):
        log_request(str(tmp_path / "r.jsonl"), khong_duoc_duyet="x")


# ── Tests cho 3 điểm cải tiến ─────────────────────────────────────────────

def test_preview_stays_within_the_byte_cap_after_redaction(tmp_path):
    """Che làm chuỗi dài ra; bản ghi cuối cùng vẫn phải trong 512 byte."""
    log_path = tmp_path / "r.jsonl"
    preview = " ".join(["a@b.com"] * 60)  # 479 byte trước khi che
    assert len(preview.encode("utf-8")) <= MAX_AUDIT_PREVIEW_BYTES
    log_request(str(log_path), method="GET", path="/x", response_preview=preview)
    rec = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert len(rec["response_preview"].encode("utf-8")) <= MAX_AUDIT_PREVIEW_BYTES


def test_all_audit_provenance_ids_survive_redaction(tmp_path):
    """Cả 6 trường định danh provenance của audit log phải ra file nguyên vẹn."""
    log_path = tmp_path / "r.jsonl"
    log_request(
        str(log_path),
        method="GET",
        path="/x",
        request_id="req-0912345678",
        candidate_id="cand-0912345678",
        objective_id="obj-0912345678",
        proposal_id="prop-0912345678",
        endpoint_id="ep-0912345678",
        template_id="tmpl-0912345678",
    )
    rec = _read_one(log_path)
    assert rec["request_id"] == "req-0912345678"
    assert rec["candidate_id"] == "cand-0912345678"
    assert rec["objective_id"] == "obj-0912345678"
    assert rec["proposal_id"] == "prop-0912345678"
    assert rec["endpoint_id"] == "ep-0912345678"
    assert rec["template_id"] == "tmpl-0912345678"


def test_response_preview_with_phone_number_is_still_redacted(tmp_path):
    """Không nới lỏng quá tay: response_preview chứa số điện thoại vẫn phải bị che."""
    log_path = tmp_path / "r.jsonl"
    log_request(str(log_path), method="GET", path="/x", response_preview="Lien he 0912345678")
    rec = _read_one(log_path)
    assert "0912345678" not in rec["response_preview"]
    assert "[REDACTED_PHONE]" in rec["response_preview"]


def test_key_keyword_needs_a_word_boundary():
    """`key` phải là từ riêng — 'monkey <hex>' không được coi là secret."""
    sha = "5f2e4a9c1b8d7e6f3a2c9b4d8e1f7a3c5b9d2e6f"
    assert redact(f"monkey {sha}")[0] == f"monkey {sha}"
    assert redact(f"commit {sha}")[0] == f"commit {sha}"
    assert "[REDACTED_API_KEY]" in redact(f"rejected key {'b' * 64}")[0]
