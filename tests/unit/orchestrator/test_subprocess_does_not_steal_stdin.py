"""Lệnh ngoài không được chạm vào stdin của người vận hành.

Cổng phê duyệt đọc câu trả lời từ stdin. Bước scan và normalize chạy lệnh ngoài
bằng `subprocess.run`. Nếu tiến trình con kế thừa stdin, nó có thể đọc hết —
và tới lúc cổng phê duyệt hỏi thì chỉ còn EOF, bị diễn giải thành TỪ CHỐI.

Đây không phải giả thuyết: chạy `printf 'approve\\n' | cli run` cho ra
"KHÔNG ĐỌC ĐƯỢC CÂU TRẢ LỜI — coi như TỪ CHỐI" ở cả hai lần thử. Mặc định
fail-safe che mất lỗi, nên nó vẫn an toàn nhưng đường phê duyệt của người thật
không dùng được.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from project_sentinel.orchestrator.steps.common import StepFailure, _run_command


def test_child_process_cannot_read_the_operator_stdin(tmp_path):
    """Chạy `_run_command` với một lệnh cố tình đọc stdin: nó phải nhận EOF ngay."""
    marker = tmp_path / "child-saw.txt"
    program = (
        "import sys, pathlib;"
        f"pathlib.Path({str(marker)!r}).write_text(sys.stdin.read(), encoding='utf-8')"
    )
    _run_command(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        step="thu-nghiem",
        root=tmp_path,
    )
    assert marker.read_text(encoding="utf-8") == "", (
        "Tiến trình con đọc được stdin — nó sẽ nuốt câu trả lời phê duyệt"
    )


def test_the_operator_answer_survives_an_external_command():
    """Chạy that: mot lenh ngoai roi mot lan input(), voi stdin la ong dan."""
    program = f'''
import sys
sys.path.insert(0, {str(Path("src").resolve())!r})
from pathlib import Path
from project_sentinel.orchestrator.steps.common import _run_command
import tempfile
tmp = Path(tempfile.mkdtemp())
_run_command(
    [sys.executable, "-c", "import sys; sys.stdin.read()"],
    cwd=tmp, step="scan", root=tmp,
)
try:
    print("DOC DUOC:" + input())
except EOFError:
    print("EOF")
'''
    result = subprocess.run(
        [sys.executable, "-c", program],
        input="approve\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "DOC DUOC:approve" in result.stdout, (
        f"Câu trả lời của người vận hành bị nuốt. stdout={result.stdout!r} "
        f"stderr={result.stderr[-400:]!r}"
    )


def test_run_command_still_reports_a_failing_command(tmp_path):
    """Chuyển hướng stdin không được làm mất khả năng báo lỗi."""
    with pytest.raises(StepFailure, match="thất bại"):
        _run_command(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            cwd=tmp_path,
            step="thu-nghiem",
            root=tmp_path,
        )
