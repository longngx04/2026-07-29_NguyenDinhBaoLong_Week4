"""Tài liệu target phải liệt kê đúng các endpoint trong allowlist."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "docs" / "target-webgoat.md"
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"


def test_doc_exists():
    assert DOC_PATH.exists(), "docs/target-webgoat.md là deliverable bắt buộc của tuần 1"


def test_doc_covers_required_sections():
    text = DOC_PATH.read_text(encoding="utf-8")
    for heading in ("## Kiến trúc", "## Endpoint chính", "## Cảnh báo đã phát hiện"):
        assert heading in text, f"Thiếu mục bắt buộc: {heading}"


def test_doc_lists_every_allowlisted_path():
    text = DOC_PATH.read_text(encoding="utf-8")
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    for endpoint in allowlist["endpoints"]:
        assert endpoint["path"] in text, (
            f"Endpoint {endpoint['path']} có trong allowlist nhưng không có trong tài liệu"
        )