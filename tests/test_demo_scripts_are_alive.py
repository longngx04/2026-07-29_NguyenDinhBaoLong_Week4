"""Script demo là deliverable — nó phải còn chạy được.

`scripts/demo-week4.sh` gọi `project_sentinel.verification` (package đã bị xoá khi
kiến trúc chuyển sang `probe/`) và tham số CLI `probe --objective-id` (không còn).
Nó im lặng đỏ 5/14 mục trong khi báo cáo Tuần 4 vẫn công bố 14/14 pass.

Không ai phát hiện ra vì không có gì chạy nó. Các test dưới đây là thứ đáng ra
phải có từ đầu — chúng không cần Docker, nên chạy trong suite offline.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL_SCRIPTS = sorted(REPO_ROOT.glob("scripts/*.sh"))
DEMO_HELPERS = sorted((REPO_ROOT / "scripts" / "demo").glob("*.py"))

# Package da bi xoa. Bat cu tham chieu nao toi chung deu la code chet.
REMOVED_MODULES = ("project_sentinel.verification", "configs/verification/")


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_shell_script_has_valid_syntax(script):
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_shell_script_does_not_mention_removed_modules(script):
    text = script.read_text(encoding="utf-8")
    found = [name for name in REMOVED_MODULES if name in text]
    assert not found, f"{script.name} còn trỏ tới thứ đã bị xoá: {found}"


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_every_repo_path_a_script_names_still_exists(script):
    """Script liệt kê đường dẫn cho người đọc. Đường dẫn sai là tài liệu sai."""
    text = script.read_text(encoding="utf-8")
    missing = []
    for candidate in re.findall(
        r"\b(?:src|tests|configs|infra|scripts|eval)/[\w./-]+", text
    ):
        cleaned = candidate.rstrip(".,;:")
        if not (REPO_ROOT / cleaned).exists():
            missing.append(cleaned)
    assert not missing, f"{script.name} nhắc tới đường dẫn không tồn tại: {sorted(set(missing))}"


@pytest.mark.parametrize("helper", DEMO_HELPERS, ids=lambda p: p.name)
def test_demo_helper_parses(helper):
    ast.parse(helper.read_text(encoding="utf-8"))


@pytest.mark.parametrize("helper", DEMO_HELPERS, ids=lambda p: p.name)
def test_demo_helper_imports_cleanly(helper):
    """Import được nghĩa là mọi module nó dùng còn tồn tại."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util,sys;"
            f"spec=importlib.util.spec_from_file_location('h',{str(helper)!r});"
            f"m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr[-600:]


def test_the_agent_proposal_demo_still_blocks_what_it_claims():
    """Chạy thật helper 6b: nó không cần Docker và phải trả về 0."""
    result = subprocess.run(
        [sys.executable, "scripts/demo/agent_proposal_denied.py"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "bi chan dung" in result.stdout
