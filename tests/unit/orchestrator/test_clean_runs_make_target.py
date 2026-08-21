"""Target clean-runs chỉ xoá các run cũ khi người vận hành gọi rõ ràng."""

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = REPO_ROOT / "Makefile"


def test_clean_runs_keeps_the_newest_requested_number(tmp_path):
    runs_dir = tmp_path / "artifacts" / "runs"
    for run_id in (
        "20260821T010000Z",
        "20260821T020000Z",
        "20260821T030000Z",
        "20260821T040000Z",
    ):
        (runs_dir / run_id).mkdir(parents=True)

    environment = os.environ.copy()
    environment["KEEP"] = "2"
    result = subprocess.run(
        ["make", "--file", str(MAKEFILE), "clean-runs"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in runs_dir.iterdir()) == [
        "20260821T030000Z",
        "20260821T040000Z",
    ]
    assert "Giữ lại 2 lần chạy mới nhất." in result.stdout


def test_clean_runs_succeeds_when_no_runs_directory_exists(tmp_path):
    result = subprocess.run(
        ["make", "--file", str(MAKEFILE), "clean-runs"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
