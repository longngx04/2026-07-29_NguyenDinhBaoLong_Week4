"""Hai lời gọi khác dòng là hai sink khác nhau, không phải một finding trùng lặp.

Heuristic cũ gộp hai finding cùng file, cùng rule, cách nhau ≤ 5 dòng. Trên WebGoat
nó gộp đúng những cặp không được gộp:

    SqlInjectionLesson3.java:47  statement.executeUpdate(query)          ← TP
    SqlInjectionLesson3.java:49  executeQuery("SELECT ... 'Barnett';")   ← FP hằng

Schema chỉ cho một `disposition` cho cả nhóm, nên false positive thừa hưởng
`confirmed/high` của true positive nằm cạnh. Đây là nguyên nhân trực tiếp của
over-claim 33,3 %, không phải lỗi phán đoán của Agent.

Gom trùng thật sự đã do khoá `(rule, file, line)` lo. Proximity merge theo định
nghĩa chỉ gộp các dòng KHÁC nhau — tức luôn gộp sink khác nhau.
"""

import json
from pathlib import Path

import pytest

from project_sentinel.analysis.grouping import group_findings
from project_sentinel.config import AppConfig
from project_sentinel.ingestion.input_loader import load_findings

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN = REPO_ROOT / "reports" / "week-06" / "artifacts" / "run-approved"


@pytest.fixture(scope="module")
def webgoat_findings(tmp_path_factory):
    source = json.loads((RUN / "findings.json").read_text(encoding="utf-8"))
    path = tmp_path_factory.mktemp("gt") / "findings.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return load_findings(path).findings


def _group_of(groups, finding_id):
    return next(g for g in groups if finding_id in g.source_finding_ids)


def test_the_two_known_bad_merges_no_longer_happen(webgoat_findings):
    """13+14 và 15+16: mỗi cặp là một TP và một FP, phải nằm ở hai nhóm."""
    groups = group_findings(
        webgoat_findings, near_dup_line_threshold=AppConfig().near_dup_line_threshold
    )
    for true_positive, false_positive in (
        ("opengrep-013", "opengrep-014"),
        ("opengrep-015", "opengrep-016"),
    ):
        assert _group_of(groups, true_positive) is not _group_of(
            groups, false_positive
        ), f"{true_positive} và {false_positive} vẫn bị gộp chung một verdict"


def test_default_config_does_not_proximity_merge():
    assert AppConfig().near_dup_line_threshold < 0, (
        "Proximity merge phải tắt mặc định: nó chỉ gộp được các dòng KHÁC nhau, "
        "tức luôn gộp sink khác nhau."
    )


def test_every_scanner_finding_still_reaches_a_group(webgoat_findings):
    """Tắt merge không được làm rơi finding nào."""
    groups = group_findings(
        webgoat_findings, near_dup_line_threshold=AppConfig().near_dup_line_threshold
    )
    grouped = {fid for g in groups for fid in g.source_finding_ids}
    assert grouped == {f.id for f in webgoat_findings}


def test_exact_duplicates_are_still_collapsed(webgoat_findings):
    """Gom trùng thật vẫn phải hoạt động — nó do khoá (rule, file, line) lo."""
    doubled = list(webgoat_findings) + list(webgoat_findings)
    groups = group_findings(doubled, near_dup_line_threshold=-1)
    assert len(groups) == len(
        group_findings(webgoat_findings, near_dup_line_threshold=-1)
    )


def test_grouping_stays_deterministic(webgoat_findings):
    import random

    baseline = group_findings(webgoat_findings, near_dup_line_threshold=-1)
    shuffled = list(webgoat_findings)
    random.Random(7).shuffle(shuffled)
    other = group_findings(shuffled, near_dup_line_threshold=-1)
    assert [g.group_key for g in baseline] == [g.group_key for g in other]


def test_opting_in_to_proximity_merge_still_works(webgoat_findings):
    """Không xoá tính năng, chỉ tắt mặc định — ai cần vẫn bật được."""
    merged = group_findings(webgoat_findings, near_dup_line_threshold=5)
    unmerged = group_findings(webgoat_findings, near_dup_line_threshold=-1)
    assert len(merged) < len(unmerged)
