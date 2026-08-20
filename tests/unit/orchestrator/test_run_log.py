"""Nhật ký toàn trình — bước 9 của luồng đề bài."""

import json

import pytest

from project_sentinel.orchestrator.run_log import append_log, read_log


def test_append_writes_one_line_with_required_fields(tmp_path):
    append_log(tmp_path, step="scan", level="info", message="Bat dau quet")
    entries = read_log(tmp_path)
    assert len(entries) == 1
    assert entries[0]["step"] == "scan"
    assert entries[0]["level"] == "info"
    assert entries[0]["message"] == "Bat dau quet"
    assert "ts" in entries[0]


def test_extra_fields_are_kept(tmp_path):
    append_log(tmp_path, step="analyze", level="info", message="xong", groups=7)
    assert read_log(tmp_path)[0]["groups"] == 7


def test_entries_accumulate_in_order(tmp_path):
    append_log(tmp_path, step="scan", level="info", message="mot")
    append_log(tmp_path, step="scan", level="info", message="hai")
    messages = [entry["message"] for entry in read_log(tmp_path)]
    assert messages == ["mot", "hai"]


def test_unknown_level_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        append_log(tmp_path, step="scan", level="tham-hoa", message="x")


def test_sensitive_data_is_redacted_before_writing(tmp_path):
    append_log(
        tmp_path,
        step="probe",
        level="error",
        message="That bai voi key " + "e" * 64,
    )
    assert "e" * 64 not in (tmp_path / "run.log.jsonl").read_text(encoding="utf-8")


def test_email_in_message_is_redacted(tmp_path):
    append_log(
        tmp_path,
        step="scrub",
        level="info",
        message="Tim thay nguyen.van.a@example.com",
    )
    assert "nguyen.van.a@example.com" not in (tmp_path / "run.log.jsonl").read_text(
        encoding="utf-8"
    )


def test_read_log_on_missing_file_returns_empty(tmp_path):
    assert read_log(tmp_path / "chua-ton-tai") == []


def test_error_entries_are_findable(tmp_path):
    append_log(tmp_path, step="analyze", level="error", message="LLM timeout")
    append_log(tmp_path, step="scan", level="info", message="ok")
    errors = [e for e in read_log(tmp_path) if e["level"] == "error"]
    assert len(errors) == 1


def test_sensitive_data_in_extra_fields_is_redacted(tmp_path):
    append_log(
        tmp_path,
        step="analyze",
        level="info",
        message="Finding",
        user_email="admin@example.com",
        nested={"secret": "sk-" + "a" * 48},
    )
    entries = read_log(tmp_path)
    assert len(entries) == 1
    assert "admin@example.com" not in (tmp_path / "run.log.jsonl").read_text(
        encoding="utf-8"
    )
    assert "sk-" + "a" * 48 not in (tmp_path / "run.log.jsonl").read_text(
        encoding="utf-8"
    )


def test_caller_cannot_forge_the_timestamp(tmp_path):
    """ts la bang chung thoi diem ghi — nguoi goi khong duoc dat no."""
    with pytest.raises(ValueError):
        append_log(
            tmp_path,
            step="scan",
            level="info",
            message="x",
            ts="1999-01-01T00:00:00+00:00",
        )


def test_message_is_bounded_after_redaction(tmp_path):
    """Che lam chuoi dai ra; dong ghi ra dia van phai trong gioi han."""
    from project_sentinel.orchestrator.run_log import MAX_MESSAGE_BYTES

    append_log(
        tmp_path,
        step="analyze",
        level="info",
        message=" ".join(["a@b.com"] * 500),
    )
    line = (tmp_path / "run.log.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert len(entry["message"].encode("utf-8")) <= MAX_MESSAGE_BYTES + 16


def test_one_corrupt_line_does_not_break_the_whole_read(tmp_path):
    append_log(tmp_path, step="scan", level="info", message="dong 1")
    with (tmp_path / "run.log.jsonl").open("a", encoding="utf-8") as h:
        h.write("{ dong hong khong phai json\n")
    append_log(tmp_path, step="scan", level="info", message="dong 3")
    messages = [e["message"] for e in read_log(tmp_path)]
    assert messages == ["dong 1", "dong 3"]


def test_non_string_message_is_rejected_clearly(tmp_path):
    """Hàm ghi log không được sập bằng AttributeError khi người gọi đưa sai kiểu."""
    with pytest.raises(ValueError):
        append_log(tmp_path, step="scan", level="info", message=12345)
