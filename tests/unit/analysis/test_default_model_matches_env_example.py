"""Model mặc định trong mã và trong .env.example phải là một.

Nếu hai chỗ lệch nhau, người clone repo và làm đúng theo README sẽ chạy bằng một
model khác model đã sinh ra số liệu trong báo cáo — và không tái lập được kết quả
mà không hiểu vì sao.
"""

import re
from pathlib import Path

from project_sentinel.config import AppConfig

REPO_ROOT = Path(__file__).resolve().parents[3]


def _model_in_env_example() -> str:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"^LLM_MODEL=(.+)$", text, re.MULTILINE)
    assert match, ".env.example không khai LLM_MODEL"
    return match.group(1).strip()


def test_code_default_matches_env_example(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert AppConfig().model_name == _model_in_env_example()


def test_env_example_names_the_model_that_produced_the_reported_numbers():
    summary = REPO_ROOT / "reports/week-06/artifacts/run-approved/analysis-summary.json"
    if not summary.exists():
        return
    import json

    reported = json.loads(summary.read_text(encoding="utf-8"))["model"]
    assert _model_in_env_example() == reported, (
        f".env.example nói {_model_in_env_example()} nhưng evidence pack "
        f"được sinh bởi {reported}"
    )


def test_env_example_holds_no_real_secret():
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("LLM_API_KEY", "SENTINEL_GATEWAY_API_KEY"):
        match = re.search(rf"^{name}=(.*)$", text, re.MULTILINE)
        assert match, f".env.example thiếu {name}"
        assert not match.group(1).strip(), f"{name} trong .env.example phải để trống"
