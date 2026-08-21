"""JSONL hợp lệ về cú pháp vẫn có thể sai về kiểu.

`json.loads("42")`, `json.loads("[1,2]")` và `json.loads("null")` đều thành công.
Nếu reader nhận bừa rồi downstream gọi `.get()`, lần chạy chết ở một chỗ cách xa
nguyên nhân, với một AttributeError không nói được gì cho người vận hành.

Chặn ngay tại biên đọc: chỉ JSON object mới là một bản ghi.
"""

import json

import pytest

from project_sentinel.guardrails.events import count_by_kind, read_events
from project_sentinel.orchestrator.report import _read_jsonl

NON_OBJECT_LINES = ["42", '"chuoi"', "[1, 2, 3]", "null", "true"]


@pytest.mark.parametrize("line", NON_OBJECT_LINES)
def test_read_events_drops_syntactically_valid_non_objects(tmp_path, line):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps({"ts": "t", "run_id": "r", "kind": "redaction", "detail": {}})
        + "\n"
        + line
        + "\n",
        encoding="utf-8",
    )
    events = read_events(path)
    assert len(events) == 1
    assert all(isinstance(event, dict) for event in events)


@pytest.mark.parametrize("line", NON_OBJECT_LINES)
def test_report_reader_drops_syntactically_valid_non_objects(tmp_path, line):
    path = tmp_path / "analysis.jsonl"
    path.write_text(
        json.dumps({"analysis_id": "analysis-a"}) + "\n" + line + "\n",
        encoding="utf-8",
    )
    entries = _read_jsonl(path)
    assert len(entries) == 1
    assert all(isinstance(entry, dict) for entry in entries)


def test_count_by_kind_survives_a_file_full_of_scalars(tmp_path):
    """Đây là chỗ lỗi cũ sẽ nổ: .get() trên một int."""
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(NON_OBJECT_LINES) + "\n", encoding="utf-8")
    assert count_by_kind(read_events(path)) == {}


def test_a_valid_record_after_a_bad_line_is_still_read(tmp_path):
    """Bỏ dòng hỏng, không bỏ phần còn lại của file."""
    path = tmp_path / "events.jsonl"
    path.write_text(
        "[1,2]\n{ hong\n"
        + json.dumps({"ts": "t", "run_id": "r", "kind": "injection", "detail": {}})
        + "\n",
        encoding="utf-8",
    )
    events = read_events(path)
    assert [event["kind"] for event in events] == ["injection"]
