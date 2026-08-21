"""Một hàm cho mỗi lệnh con của CLI.

Trước đây cả bảy lệnh nằm trong một `main()` dài 260 dòng. Vì chúng dùng chung
một phạm vi biến, một nhánh có thể đọc phải biến của nhánh khác — mypy đã báo
đúng chuyện này (`Name "decision" already defined`), và cùng dạng lỗi đó đã xảy
ra thật trong `send_probe`.

Mỗi handler nhận `args` đã parse và trả về exit code. `main()` chỉ còn dựng
parser rồi điều phối.
"""

from project_sentinel.commands.analyze import cmd_analyze
from project_sentinel.commands.approve import cmd_approve
from project_sentinel.commands.demo import cmd_demo
from project_sentinel.commands.probe import cmd_probe
from project_sentinel.commands.run import cmd_run
from project_sentinel.commands.runs import cmd_runs
from project_sentinel.commands.validate import cmd_validate

__all__ = [
    "cmd_analyze",
    "cmd_approve",
    "cmd_demo",
    "cmd_probe",
    "cmd_run",
    "cmd_runs",
    "cmd_validate",
]
