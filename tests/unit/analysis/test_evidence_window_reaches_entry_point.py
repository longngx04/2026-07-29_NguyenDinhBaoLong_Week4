"""Cửa sổ bằng chứng phải với tới nơi khai báo đường vào.

Trong lần chạy thật với prompt mới, Agent trả `attacker_control: not_proven` cho
12/12 finding mà bộ nhãn ghi là `proven` — kể cả ca hiển nhiên nhất, nơi TOÀN BỘ
câu truy vấn chính là tham số request. Agent viết: "không có bằng chứng trực tiếp
cho thấy tham số query đến từ người dùng".

Nó không sai. Với `radius=4`, cửa sổ quanh sink dòng 49 là dòng 45–53, còn
`@PostMapping` và `@RequestParam` nằm ở dòng 40–43 — vừa lọt ra ngoài. Agent bị
bỏ đói bằng chứng rồi bị chấm là thiếu tự tin.
"""

from pathlib import Path

import pytest

from project_sentinel.analysis.evidence import extract_source_window
from project_sentinel.config import AppConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
WEBGOAT = REPO_ROOT / "benchmarks/targets/webgoat"
# Duong dan y NHU normalizer ghi vao findings.json: tuong doi voi repo root,
# khong phai voi target_root. Truyen sai thi extract_source_window tra loi
# "outside target_root boundary" va Agent nhan duoc 0 bang chung.
LESSON2 = (
    "benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/"
    "sqlinjection/introduction/SqlInjectionLesson2.java"
)


@pytest.mark.skipif(
    not (REPO_ROOT / LESSON2).exists(),
    reason="Submodule WebGoat chưa được init — không thể kiểm chứng trên source thật",
)
def test_window_reaches_the_request_mapping_above_the_sink():
    """Sink ở dòng 49; @PostMapping ở dòng 40. Cửa sổ phải với tới."""
    config = AppConfig()
    evidence = extract_source_window(
        project_root=config.project_root,
        target_root=config.target_root,
        relative_path=LESSON2,
        line=49,
        radius=config.source_radius,
    )
    assert evidence.error is None, evidence.error
    assert "@PostMapping" in evidence.content, (
        f"Cửa sổ {evidence.start_line}–{evidence.end_line} không chứa đường vào; "
        "Agent sẽ không chứng minh được attacker control."
    )
    assert "@RequestParam" in evidence.content


def test_default_radius_is_wide_enough_for_an_annotated_java_handler():
    """Java đặt annotation phía trên chữ ký hàm, nên bán kính rất hẹp luôn hụt.

    Đo trên 23 finding thật: radius=4 với tới 0/13, radius=20 với tới 10/13,
    radius=28 với tới 12/13 rồi bão hoà.
    """
    assert AppConfig().source_radius >= 20
