"""Sổ sự kiện guardrail — bằng chứng chấm điểm và nguồn cho màn hình web."""

import json

import pytest

from project_sentinel.guardrails.events import (
    EVENT_KINDS,
    append_event,
    count_by_kind,
    read_events,
)


def test_four_event_kinds_are_defined():
    assert EVENT_KINDS == {"redaction", "injection", "approval", "allowlist_block"}


def test_append_writes_one_json_line(tmp_path):
    path = tmp_path / "events.jsonl"
    append_event(str(path), run_id="run-1", kind="injection", detail={"pattern": "ignore_previous"})
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_id"] == "run-1"
    assert record["kind"] == "injection"
    assert record["detail"]["pattern"] == "ignore_previous"
    assert "ts" in record


def test_appending_twice_keeps_both_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    append_event(str(path), run_id="run-1", kind="approval", detail={"approved": True})
    append_event(str(path), run_id="run-1", kind="approval", detail={"approved": False})
    assert len(read_events(str(path))) == 2


def test_unknown_kind_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        append_event(str(tmp_path / "e.jsonl"), run_id="r", kind="bia_dat", detail={})


def test_detail_is_redacted_before_writing(tmp_path):
    path = tmp_path / "events.jsonl"
    append_event(
        str(path),
        run_id="run-1",
        kind="redaction",
        detail={"sample": "nguyen.van.a@example.com"},
    )
    assert "nguyen.van.a@example.com" not in path.read_text(encoding="utf-8")


def test_run_id_survives_redaction(tmp_path):
    path = tmp_path / "events.jsonl"
    append_event(str(path), run_id="a" * 64, kind="approval", detail={})
    assert read_events(str(path))[0]["run_id"] == "a" * 64


def test_read_events_on_missing_file_returns_empty(tmp_path):
    assert read_events(str(tmp_path / "khong-ton-tai.jsonl")) == []


def test_one_corrupt_line_does_not_break_reading_events(tmp_path):
    path = tmp_path / "events.jsonl"
    valid_events = [
        {"run_id": "run-1", "kind": "approval", "detail": {"approved": True}},
        {"run_id": "run-1", "kind": "injection", "detail": {"pattern": "x"}},
    ]
    path.write_text(
        "\n".join(
            [json.dumps(valid_events[0]), "{ hong", json.dumps(valid_events[1])]
        )
        + "\n",
        encoding="utf-8",
    )

    assert read_events(path) == valid_events


def test_count_by_kind_totals_correctly(tmp_path):
    path = tmp_path / "events.jsonl"
    append_event(str(path), run_id="r", kind="injection", detail={})
    append_event(str(path), run_id="r", kind="injection", detail={})
    append_event(str(path), run_id="r", kind="approval", detail={})
    counts = count_by_kind(read_events(str(path)))
    assert counts == {"injection": 2, "approval": 1}
