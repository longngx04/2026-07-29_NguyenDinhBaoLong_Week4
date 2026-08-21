"""Bộ nhãn không bao giờ được nằm trong phạm vi Agent quét được.

README gốc của mentor cảnh báo: chép bộ nhãn vào repo bị quét là phá bỏ tính chất
blind-scan — Agent sẽ "tìm ra" lỗ hổng bằng cách đọc đáp án.

Cảnh báo đó vẫn đúng ở đây, nên có test canh. Scanner chỉ quét
`benchmarks/targets/webgoat` và lọc kết quả theo đúng tiền tố đó.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = REPO_ROOT / "scripts" / "scan-opengrep.sh"
GROUND_TRUTH_DIR = REPO_ROOT / "eval" / "ground-truth"
TARGET = REPO_ROOT / "benchmarks" / "targets" / "webgoat"


def test_the_scan_script_targets_only_the_webgoat_submodule():
    text = SCAN_SCRIPT.read_text(encoding="utf-8")
    assert "benchmarks/targets/webgoat" in text
    assert "eval" not in re.sub(r"#.*", "", text), (
        "Script quét nhắc tới eval/ — bộ nhãn có thể lọt vào phạm vi quét"
    )


def test_ground_truth_lives_outside_the_scanned_tree():
    scanned = TARGET.resolve()
    for path in GROUND_TRUTH_DIR.rglob("*"):
        if not path.is_file():
            continue
        assert scanned not in path.resolve().parents, (
            f"{path} nằm trong cây bị quét — phá bỏ tính chất blind-scan"
        )


def test_no_ground_truth_file_was_copied_into_the_target():
    """Không file nào mang tên gợi đáp án được nằm trong submodule đích."""
    if not TARGET.exists():
        return
    suspicious = [
        p.relative_to(TARGET).as_posix()
        for p in TARGET.rglob("*")
        if p.is_file()
        and re.search(r"(?i)(ground.?truth|answer.?key|solutions?\.json)", p.name)
    ]
    assert not suspicious, f"File giống đáp án nằm trong cây bị quét: {suspicious}"


def test_the_scan_output_filter_pins_the_target_prefix():
    """Kể cả nếu ai đó mở rộng phạm vi quét, bộ lọc output vẫn phải ghim tiền tố."""
    text = SCAN_SCRIPT.read_text(encoding="utf-8")
    assert 'startswith("benchmarks/targets/webgoat/")' in text
