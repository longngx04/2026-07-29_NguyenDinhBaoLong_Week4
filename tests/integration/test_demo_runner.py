"""Demo phải chạy được thật, không chỉ import được.

Cần Gateway và WebGoat thật, đúng như mọi test khác của repo: thiếu hạ tầng
thì fail chứ không skip.
"""

import os

import pytest

from project_sentinel.demo.runner import run_demo

pytestmark = pytest.mark.live_gateway


def test_demo_auto_mode_passes_every_step():
    assert os.environ.get("SENTINEL_GATEWAY_API_KEY"), "Cần SENTINEL_GATEWAY_API_KEY"

    captured: list[str] = []
    exit_code = run_demo(auto=True, out=captured.append)
    transcript = "\n".join(captured)

    assert exit_code == 0, transcript
    assert "0 không đạt" in transcript
    assert "[KHÔNG ĐẠT]" not in transcript


def test_demo_never_prints_the_gateway_api_key():
    api_key = os.environ.get("SENTINEL_GATEWAY_API_KEY", "")
    assert api_key, "Cần SENTINEL_GATEWAY_API_KEY"

    captured: list[str] = []
    run_demo(auto=True, out=captured.append)

    assert api_key not in "\n".join(captured)
