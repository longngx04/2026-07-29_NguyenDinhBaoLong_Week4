"""Trạng thái một lần chạy nằm trên đĩa, không nằm trong bộ nhớ tiến trình."""

import json

import pytest

from project_sentinel.orchestrator.state import (
    STEP_NAMES,
    RunState,
    list_runs,
    load_run,
    new_run,
    save_run,
)


def test_nine_steps_in_order():
    assert STEP_NAMES == (
        "scan", "normalize", "analyze", "propose",
        "approval", "probe", "scrub", "report", "finalize",
    )


def test_new_run_starts_idle_with_nine_pending_steps(tmp_path):
    record = new_run(tmp_path)
    assert record.state is RunState.IDLE
    assert len(record.steps) == 9
    assert all(step.status == "pending" for step in record.steps)


def test_run_id_is_a_utc_timestamp(tmp_path):
    record = new_run(tmp_path)
    assert len(record.run_id) == 16
    assert record.run_id.endswith("Z")
    assert record.run_id[8] == "T"


def test_run_root_is_a_directory_under_runs_dir(tmp_path):
    record = new_run(tmp_path)
    assert record.root == tmp_path / record.run_id
    assert record.root.is_dir()


def test_save_then_load_round_trips(tmp_path):
    record = new_run(tmp_path)
    record.state = RunState.ANALYZING
    record.mark_step("scan", "done", detail={"findings": 12})
    save_run(record)

    # Thêm trường tương lai để xác nhận from_dict bỏ qua trường lạ
    raw = json.loads((record.root / "state.json").read_text(encoding="utf-8"))
    raw["steps"][0]["future_field_v2"] = "extra_data"
    (record.root / "state.json").write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_run(tmp_path, record.run_id)
    assert loaded.state is RunState.ANALYZING
    assert loaded.step("scan").status == "done"
    assert loaded.step("scan").detail == {"findings": 12}



def test_state_json_is_written_where_the_web_can_read_it(tmp_path):
    record = new_run(tmp_path)
    save_run(record)
    data = json.loads((record.root / "state.json").read_text(encoding="utf-8"))
    assert data["run_id"] == record.run_id
    assert data["state"] == "IDLE"


def test_mark_step_running_sets_started_at(tmp_path):
    record = new_run(tmp_path)
    record.mark_step("scan", "running")
    assert record.step("scan").started_at is not None
    assert record.step("scan").finished_at is None


def test_mark_step_done_sets_elapsed(tmp_path):
    record = new_run(tmp_path)
    record.mark_step("scan", "running")
    record.mark_step("scan", "done")
    step = record.step("scan")
    assert step.finished_at is not None
    assert step.elapsed_ms >= 0.0


def test_mark_step_updates_the_run_timestamp(tmp_path):
    record = new_run(tmp_path)
    before = record.updated_at
    record.mark_step("scan", "running")
    assert record.updated_at >= before


def test_unknown_step_name_is_rejected(tmp_path):
    record = new_run(tmp_path)
    with pytest.raises(KeyError):
        record.mark_step("khong-ton-tai", "done")


def test_unknown_status_is_rejected(tmp_path):
    record = new_run(tmp_path)
    with pytest.raises(ValueError):
        record.mark_step("scan", "bia-dat")


def test_list_runs_returns_newest_first(tmp_path):
    first = new_run(tmp_path)
    save_run(first)
    second = new_run(tmp_path)
    second.run_id = "29991231T235959Z"
    (tmp_path / second.run_id).mkdir(exist_ok=True)
    second.root = tmp_path / second.run_id
    save_run(second)

    ids = list_runs(tmp_path)
    assert ids[0] == "29991231T235959Z"
    assert first.run_id in ids


def test_list_runs_on_missing_directory_returns_empty(tmp_path):
    assert list_runs(tmp_path / "chua-ton-tai") == []


def test_terminal_states_are_recognisable():
    assert RunState.DONE.is_terminal()
    assert RunState.REJECTED.is_terminal()
    assert RunState.FAILED.is_terminal()
    assert not RunState.ANALYZING.is_terminal()
    assert not RunState.AWAITING_APPROVAL.is_terminal()


def test_two_runs_in_the_same_second_do_not_collide(tmp_path):
    """Bấm Chạy hai lần trong một giây không được làm mất lần chạy trước."""
    a = new_run(tmp_path)
    a.mark_step("scan", "done", detail={"findings": 12})
    save_run(a)
    b = new_run(tmp_path)
    save_run(b)
    assert a.run_id != b.run_id
    assert len(list_runs(tmp_path)) == 2
    assert load_run(tmp_path, a.run_id).step("scan").detail == {"findings": 12}


def test_concurrent_reader_never_sees_a_torn_state_file(tmp_path):
    """Web poll state.json trong khi CLI đang ghi — không được đọc phải JSON vỡ."""
    import json
    import threading
    import time
    record = new_run(tmp_path)
    for name in STEP_NAMES:
        record.mark_step(name, "done", detail={"x": "y" * 400})
    save_run(record)
    path = record.root / "state.json"
    errors, stop = [], []

    def writer():
        while not stop:
            save_run(record)

    def reader():
        while not stop:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(repr(exc))

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    time.sleep(1.0)
    stop.append(True)
    for t in threads:
        t.join()
    assert not errors, f"{len(errors)} lần đọc phải file vỡ, ví dụ: {errors[0]}"


def test_list_runs_returns_newest_first_even_within_one_second(tmp_path):
    """Ba lần chạy trong cùng một giây vẫn phải xếp mới nhất trước."""
    first = new_run(tmp_path)
    save_run(first)
    second = new_run(tmp_path)
    save_run(second)
    third = new_run(tmp_path)
    save_run(third)
    assert list_runs(tmp_path) == [third.run_id, second.run_id, first.run_id]




