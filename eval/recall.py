"""Đo recall: trong số lỗ hổng thật sự tồn tại, hệ thống nói cho ta biết bao nhiêu?

Bộ nhãn `eval/ground-truth/webgoat-findings.json` của nhóm chỉ chứa 23 cảnh báo mà
OpenGrep đã báo. Nó trả lời được "cái được báo có thật không" (precision), nhưng
**về mặt cấu trúc không thể** trả lời "cái có thật có được tìm ra không" (recall) —
theo định nghĩa nó không biết gì về những lỗ hổng bị bỏ sót.

Bộ nhãn của mentor (`ground-truth/mentor/`) liệt kê lỗ hổng có thật trong WebGoat,
dựng từ chính tài liệu `.adoc` và file hint của WebGoat, độc lập với mọi scanner.
Nó lấp đúng chỗ đó. Nguồn gốc và câu hỏi bản quyền: `ground-truth/mentor/PROVENANCE.md`.

Hai chỉ số được tách bạch vì hỏng ở hai tầng khác nhau cần hai cách sửa khác nhau:

- **Scanner recall** — OpenGrep có sinh cảnh báo nào cho lỗ hổng này không?
  Hỏng ở đây thì sửa bằng cách **thêm rule**, không phải chỉnh Agent.
- **End-to-end recall** — lỗ hổng có sống sót tới báo cáo cuối không, hay bị Agent
  gạt đi? Hỏng ở đây thì sửa bằng cách **chỉnh Agent**.

Gộp hai con số làm một sẽ chỉ ra "hệ thống bỏ sót nhiều" mà không nói được sửa ở đâu.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
# Ban GOC cua mentor. Loc no can submodule WebGoat.
RAW_RECALL_TRUTH = (
    REPO_ROOT / "eval" / "ground-truth" / "mentor" / "webgoat-vulnerabilities.jsonl"
)
# Ban DA LOC, duoc commit. Bo cham dung ban nay de chay duoc tu mot
# `git archive HEAD`: archive khong mang theo submodule, va truoc day dieu do lam
# 7 test do tren fresh clone.
DEFAULT_RECALL_TRUTH = (
    REPO_ROOT
    / "eval"
    / "ground-truth"
    / "mentor"
    / "webgoat-vulnerabilities.applicable.json"
)
DEFAULT_TARGET_ROOT = REPO_ROOT / "benchmarks" / "targets" / "webgoat"

# Tien to duong dan trong findings.json, tinh tu goc repo.
TARGET_PREFIX = "benchmarks/targets/webgoat/"

# Agent noi mot trong bon tu nay. Chi `false_positive` nghia la "dung bo qua".
DISMISSED = "false_positive"

SEVERITIES = ("critical", "high", "medium", "low")


def load_vulnerabilities(
    path: str | Path = DEFAULT_RECALL_TRUTH,
    *,
    target_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Nạp bộ nhãn lỗ hổng, bỏ những mục không áp dụng được cho submodule đang ghim.

    Mentor dựng bộ này trên một bản WebGoat khác, nên vài mục trỏ tới file không tồn
    tại ở đây (ví dụ lesson `openredirect`). Giữ chúng lại thì chúng trở thành false
    negative vĩnh viễn và làm recall xấu đi một cách **sai sự thật** — hệ thống bị
    trách vì không tìm ra thứ không có trong mã nguồn.

    `target_root=None` tắt lọc, dùng khi cần xem trọn bộ gốc.
    """
    source = Path(path)
    text = source.read_text(encoding="utf-8")

    # Ban da loc la mot JSON object; ban goc cua mentor la JSONL.
    if source.suffix == ".json":
        payload = json.loads(text)
        rows = [
            entry
            for entry in payload.get("vulnerabilities", [])
            if isinstance(entry, dict) and entry.get("file")
        ]
        if target_root is None:
            return rows
        return [row for row in rows if (Path(target_root) / row["file"]).exists()]

    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or not entry.get("file"):
            continue
        if target_root is not None and not (Path(target_root) / entry["file"]).exists():
            continue
        rows.append(entry)
    return rows


def _scanned_files(findings: Any) -> dict[str, list[str]]:
    """Ánh xạ đường dẫn (tương đối với WebGoat) → các finding id chạm tới nó."""
    mapping: dict[str, list[str]] = {}
    if not isinstance(findings, list):
        return mapping
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        path = finding.get("file_or_url")
        if not isinstance(path, str):
            continue
        relative = path[len(TARGET_PREFIX):] if path.startswith(TARGET_PREFIX) else path
        finding_id = finding.get("id")
        if isinstance(finding_id, str) and finding_id:
            mapping.setdefault(relative, []).append(finding_id)
        else:
            mapping.setdefault(relative, [])
    return mapping


