"""Dieu phoi bang chung: finding tinh doc source, finding dong dung chinh alert.

Yeu cau quan trong nhat: duong CU khong doi hanh vi (AGENTS.md §2.1).
"""

from pathlib import Path

from project_sentinel.analysis.evidence import (
    evidence_for_finding,
    extract_source_window,
)

REPO = Path(__file__).resolve().parents[3]
TARGET = REPO / "benchmarks" / "targets" / "webgoat"
JAVA = (
    "benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat"
    "/container/WebSecurityConfig.java"
)


def test_static_finding_takes_the_unchanged_source_path():
    finding = {"id": "opengrep-001", "tool": "opengrep",
               "file_or_url": JAVA, "line": 61}
    routed = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    direct = extract_source_window(REPO, TARGET, JAVA, 61)
    assert routed == direct, "Duong cu phai cho ket qua y het khi goi thang"


def test_dast_finding_uses_its_own_alert_content():
    finding = {
        "id": "zap-10021-abc", "tool": "zap",
        "file_or_url": "http://gateway-dast:8081/WebGoat/login",
        "line": 0, "title": "Thieu CSP",
        "instances": [{"url": "http://gateway-dast:8081/WebGoat/login",
                       "method": "GET", "param": "username"}],
        "instances_total": 7,
    }
    evidence = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    assert evidence.error is None
    assert "GET" in evidence.content
    assert "username" in evidence.content
    assert "7" in evidence.content, "Phai noi tong so instance that"


def test_line_zero_is_not_treated_as_a_source_location():
    # zap_normalizer dat line: 0, khong phai None. Dieu phoi bang line > 0.
    finding = {"id": "zap-1", "tool": "zap", "file_or_url": "http://x/a",
               "line": 0, "instances": [], "instances_total": 0}
    evidence = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    assert evidence.error
