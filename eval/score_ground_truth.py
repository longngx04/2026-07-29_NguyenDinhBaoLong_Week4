"""Chấm Agent trên 23 finding WebGoat thật, đối chiếu với nhãn do người review đặt.

Bộ sáu ca trong `eval/cases/` là dữ liệu tự nghĩ ra. Nó trả lời câu "Agent có
chạy đúng trên input mẫu không". Nó KHÔNG trả lời câu quan trọng hơn: "trên
output thật của sản phẩm, Agent phân loại đúng bao nhiêu phần trăm".

File này trả lời câu thứ hai, và tách rõ hai con số hay bị gộp làm một:

- **Scanner precision** — trong 23 cảnh báo OpenGrep đưa ra, bao nhiêu là lỗ hổng
  thật. Đây là thuộc tính của scanner và bộ nhãn, không liên quan tới Agent.
- **Agent triage precision** — Agent phân loại đúng bao nhiêu trong số đó. Đây
  mới là con số nói về chất lượng Agent.

Chỉ số đáng lo nhất được tính riêng: **over-claim rate** — tỷ lệ finding thật sự
là false positive mà Agent vẫn trình bày như lỗ hổng có thật.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUND_TRUTH = REPO_ROOT / "eval" / "ground-truth" / "webgoat-findings.json"

# Agent nói `disposition`; người review nói `label`. Bảng này nối hai từ vựng.
DISPOSITION_TO_LABEL: dict[str, str] = {
    "confirmed": "true_positive",
    "likely": "true_positive",
    "needs_review": "needs_review",
    "false_positive": "false_positive",
}

# Trình bày một finding như lỗ hổng có thật.
ASSERTIVE_DISPOSITIONS: frozenset[str] = frozenset({"confirmed", "likely"})

# Bản analysis.jsonl sinh trước khi có `disposition` không có gì để đọc. Với
# những bản đó, thứ người đọc thật sự thấy là mức nghiêm trọng.
ASSERTIVE_SEVERITIES: frozenset[str] = frozenset({"critical", "high"})


def is_presented_as_real(record: dict[str, Any]) -> bool:
    """Người đọc báo cáo có hiểu đây là lỗ hổng có thật không?

    Chấm theo CÁCH TRÌNH BÀY chứ không theo sự tồn tại của một field. Nếu chỉ
    đếm `disposition`, một bản chạy cũ không có field đó sẽ được báo
    "over-claim 0%" trong khi nó gán `high` cho mọi thứ — con số đẹp vì thiếu
    dữ liệu, đúng loại số liệu mà bộ chấm này sinh ra để chặn.
    """
    disposition = record.get("disposition")
    if isinstance(disposition, str) and disposition:
        return disposition in ASSERTIVE_DISPOSITIONS
    return record.get("severity") in ASSERTIVE_SEVERITIES


def load_ground_truth(path: str | Path = DEFAULT_GROUND_TRUTH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data.get("cases"), list):
        raise ValueError(f"Bộ nhãn {path} thiếu mảng 'cases'")
    return data


def load_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            records.append(entry)
    return records


def _record_by_finding(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Một record phân tích có thể phủ nhiều finding — trải phẳng theo finding id.

    Nhóm là quyết định của hệ thống, còn nhãn được đặt trên từng finding. Khi một
    record phủ nhiều finding, kết luận của nó áp cho tất cả — và đó chính là chỗ
    ghép nhóm quá tay lộ ra: một false positive bị gộp cùng một true positive sẽ
    thừa hưởng kết luận của cả nhóm.
    """
    mapping: dict[str, dict[str, Any]] = {}
    for record in records:
        ids = record.get("source_finding_ids")
        if not isinstance(ids, list):
            continue
        for finding_id in ids:
            if isinstance(finding_id, str) and finding_id:
                mapping.setdefault(finding_id, record)
    return mapping