def _disposition_by_finding(records: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not isinstance(records, list):
        return mapping
    for record in records:
        if not isinstance(record, dict):
            continue
        ids = record.get("source_finding_ids")
        if not isinstance(ids, list):
            continue
        disposition = record.get("disposition")
        for finding_id in ids:
            if isinstance(finding_id, str) and finding_id:
                mapping[finding_id] = (
                    disposition if isinstance(disposition, str) else "unknown"
                )
    return mapping


def _tally(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def score_recall(
    *, findings: Any, records: Any, vulnerabilities: list[dict[str, Any]]
) -> dict[str, Any]:
    """Chấm recall của một lần chạy so với bộ nhãn lỗ hổng."""
    scanned = _scanned_files(findings)
    dispositions = _disposition_by_finding(records)

    found: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    reported: list[dict[str, Any]] = []
    dismissed: list[dict[str, Any]] = []

    for vulnerability in vulnerabilities:
        paths = [vulnerability["file"], *(vulnerability.get("related_files") or [])]
        touching: list[str] = []
        for path in paths:
            touching.extend(scanned.get(path, []))

        if not any(path in scanned for path in paths):
            missed.append(vulnerability)
            continue

        found.append(vulnerability)

        # Co canh bao, nhung Agent co giu lai khong?
        verdicts = {dispositions.get(finding_id) for finding_id in touching}
        verdicts.discard(None)
        if verdicts and verdicts <= {DISMISSED}:
            dismissed.append(vulnerability)
        elif verdicts:
            reported.append(vulnerability)
        else:
            # Canh bao ton tai nhung khong record nao phu no — record bi mat o
            # buoc analyze. Nguoi doc bao cao cuoi khong thay lo hong nay.
            dismissed.append(vulnerability)

    total = len(vulnerabilities)
    return {
        "total_known_vulnerabilities": total,
        "scanner": {
            "found": len(found),
            "missed": len(missed),
            "recall": round(len(found) / total, 4) if total else 0.0,
            "missed_by_type": _tally(missed, "vulnerability_type"),
            "missed_by_severity": _tally(missed, "severity"),
            "missed_items": [
                {
                    "id": item["id"],
                    "vulnerability_type": item["vulnerability_type"],
                    "severity": item["severity"],
                    "file": item["file"],
                }
                for item in missed
            ],
            "note": (
                "Hong o day thi sua bang cach THEM RULE cho scanner, khong phai "
                "chinh Agent."
            ),
        },
        "end_to_end": {
            "reported": len(reported),
            "dismissed_by_agent": len(dismissed),
            "recall": round(len(reported) / total, 4) if total else 0.0,
            "dismissed_items": [
                {"id": item["id"], "vulnerability_type": item["vulnerability_type"]}
                for item in dismissed
            ],
            "note": (
                "Ty le lo hong THAT SU ton tai ma nguoi doc bao cao cuoi biet duoc. "
                "Day la con so co y nghia nhat voi nguoi dung."
            ),
        },
    }


def render(report: dict[str, Any]) -> str:
    scanner = report["scanner"]
    end = report["end_to_end"]
    total = report["total_known_vulnerabilities"]
    lines = [
        "=== Recall — đối chiếu bộ nhãn lỗ hổng của mentor ===",
        f"  Lỗ hổng đã biết trong WebGoat : {total}",
        "",
        f"  Scanner tìm tới               : {scanner['found']}/{total}"
        f" ({scanner['recall']:.1%})",
        f"  Scanner bỏ sót                : {scanner['missed']}/{total}",
        f"  Tới được báo cáo cuối         : {end['reported']}/{total}"
        f" ({end['recall']:.1%})",
    ]
    if end["dismissed_by_agent"]:
        lines.append(
            f"  ! Agent gạt đi hoặc làm mất   : {end['dismissed_by_agent']}"
            " (scanner đã tìm ra nhưng người đọc vẫn không biết)"
        )
    if scanner["missed_by_severity"]:
        lines += ["", "  Bỏ sót theo mức nghiêm trọng:"]
        for severity in SEVERITIES:
            count = scanner["missed_by_severity"].get(severity)
            if count:
                lines.append(f"    {severity:<9}: {count}")
    if scanner["missed_by_type"]:
        lines += ["", "  Bỏ sót nhiều nhất theo loại:"]
        for name, count in list(scanner["missed_by_type"].items())[:8]:
            lines.append(f"    {count:>2}x  {name[:64]}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_RECALL_TRUTH",
    "DEFAULT_TARGET_ROOT",
    "load_vulnerabilities",
    "render",
    "score_recall",
]
