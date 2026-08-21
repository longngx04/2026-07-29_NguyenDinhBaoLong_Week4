"""Tài liệu bàn giao phải trỏ tới thứ có thật.

Một README hứa một file không tồn tại, hay một Makefile target đã bị đổi tên, làm
người clone repo tắc ngay bước đầu — và đó chính là tiêu chí "thành viên khác chạy
lại được demo dựa trên README".
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "architecture.md",
    REPO_ROOT / "docs" / "product-brief.md",
    REPO_ROOT / "docs" / "limitations.md",
    REPO_ROOT / "docs" / "demo-script.md",
    REPO_ROOT / "reports" / "week-06" / "report.md",
]

REQUIRED_DELIVERABLES = {
    "docs/architecture.md": "sơ đồ kiến trúc cuối",
    "docs/product-brief.md": "bản mô tả sản phẩm 1–2 trang",
    "docs/limitations.md": "giới hạn và rủi ro còn tồn tại",
    "docs/demo-script.md": "kịch bản trình diễn 10–15 phút",
}

LINK = re.compile(r"\[[^\]]*\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")
MAKE_TARGET = re.compile(r"^([a-z][a-z0-9-]*):", re.MULTILINE)


@pytest.mark.parametrize("relative,label", sorted(REQUIRED_DELIVERABLES.items()))
def test_required_deliverable_exists_and_is_not_a_stub(relative, label):
    path = REPO_ROOT / relative
    assert path.exists(), f"Thiếu deliverable bắt buộc: {relative} ({label})"
    assert len(path.read_text(encoding="utf-8")) > 1500, (
        f"{relative} quá ngắn để là {label}"
    )


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_every_relative_link_resolves(doc):
    if not doc.exists():
        pytest.skip(f"{doc.name} chưa tồn tại")
    broken = []
    for target in LINK.findall(doc.read_text(encoding="utf-8")):
        target = target.strip()
        if not target or target.startswith("mailto:"):
            continue
        if not (doc.parent / target).resolve().exists():
            broken.append(target)
    assert not broken, f"{doc.name} trỏ tới thứ không tồn tại: {broken}"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_every_make_target_mentioned_actually_exists(doc):
    if not doc.exists():
        pytest.skip(f"{doc.name} chưa tồn tại")
    available = set(MAKE_TARGET.findall((REPO_ROOT / "Makefile").read_text(encoding="utf-8")))
    mentioned = set(re.findall(r"\bmake ([a-z][a-z0-9-]*)", doc.read_text(encoding="utf-8")))
    missing = mentioned - available
    assert not missing, f"{doc.name} nhắc tới make target không có: {sorted(missing)}"


def test_readme_documents_every_cli_subcommand():
    """README phải nói tới cả bảy lệnh, không chỉ những lệnh dễ."""
    from project_sentinel.cli import COMMAND_HANDLERS

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    missing = [
        name
        for name in COMMAND_HANDLERS
        if f"cli {name}" not in readme and f"cli.{name}" not in readme
    ]
    assert not missing, f"README chưa hướng dẫn các lệnh: {missing}"


def test_readme_covers_the_handover_workflow():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for phrase, why in [
        ("--yes", "phải nói rõ chế độ tự động phê duyệt"),
        ("clean-runs", "phải nói cách dọn artifact"),
        ("score-ground-truth", "phải nói cách đo chất lượng Agent"),
        ("reports/week-06", "phải trỏ tới báo cáo và evidence pack Tuần 6"),
        ("docs/limitations.md", "phải trỏ tới giới hạn đã biết"),
    ]:
        assert phrase in readme, f"README thiếu `{phrase}` — {why}"


def test_limitations_names_the_numbers_it_cannot_promise():
    text = (REPO_ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")
    assert "dao động" in text or "khoảng đo được" in text.lower()
    assert "over-claim" in text.lower()
