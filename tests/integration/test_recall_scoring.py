"""Đo recall: trong số lỗ hổng THẬT SỰ tồn tại, hệ thống nói cho ta biết bao nhiêu?

`webgoat-findings.json` của nhóm chỉ chứa 23 cảnh báo mà OpenGrep đã báo, nên nó
**về cấu trúc không thể** đo recall — theo định nghĩa nó không biết gì về những lỗ
hổng bị bỏ sót. Bộ nhãn của mentor liệt kê lỗ hổng có thật, độc lập với mọi scanner,
nên nó trả lời được câu đó.

Hai chỉ số tách bạch, vì hỏng ở hai tầng khác nhau cần hai cách sửa khác nhau:

- **Scanner recall** — OpenGrep có sinh ra cảnh báo nào cho lỗ hổng này không?
  Hỏng ở đây thì sửa bằng cách thêm rule.
- **End-to-end recall** — lỗ hổng có sống sót tới báo cáo cuối không, hay bị Agent
  gạt đi? Hỏng ở đây thì sửa bằng cách chỉnh Agent.
"""

import json
from pathlib import Path

import pytest

from eval.recall import (
    DEFAULT_RECALL_TRUTH,
    RAW_RECALL_TRUTH,
    load_vulnerabilities,
    score_recall,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBGOAT = REPO_ROOT / "benchmarks" / "targets" / "webgoat"
# Thu muc submodule VAN TON TAI (rong) trong mot `git archive`, nen `.exists()`
# tren thu muc khong noi len duoc submodule da init hay chua. Doi chieu mot file
# co that ben trong.
WEBGOAT_INITIALISED = (WEBGOAT / "src" / "main" / "java").is_dir()


@pytest.fixture(scope="module")
def vulnerabilities():
    # Ban da loc duoc commit, nen fixture nay khong can submodule WebGoat.
    return load_vulnerabilities(DEFAULT_RECALL_TRUTH)


# --- bộ nhãn ---------------------------------------------------------------


def test_the_vendored_dataset_loads(vulnerabilities):
    assert len(vulnerabilities) >= 60, (
        "Bộ nhãn của mentor phải còn lại phần lớn sau khi lọc theo submodule"
    )


def test_entries_pointing_outside_the_pinned_submodule_are_dropped():
    """Mentor dựng bộ này trên một bản WebGoat khác; mục trỏ file không có phải bỏ.

    Giữ lại thì chúng thành false negative vĩnh viễn và làm recall xấu đi một cách
    sai sự thật.
    """
    everything = load_vulnerabilities(RAW_RECALL_TRUTH, target_root=None)
    applicable = load_vulnerabilities(DEFAULT_RECALL_TRUTH)
    assert len(applicable) < len(everything)


@pytest.mark.skipif(
    not WEBGOAT_INITIALISED,
    reason="Submodule WebGoat chưa init — không đối chiếu được bản đã lọc",
)
def test_the_committed_filtered_list_is_still_current():
    """Bản đã lọc là dữ liệu dẫn xuất. Nó phải khớp thứ lọc lại sinh ra.

    Chạy khi có submodule, nên nó bắt được lúc submodule được ghim sang commit
    khác mà không ai chạy lại `make refresh-recall-truth`. Không có test này, bản
    đã lọc sẽ âm thầm cũ đi và mọi con số recall lệch theo.
    """
    committed = {item["id"] for item in load_vulnerabilities(DEFAULT_RECALL_TRUTH)}
    recomputed = {
        item["id"]
        for item in load_vulnerabilities(RAW_RECALL_TRUTH, target_root=WEBGOAT)
    }
    assert committed == recomputed, (
        "Bản đã lọc đã cũ. Chạy: make refresh-recall-truth"
    )


def test_every_entry_has_what_scoring_needs(vulnerabilities):
    for item in vulnerabilities:
        assert item["id"]
        assert item["file"]
        assert item["vulnerability_type"]
        assert item["severity"] in {"critical", "high", "medium", "low"}


# --- chấm ------------------------------------------------------------------


def _finding(path, finding_id="opengrep-x"):
    return {"id": finding_id, "file_or_url": f"benchmarks/targets/webgoat/{path}"}


def _record(finding_ids, disposition="likely"):
    return {
        "analysis_id": "analysis-a",
        "source_finding_ids": list(finding_ids),
        "title": "SQL Injection",
        "severity": "high",
        "disposition": disposition,
    }


def test_a_vulnerability_nobody_scanned_is_a_scanner_miss(vulnerabilities):
    report = score_recall(findings=[], records=[], vulnerabilities=vulnerabilities)
    assert report["scanner"]["found"] == 0
    assert report["scanner"]["missed"] == len(vulnerabilities)
    assert report["scanner"]["recall"] == 0.0


def test_a_scanned_vulnerability_counts_as_found(vulnerabilities):
    target = vulnerabilities[0]
    report = score_recall(
        findings=[_finding(target["file"])], records=[], vulnerabilities=vulnerabilities
    )
    assert report["scanner"]["found"] == 1
    assert target["id"] not in [m["id"] for m in report["scanner"]["missed_items"]]


def test_related_files_also_count_as_reaching_the_vulnerability(vulnerabilities):
    target = next(v for v in vulnerabilities if v.get("related_files"))
    report = score_recall(
        findings=[_finding(target["related_files"][0])],
        records=[],
        vulnerabilities=vulnerabilities,
    )
    assert report["scanner"]["found"] >= 1


def test_agent_dismissing_a_real_vulnerability_is_an_end_to_end_miss(vulnerabilities):
    """Scanner tìm ra, nhưng Agent gọi là false_positive — người dùng vẫn không biết."""
    target = vulnerabilities[0]
    findings = [_finding(target["file"], "opengrep-1")]
    report = score_recall(
        findings=findings,
        records=[_record(["opengrep-1"], disposition="false_positive")],
        vulnerabilities=vulnerabilities,
    )
    assert report["scanner"]["found"] == 1
    assert report["end_to_end"]["reported"] == 0
    assert report["end_to_end"]["dismissed_by_agent"] == 1


def test_agent_keeping_a_real_vulnerability_counts_end_to_end(vulnerabilities):
    target = vulnerabilities[0]
    report = score_recall(
        findings=[_finding(target["file"], "opengrep-1")],
        records=[_record(["opengrep-1"], disposition="confirmed")],
        vulnerabilities=vulnerabilities,
    )
    assert report["end_to_end"]["reported"] == 1
    assert report["end_to_end"]["dismissed_by_agent"] == 0


def test_misses_are_grouped_so_they_point_at_a_fix(vulnerabilities):
    """Danh sách bỏ sót phải gom theo loại, nếu không nó chỉ là 61 dòng vô dụng."""
    report = score_recall(findings=[], records=[], vulnerabilities=vulnerabilities)
    by_type = report["scanner"]["missed_by_type"]
    assert by_type
    assert sum(by_type.values()) == report["scanner"]["missed"]


def test_severity_breakdown_separates_the_misses_that_matter(vulnerabilities):
    report = score_recall(findings=[], records=[], vulnerabilities=vulnerabilities)
    by_sev = report["scanner"]["missed_by_severity"]
    assert set(by_sev) <= {"critical", "high", "medium", "low"}
    assert sum(by_sev.values()) == report["scanner"]["missed"]


# --- số liệu thật ----------------------------------------------------------


def test_the_real_run_recall_is_recorded_honestly(vulnerabilities):
    """Chốt con số thật: bộ rule hiện tại bỏ sót phần lớn lỗ hổng của WebGoat."""
    run = REPO_ROOT / "reports/week-06/artifacts/run-approved"
    findings = json.loads((run / "findings.json").read_text(encoding="utf-8"))["findings"]
    records = [
        json.loads(line)
        for line in (run / "analysis.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = score_recall(
        findings=findings, records=records, vulnerabilities=vulnerabilities
    )
    assert report["scanner"]["recall"] < 0.30, (
        "Recall bất ngờ cao — kiểm tra lại việc ghép đường dẫn trước khi ăn mừng"
    )
    assert report["scanner"]["missed_by_severity"].get("high", 0) > 10