def _scanner_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"true_positive": 0, "false_positive": 0, "needs_review": 0}
    for case in cases:
        label = case.get("label")
        if label in counts:
            counts[label] += 1
    total = len(cases)
    tp, fp, nr = counts["true_positive"], counts["false_positive"], counts["needs_review"]
    return {
        "total_findings": total,
        **counts,
        # Chặt: chỉ true positive mới tính là đúng.
        "precision_strict": round(tp / total, 4) if total else 0.0,
        # Rộng: bỏ needs_review ra khỏi mẫu số vì chúng chưa kết luận được.
        "precision_excluding_unresolved": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
        "note": (
            "Hai con so nay do CHAT LUONG SCANNER va bo nhan, khong do Agent. "
            "OpenGrep gan 'high' cho ca 23 canh bao."
        ),
    }


def _dimension(name: str, expected_key: str) -> tuple[str, str]:
    return name, expected_key


def score(
    records: list[dict[str, Any]], ground_truth: dict[str, Any]
) -> dict[str, Any]:
    """Chấm một analysis.jsonl so với bộ nhãn, trả về báo cáo số liệu."""
    cases = ground_truth["cases"]
    by_finding = _record_by_finding(records)

    matched = 0
    label_agreements = 0
    over_claimed: list[dict[str, Any]] = []
    under_claimed: list[dict[str, Any]] = []
    unmatched: list[str] = []
    confusion: dict[str, dict[str, int]] = {}

    dimensions = {
        "severity": {"compared": 0, "match": 0, "mismatch": []},
        "attacker_control": {"compared": 0, "match": 0, "mismatch": []},
        "category": {"compared": 0, "match": 0, "mismatch": []},
    }
    records_without_disposition = 0
    coverage = {
        "explanation_nonempty": 0,
        "remediation_nonempty": 0,
        "confidence_present": 0,
    }

    for case in cases:
        finding_id = case["finding_id"]
        expected_label = case.get("label")
        record = by_finding.get(finding_id)
        if record is None:
            unmatched.append(finding_id)
            continue

        matched += 1
        disposition = record.get("disposition")
        if not isinstance(disposition, str) or not disposition:
            records_without_disposition += 1
        predicted_label = DISPOSITION_TO_LABEL.get(disposition, "unknown")

        row = confusion.setdefault(expected_label, {})
        row[predicted_label] = row.get(predicted_label, 0) + 1

        if predicted_label == expected_label:
            label_agreements += 1

        # Sai nguy hiem: false positive duoc trinh bay nhu lo hong that.
        if expected_label == "false_positive" and is_presented_as_real(record):
            over_claimed.append(
                {
                    "finding_id": finding_id,
                    "agent_disposition": disposition or "(không có field)",
                    "agent_severity": record.get("severity"),
                    "reason": case.get("reason"),
                }
            )
        # Sai theo huong bo sot: lo hong that bi goi la false positive.
        if expected_label == "true_positive" and disposition == "false_positive":
            under_claimed.append(
                {"finding_id": finding_id, "reason": case.get("reason")}
            )

        for dim_name, expected_key in (
            _dimension("severity", "expected_severity"),
            _dimension("attacker_control", "expected_attacker_control"),
        ):
            expected_value = case.get(expected_key)
            actual_value = record.get(dim_name)
            if expected_value is None or actual_value is None:
                continue
            dimensions[dim_name]["compared"] += 1
            if expected_value == actual_value:
                dimensions[dim_name]["match"] += 1
            else:
                dimensions[dim_name]["mismatch"].append(
                    {
                        "finding_id": finding_id,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )

        expected_category = case.get("expected_category")
        title = record.get("title")
        if expected_category and isinstance(title, str):
            dimensions["category"]["compared"] += 1
            if expected_category.lower() in title.lower():
                dimensions["category"]["match"] += 1
            else:
                dimensions["category"]["mismatch"].append(
                    {
                        "finding_id": finding_id,
                        "expected": expected_category,
                        "actual": title,
                    }
                )

        if isinstance(record.get("explanation"), str) and record["explanation"].strip():
            coverage["explanation_nonempty"] += 1
        remediation = record.get("remediation")
        if isinstance(remediation, list) and any(str(x).strip() for x in remediation):
            coverage["remediation_nonempty"] += 1
        if record.get("confidence"):
            coverage["confidence_present"] += 1

    real_fp_total = sum(1 for c in cases if c.get("label") == "false_positive")
    matched_fp = sum(
        1
        for c in cases
        if c.get("label") == "false_positive" and c["finding_id"] in by_finding
    )

    for dim in dimensions.values():
        dim["rate"] = (
            round(dim["match"] / dim["compared"], 4) if dim["compared"] else None
        )

    return {
        "scanner": _scanner_metrics(cases),
        "agent": {
            "findings_in_ground_truth": len(cases),
            "findings_matched_to_a_record": matched,
            "findings_without_a_record": unmatched,
            "label_agreement": label_agreements,
            "records_without_disposition": records_without_disposition,
            "triage_precision": (
                round(label_agreements / matched, 4) if matched else None
            ),
            "over_claimed_false_positives": over_claimed,
            "over_claim_rate": (
                round(len(over_claimed) / matched_fp, 4) if matched_fp else None
            ),
            "under_claimed_true_positives": under_claimed,
            "confusion": confusion,
            "note": (
                "triage_precision do Agent, KHONG do scanner. over_claim_rate la "
                "chi so dang lo nhat: ty le false positive that duoc trinh bay nhu "
                "lo hong co that."
            ),
        },
        "dimensions": dimensions,
        "coverage": {
            **coverage,
            "of_matched": matched,
            "note": (
                "Coverage chi dem CO NOI DUNG hay khong. No khong cham chat luong "
                "noi dung — viec do van can nguoi doc."
            ),
        },
    }


def render(report: dict[str, Any]) -> str:
    scanner = report["scanner"]
    agent = report["agent"]
    lines = [
        "=== Scanner (OpenGrep + bộ nhãn người review) ===",
        f"  Tổng cảnh báo            : {scanner['total_findings']}",
        f"  true_positive            : {scanner['true_positive']}",
        f"  false_positive           : {scanner['false_positive']}",
        f"  needs_review             : {scanner['needs_review']}",
        f"  Precision (chặt)         : {scanner['precision_strict']:.1%}",
        f"  Precision (bỏ chưa rõ)   : {scanner['precision_excluding_unresolved']:.1%}",
        "",
        "=== Agent triage ===",
        f"  Finding khớp được record : {agent['findings_matched_to_a_record']}"
        f"/{agent['findings_in_ground_truth']}",
    ]
    if agent["records_without_disposition"]:
        lines.append(
            f"  ! {agent['records_without_disposition']} record không có field "
            "`disposition` — bản chạy trước Task E; chấm theo severity."
        )
    if agent["triage_precision"] is not None:
        lines.append(f"  Triage precision         : {agent['triage_precision']:.1%}")
    if agent["over_claim_rate"] is not None:
        lines.append(
            f"  Over-claim rate          : {agent['over_claim_rate']:.1%} "
            f"({len(agent['over_claimed_false_positives'])} false positive bị trình bày như lỗ hổng thật)"
        )
    for item in agent["over_claimed_false_positives"]:
        lines.append(
            f"    ! {item['finding_id']}: {item['agent_disposition']}"
            f"/{item['agent_severity']}"
        )
    lines.append("")
    lines.append("=== Từng chiều ===")
    for name, dim in report["dimensions"].items():
        rate = f"{dim['rate']:.1%}" if dim["rate"] is not None else "n/a"
        lines.append(f"  {name:<18}: {dim['match']}/{dim['compared']} ({rate})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chấm Agent trên bộ nhãn WebGoat thật."
    )
    parser.add_argument(
        "--analysis", required=True, help="Đường dẫn tới analysis.jsonl của một lần chạy"
    )
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--json-out", default=None, help="Ghi báo cáo JSON ra file")
    args = parser.parse_args(argv)

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(f"Không tìm thấy {analysis_path}", file=sys.stderr)
        return 2

    report = score(load_records(analysis_path), load_ground_truth(args.ground_truth))
    print(render(report))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nBáo cáo JSON: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
