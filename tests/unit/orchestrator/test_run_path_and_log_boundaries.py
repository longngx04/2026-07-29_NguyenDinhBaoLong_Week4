"""Hai biên đầu vào của orchestrator: nhật ký lần chạy, và đường dẫn lần chạy.

`read_log()` nhận bừa mọi thứ `json.loads` trả về. `json.loads("42")` thành công,
rồi `collect_metrics` gọi `.get()` trên một int và bước finalize sập — ở một chỗ
cách xa nguyên nhân.

`list_runs()`/`load_run()` đi theo symlink. `_confine_path()` tồn tại trong CLI
nhưng không được dùng ở đây, nên một symlink trong `runs/` đọc được file bất kỳ
mà tiến trình có quyền.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.metrics import collect_metrics
from project_sentinel.orchestrator.run_log import read_log
from project_sentinel.orchestrator.state import list_runs, load_run, new_run
from project_sentinel.orchestrator.steps import step_finalize

NON_OBJECTS = ["42", "[1, 2]", '"chuoi"', "null", "true"]


@pytest.fixture
def ctx(tmp_path):
    real_root = Path(__file__).resolve().parents[3]
    return RunContext.default(repo_root=real_root).replace(runs_dir=tmp_path / "runs")


# --- nhật ký ----------------------------------------------------------------


def test_read_log_drops_syntactically_valid_non_objects(tmp_path):
    (tmp_path / "run.log.jsonl").write_text(
        "\n".join(NON_OBJECTS)
        + "\n"
        + json.dumps({"ts": "t", "step": "scan", "level": "error", "message": "x"})
        + "\n",
        encoding="utf-8",
    )
    entries = read_log(tmp_path)
    assert len(entries) == 1
    assert all(isinstance(entry, dict) for entry in entries)


def test_finalize_survives_a_log_full_of_scalars(ctx):
    """Đây là chỗ lỗi cũ nổ: `.get()` trên một int, ở bước gần cuối."""
    record = new_run(ctx.runs_dir)
    (record.root / "run.log.jsonl").write_text(
        "\n".join(NON_OBJECTS) + "\n", encoding="utf-8"
    )
    record = step_finalize(record, ctx)
    assert (record.root / "metrics.json").exists()
    assert collect_metrics(record)["errors"]["total"] == 0


# --- đường dẫn lần chạy ------------------------------------------------------


def test_a_symlinked_run_directory_is_not_followed(ctx, tmp_path):
    """Symlink trong runs/ không được biến thành một lần chạy đọc được."""
    outside = tmp_path / "ngoai-pham-vi"
    outside.mkdir()
    (outside / "state.json").write_text(
        json.dumps({"run_id": "gia-mao", "state": "DONE", "steps": []}),
        encoding="utf-8",
    )
    ctx.runs_dir.mkdir(parents=True, exist_ok=True)
    (ctx.runs_dir / "20260101T000000Z").symlink_to(outside, target_is_directory=True)

    assert "20260101T000000Z" not in list_runs(ctx.runs_dir)
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        load_run(ctx.runs_dir, "20260101T000000Z")


def test_a_run_id_escaping_the_runs_directory_is_refused(ctx):
    ctx.runs_dir.mkdir(parents=True, exist_ok=True)
    for run_id in ("../../etc", "..", "/etc", "a/../../b"):
        with pytest.raises((ValueError, FileNotFoundError, OSError)):
            load_run(ctx.runs_dir, run_id)


def test_a_real_run_still_loads(ctx):
    from project_sentinel.orchestrator.state import save_run

    record = new_run(ctx.runs_dir)
    # `new_run` chua ghi state.json; lan chay chi "ton tai" sau khi duoc luu.
    save_run(record)
    assert record.run_id in list_runs(ctx.runs_dir)
    assert load_run(ctx.runs_dir, record.run_id).run_id == record.run_id
