"""Allowlist POST cho lane DAST: mỗi mục là một request thật vào ứng dụng có lỗ hổng.

Cổng bảo vệ duy nhất là người đọc @RequestParam rồi chọn body làm ít nhất có
thể. Các test dưới đây không thay được việc review, nhưng chúng chặn những
kiểu sai máy móc: trích sai dòng nguồn, method lạ, path ngoài /WebGoat/.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST = REPO_ROOT / "configs" / "gateway" / "dast-allowlist.json"

REQUIRED_FIELDS = {
    "path",
    "method",
    "canonical_body",
    "content_type",
    "purpose",
    "source",
}


def _entries() -> list[dict]:
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    return data["endpoints"]


def test_every_entry_has_all_required_fields():
    for entry in _entries():
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"{entry.get('path')}: thiếu {sorted(missing)}"


def test_every_entry_is_post_under_the_webgoat_prefix():
    for entry in _entries():
        assert entry["method"] == "POST", (
            f"{entry['path']}: allowlist này CHỈ dành cho POST. GET/HEAD đã "
            "được lane cho phép sẵn và không cần khai ở đây."
        )
        assert entry["path"].startswith("/WebGoat/"), entry["path"]
        assert "?" not in entry["path"], "Path không được mang query"
        assert "{" not in entry["path"], (
            f"{entry['path']}: path template không dùng được — map nginx cần key chính xác"
        )


def test_no_duplicate_paths():
    paths = [entry["path"] for entry in _entries()]
    assert len(paths) == len(set(paths)), f"Path trùng: {paths}"


def test_every_source_points_at_a_real_postmapping():
    """Trích sai dòng nguồn làm cả review mất căn cứ."""
    for entry in _entries():
        raw = entry["source"]
        file_part, line_part = raw.rsplit(":", 1)
        start = int(line_part.split("-")[0])
        path = REPO_ROOT / file_part
        assert path.is_file(), f"{entry['path']}: không có file {file_part}"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        assert start <= len(lines), f"{entry['path']}: file chỉ có {len(lines)} dòng"
        window = "\n".join(lines[start - 1 : start + 4])
        route = entry["path"].removeprefix("/WebGoat")
        assert "@PostMapping" in window, (
            f"{entry['path']}: dòng {start} của {file_part} không có @PostMapping"
        )
        assert route in window, f"{entry['path']}: dòng {start} không khai route {route}"


def test_every_canonical_body_names_a_parameter_the_endpoint_declares():
    """Body chính tắc phải dùng đúng tên tham số Java khai, không phải tên đoán."""
    for entry in _entries():
        body = entry["canonical_body"]
        assert body, f"{entry['path']}: canonical_body rỗng chuỗi"
        param = body.split("=", 1)[0]
        file_part, line_part = entry["source"].rsplit(":", 1)
        start = int(line_part.split("-")[0])
        lines = (REPO_ROOT / file_part).read_text(encoding="utf-8", errors="replace").splitlines()
        window = "\n".join(lines[start - 1 : start + 6])
        assert re.search(rf"\b{re.escape(param)}\b", window), (
            f"{entry['path']}: tham số '{param}' không xuất hiện trong chữ ký "
            f"method tại {file_part}:{start}"
        )


def test_canonical_body_carries_no_sql_or_shell():
    """Body chính tắc phải làm ÍT NHẤT có thể, không phải một payload khéo léo."""
    banned = ["select", "union", "drop", "'", '"', ";", "--", "$(", "`"]
    for entry in _entries():
        low = entry["canonical_body"].lower()
        hits = [token for token in banned if token in low]
        assert not hits, (
            f"{entry['path']}: canonical_body chứa {hits}. Body chỉ để chứng "
            "minh endpoint sống, không để thử gì cả."
        )
