import random
from project_sentinel.analysis.grouping import group_findings
from project_sentinel.models import NormalizedFinding, NormalizedLocation


def _make_finding(fid, rule_id, file_path, line, fingerprint=None, cwe=None, owasp=None, severity="high"):
    return NormalizedFinding(
        id=fid,
        rule_id=rule_id,
        title=f"Finding {fid}",
        severity=severity,
        confidence="MEDIUM",
        location=NormalizedLocation(file=file_path, line=line),
        fingerprint=fingerprint,
        cwe=cwe or ["CWE-89"],
        owasp=owasp or ["A03:2021-Injection"]
    )


def test_grouping_same_fingerprint():
    f1 = _make_finding("f1", "rule-sqli", "app/db.py", 10, fingerprint="fp-100")
    f2 = _make_finding("f2", "rule-sqli", "app/db.py", 10, fingerprint="fp-100")
    
    groups = group_findings([f1, f2])
    assert len(groups) == 1
    assert set(groups[0].source_finding_ids) == {"f1", "f2"}


def test_grouping_different_files():
    f1 = _make_finding("f1", "rule-sqli", "app/a.py", 10)
    f2 = _make_finding("f2", "rule-sqli", "app/b.py", 10)
    
    groups = group_findings([f1, f2])
    assert len(groups) == 2


def test_grouping_distant_lines():
    f1 = _make_finding("f1", "rule-sqli", "app/a.py", 10)
    f2 = _make_finding("f2", "rule-sqli", "app/a.py", 100)  # > 5 lines apart
    
    groups = group_findings([f1, f2], near_dup_line_threshold=5)
    assert len(groups) == 2


def test_grouping_near_duplicate_lines():
    f1 = _make_finding("f1", "rule-sqli", "app/a.py", 10)
    f2 = _make_finding("f2", "rule-sqli", "app/a.py", 14)  # 4 lines apart (<= 5)
    
    groups = group_findings([f1, f2], near_dup_line_threshold=5)
    assert len(groups) == 1
    assert groups[0].source_finding_ids == ["f1", "f2"]
    assert len(groups[0].locations) == 2


def test_grouping_determinism_under_shuffle():
    f1 = _make_finding("f1", "rule-sqli", "app/a.py", 10)
    f2 = _make_finding("f2", "rule-sqli", "app/a.py", 12)
    f3 = _make_finding("f3", "rule-cmdi", "app/exec.py", 50, severity="critical")
    f4 = _make_finding("f4", "rule-xss", "app/view.py", 5, severity="low")

    original_findings = [f1, f2, f3, f4]
    groups_baseline = group_findings(original_findings)

    # Shuffle input list 5 times and check results are identical
    for seed in range(5):
        shuffled = list(original_findings)
        random.seed(seed)
        random.shuffle(shuffled)
        groups_shuffled = group_findings(shuffled)
        
        assert len(groups_shuffled) == len(groups_baseline)
        for g_base, g_shuf in zip(groups_baseline, groups_shuffled, strict=True):
            assert g_base.group_key == g_shuf.group_key
            assert g_base.source_finding_ids == g_shuf.source_finding_ids
            assert g_base.severity == g_shuf.severity
