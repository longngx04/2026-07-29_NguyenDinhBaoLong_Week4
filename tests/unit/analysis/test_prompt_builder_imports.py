"""Import prompt_builder trước bất cứ thứ gì khác không được gây vòng lặp import."""

import subprocess
import sys


def test_prompt_builder_imports_cleanly_on_its_own():
    """Import prompt_builder trước bất cứ thứ gì khác không được gây vòng lặp."""
    for stmt in [
        "import project_sentinel.analysis.prompt_builder",
        "from project_sentinel.analysis.prompt_builder import build_packet_dict",
        "from project_sentinel.llm.base import build_packet_dict",
        "import project_sentinel.llm.openrouter",
    ]:
        r = subprocess.run([sys.executable, "-c", stmt], capture_output=True, text=True, env={"PYTHONPATH": "src"})
        assert r.returncode == 0, f"{stmt} thất bại:\n{r.stderr}"
