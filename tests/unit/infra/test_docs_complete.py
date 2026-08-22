"""Đủ bộ tài liệu đề bài liệt kê ở sản phẩm bàn giao cuối cùng."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("relative", [
    "README.md",
    "docs/architecture.md",
    "docs/target-webgoat.md",
    "docs/product-brief.md",
    "docs/limitations.md",
    "docs/demo-script.md",
    "eval/README.md",
    "exercises/week4-gateway/README.md",
    "reports/week-05/report.md",
    "reports/week-06/report.md",
])
def test_required_document_exists(relative):
    assert (REPO_ROOT / relative).exists(), f"Thiếu tài liệu bắt buộc: {relative}"


def test_product_brief_covers_the_six_required_points():
    text = (REPO_ROOT / "docs" / "product-brief.md").read_text(encoding="utf-8")
    for heading in ("## Vấn đề", "## Người sử dụng", "## Giá trị",
                    "## Phạm vi", "## Hạn chế", "## Hướng phát triển"):
        assert heading in text, f"Bản mô tả sản phẩm thiếu mục {heading}"


def test_readme_has_an_architecture_diagram():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "```mermaid" in text, "README phải có sơ đồ kiến trúc"


def test_readme_documents_the_one_command_run():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "make run" in text
    assert "make web" in text


def test_demo_script_covers_all_seven_required_items():
    text = (REPO_ROOT / "docs" / "demo-script.md").read_text(encoding="utf-8").lower()
    for item in ["quét", "báo cáo", "đề xuất", "approve", "reject",
                 "gateway", "injection", "che"]:
        assert item in text, f"Kịch bản demo thiếu hạng mục: {item}"


def test_historical_reports_are_untouched():
    for week in ("01", "02", "03", "04"):
        assert (REPO_ROOT / "reports" / f"week-{week}" / "report.md").exists()


def test_limitations_names_residual_security_risks():
    text = (REPO_ROOT / "docs" / "limitations.md").read_text(encoding="utf-8").lower()
    assert "webgoat" in text
    assert "rủi ro" in text
