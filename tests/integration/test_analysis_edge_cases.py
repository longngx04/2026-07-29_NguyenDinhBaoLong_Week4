"""Ba tình huống kiểm thử cho Agent, theo đúng tiêu chí tuần 3.

Ba ca này KHÔNG gọi LLM: chúng khẳng định agent thoát êm trước khi tốn token,
nên chạy được trong CI không cần API key.
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis"

pytestmark = pytest.mark.integration


def _run_analyze(input_path: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "project_sentinel.cli", "analyze",
            "--input", str(input_path),
            "--output", str(tmp_path / "analysis.jsonl"),
            "--summary", str(tmp_path / "run-summary.json"),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_empty_input_exits_cleanly_without_inventing_records(tmp_path):
    result = _run_analyze(FIXTURES / "empty-findings.json", tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    output = tmp_path / "analysis.jsonl"
    if output.exists():
        assert output.read_text(encoding="utf-8").strip() == "", (
            "Đầu vào rỗng mà agent vẫn sinh record — đây là bịa đặt"
        )


def test_malformed_input_fails_loudly_and_does_not_crash(tmp_path):
    result = _run_analyze(FIXTURES / "malformed-findings.json", tmp_path)
    assert result.returncode != 0, "JSON hỏng phải làm CLI trả mã lỗi khác 0"

    combined = (result.stdout + result.stderr).lower()
    assert "traceback" not in combined, (
        "Lỗi đầu vào phải được xử lý, không được để traceback lộ ra"
    )
    assert any(word in combined for word in ("json", "invalid", "không hợp lệ")), (
        f"Thông báo lỗi phải nói rõ vấn đề. Nhận được: {combined[:400]}"
    )


def test_missing_input_file_fails_with_clear_message(tmp_path):
    result = _run_analyze(tmp_path / "khong-ton-tai.json", tmp_path)
    assert result.returncode != 0

    combined = (result.stdout + result.stderr).lower()
    assert "traceback" not in combined
    assert any(word in combined for word in ("not found", "no such", "không tìm thấy")), (
        f"Thông báo lỗi phải nói rõ file không tồn tại. Nhận được: {combined[:400]}"
    )


def test_normalized_findings_fixture_is_present_and_non_empty():
    """Tiền điều kiện: artifact chuẩn hoá thật phải có sẵn và không rỗng.

    Ca 'đầu vào bình thường' chạy end-to-end nằm ở
    tests/integration/test_analysis_pipeline.py::test_pipeline_live_valid_findings
    (đánh dấu @pytest.mark.llm vì phải gọi LLM thật).
    """
    normalized = REPO_ROOT / "artifacts" / "normalized" / "findings.json"
    assert normalized.exists(), (
        "Chạy `make normalize` trước. Test này dùng dữ liệu thật, không dùng fixture giả."
    )
    data = json.loads(normalized.read_text(encoding="utf-8"))
    assert isinstance(data.get("findings"), list) and data["findings"], (
        "artifacts/normalized/findings.json phải có ít nhất một finding"
    )
