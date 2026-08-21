"""Bộ chấm ground truth phải nói đúng, kể cả khi sự thật khó nghe.

Bẫy lớn nhất của một bộ chấm là báo số đẹp vì thiếu dữ liệu. Các test dưới đây
chốt rằng không xảy ra chuyện đó.
"""

import json
from pathlib import Path

import pytest

from eval.score_ground_truth import (
    DEFAULT_GROUND_TRUTH,
    is_presented_as_real,
    load_ground_truth,
    score,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Doc tu EVIDENCE PACK DA COMMIT, khong doc `artifacts/runs/` — thu muc do bi Git
# ignore, nen suite chi xanh tren may con giu artifact cu va fail tren fresh clone.
BASELINE = REPO_ROOT / "reports" / "week-06" / "artifacts" / "run-baseline"


@pytest.fixture(scope="module")
def ground_truth():
    return load_ground_truth(DEFAULT_GROUND_TRUTH)


def _record(finding_ids, **overrides):
    base = {
        "analysis_id": "analysis-x",
        "source_finding_ids": list(finding_ids),
        "title": "SQL Injection",
        "severity": "high",
        "disposition": "likely",
        "attacker_control": "proven",
        "explanation": "giai thich",
        "remediation": ["dung PreparedStatement"],
        "confidence": "high",
    }
    base.update(overrides)
    return base


# --- bộ nhãn ---------------------------------------------------------------


def test_ground_truth_covers_every_finding_of_the_real_run(ground_truth):
    findings = json.loads(
        (BASELINE / "findings.json").read_text(encoding="utf-8")
    )["findings"]
    labeled = {case["finding_id"] for case in ground_truth["cases"]}
    assert {f["id"] for f in findings} == labeled


def test_ground_truth_includes_the_two_static_query_sinks(ground_truth):
    """Hai ca review chỉ đích danh phải có mặt và phải là false positive."""
    by_id = {case["finding_id"]: case for case in ground_truth["cases"]}
    assert by_id["opengrep-011"]["label"] == "false_positive"
    assert by_id["opengrep-023"]["label"] == "false_positive"


def test_every_case_states_a_dataflow_not_just_a_filename(ground_truth):
    for case in ground_truth["cases"]:
        assert case["dataflow"].strip(), case["finding_id"]
        assert case["reason"].strip(), case["finding_id"]


def test_declared_counts_match_the_actual_labels(ground_truth):
    counts: dict[str, int] = {}
    for case in ground_truth["cases"]:
        counts[case["label"]] = counts.get(case["label"], 0) + 1
    assert counts == ground_truth["label_counts"]


# --- cách trình bày --------------------------------------------------------


def test_a_record_without_disposition_is_judged_by_its_severity():
    """Bản chạy cũ không có disposition không được hưởng điểm 'chưa khẳng định'."""
    assert is_presented_as_real({"severity": "high"}) is True
    assert is_presented_as_real({"severity": "info"}) is False


def test_disposition_wins_over_severity_when_present():
    assert is_presented_as_real({"disposition": "needs_review", "severity": "high"}) is False
    assert is_presented_as_real({"disposition": "confirmed", "severity": "low"}) is True


# --- chấm ------------------------------------------------------------------


def test_scanner_metrics_do_not_depend_on_the_agent(ground_truth):
    empty = score([], ground_truth)
    full = score(
        [_record(["opengrep-011"], disposition="false_positive", severity="info")],
        ground_truth,
    )
    assert empty["scanner"] == full["scanner"]


def test_calling_a_false_positive_high_counts_as_an_over_claim(ground_truth):
    report = score(
        [_record(["opengrep-011"], disposition="likely", severity="high")],
        ground_truth,
    )
    assert report["agent"]["over_claim_rate"] == 1.0
    assert report["agent"]["over_claimed_false_positives"][0]["finding_id"] == (
        "opengrep-011"
    )


def test_calling_a_false_positive_false_positive_is_not_an_over_claim(ground_truth):
    report = score(
        [
            _record(
                ["opengrep-011"],
                disposition="false_positive",
                severity="info",
                attacker_control="not_proven",
            )
        ],
        ground_truth,
    )
    assert report["agent"]["over_claim_rate"] == 0.0
    assert report["agent"]["triage_precision"] == 1.0


def test_calling_a_real_vulnerability_a_false_positive_is_reported(ground_truth):
    report = score(
        [_record(["opengrep-012"], disposition="false_positive", severity="info")],
        ground_truth,
    )
    assert report["agent"]["under_claimed_true_positives"][0]["finding_id"] == (
        "opengrep-012"
    )


def test_findings_with_no_record_are_named_not_silently_dropped(ground_truth):
    report = score([], ground_truth)
    assert len(report["agent"]["findings_without_a_record"]) == 23
    assert report["agent"]["triage_precision"] is None


def test_a_grouped_record_applies_its_verdict_to_every_finding_it_covers(ground_truth):
    """Gộp một false positive chung nhóm với một true positive thì lộ ra ở đây."""
    report = score(
        [
            _record(
                ["opengrep-012", "opengrep-011"], disposition="likely", severity="high"
            )
        ],
        ground_truth,
    )
    assert report["agent"]["over_claim_rate"] == 1.0


def test_the_real_run_baseline_over_claims_every_false_positive(ground_truth):
    """Chốt số liệu nền của lần chạy 20260821T045519Z trước khi có Task E.

    Đây là bằng chứng cho phát hiện của mentor: mọi false positive đều được
    trình bày là `high`.
    """
    from eval.score_ground_truth import load_records

    records = load_records(BASELINE / "analysis.jsonl")
    report = score(records, ground_truth)
    assert report["scanner"]["precision_strict"] == pytest.approx(0.5652, abs=1e-3)
    assert report["agent"]["over_claim_rate"] == 1.0
    assert report["agent"]["records_without_disposition"] == 21
