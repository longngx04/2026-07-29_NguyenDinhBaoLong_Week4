"""Noi finding tinh voi endpoint runtime ma ZAP that su cham toi.

Doi chieu la thao tac TAT DINH, doc file, khong hoi LLM. Chinh vi vay ket qua
cua no du tin de ghi de truong reachability ma Agent tu khai.
"""

from pathlib import Path

import pytest

from project_sentinel.analysis.correlation import (
    STRENGTHS,
    correlate,
    extract_route,
    parse_gateway_access_log,
)

REPO = Path(__file__).resolve().parents[3]
LOG_FIXTURE = REPO / "tests/fixtures/dast/gateway-access-authenticated.log"


# ---------- parse_gateway_access_log ----------

def test_parses_method_path_and_query_from_a_real_log(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=GET "
        "path=/WebGoat/SqlInjection/attack5a query=account=x&op=1 status=200 "
        "bytes=12 rt=0.01\n"
        "2026-08-22T09:00:01+00:00 channel=dast method=GET "
        "path=/WebGoat/login query=- status=200 bytes=9 rt=0.01\n",
        encoding="utf-8",
    )
    result = parse_gateway_access_log(log)
    by_path = {item["path"]: item for item in result["endpoints"]}
    assert by_path["/WebGoat/SqlInjection/attack5a"]["params"] == ["account", "op"]
    assert by_path["/WebGoat/login"]["params"] == []


def test_non_dast_lines_are_ignored(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "nginx khoi dong\n"
        "2026-08-22T09:00:00+00:00 method=GET path=/WebGoat/x status=200 "
        "bytes=1 rt=0.01\n",
        encoding="utf-8",
    )
    assert parse_gateway_access_log(log)["endpoints"] == []


def test_blocked_requests_are_not_counted_as_reachable(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=GET "
        "path=/WebGoat/logout query=- status=403 bytes=0 rt=0.01\n",
        encoding="utf-8",
    )
    assert parse_gateway_access_log(log)["endpoints"] == [], (
        "403 nghia la Gateway chan, khong phai endpoint cham toi duoc"
    )


def test_a_missing_log_is_an_empty_map_not_a_crash(tmp_path):
    assert parse_gateway_access_log(tmp_path / "khong-co.log") == {"endpoints": []}


def test_the_real_fixture_log_parses():
    assert LOG_FIXTURE.is_file(), "Task 3 phai sinh fixture nay truoc"
    result = parse_gateway_access_log(LOG_FIXTURE)
    assert result["endpoints"], "Log that phai co it nhat mot endpoint"


# ---------- extract_route ----------

@pytest.fixture
def lesson(tmp_path):
    src = tmp_path / "src" / "Lesson.java"
    src.parent.mkdir(parents=True)
    src.write_text(
        '@RequestMapping("/SqlInjection")\n'
        'public class Lesson {\n'
        '  @PostMapping("/attack5a")\n'
        '  public void attack() {}\n'
        '}\n',
        encoding="utf-8",
    )
    return tmp_path


def test_class_mapping_is_prefixed_to_method_mapping(lesson):
    assert extract_route(lesson / "src" / "Lesson.java") == "/SqlInjection/attack5a"


def test_a_file_without_mapping_returns_none(tmp_path):
    plain = tmp_path / "Plain.java"
    plain.write_text("public class Plain { void x() {} }", encoding="utf-8")
    assert extract_route(plain) is None


def test_a_missing_file_returns_none_rather_than_raising(tmp_path):
    assert extract_route(tmp_path / "KhongCoThat.java") is None


# ---------- correlate ----------

def _endpoints(*paths):
    return {"endpoints": [{"method": "GET", "path": p, "params": []} for p in paths]}


def test_route_reached_by_zap_is_reachable(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    out = correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
                    project_root=lesson)
    evidence = out[0]["runtime_evidence"]
    assert evidence["route"] == "/SqlInjection/attack5a"
    assert evidence["strength"] == "reachable"


def test_route_zap_never_reached(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    out = correlate(findings, _endpoints("/WebGoat/login"), project_root=lesson)
    assert out[0]["runtime_evidence"]["strength"] == "route_known_not_reached"


def test_no_route_when_the_file_declares_none(tmp_path):
    plain = tmp_path / "Plain.java"
    plain.write_text("public class Plain {}", encoding="utf-8")
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "Plain.java", "line": 1}]
    out = correlate(findings, _endpoints(), project_root=tmp_path)
    assert out[0]["runtime_evidence"]["strength"] == "no_route"


def test_a_zap_alert_on_the_same_route_upgrades_to_alerted(lesson):
    findings = [
        {"id": "opengrep-001", "tool": "opengrep",
         "file_or_url": "src/Lesson.java", "line": 4},
        {"id": "zap-10021-abc", "tool": "zap", "instances": [
            {"url": "http://gateway-dast:8081/WebGoat/SqlInjection/attack5a",
             "method": "GET", "param": ""}]},
    ]
    out = correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
                    project_root=lesson)
    evidence = next(f for f in out if f["id"] == "opengrep-001")["runtime_evidence"]
    assert evidence["strength"] == "reachable_and_alerted"
    assert evidence["dast_alerts"] == ["zap-10021-abc"]


def test_zap_findings_get_no_runtime_evidence_block(lesson):
    out = correlate([{"id": "zap-1", "tool": "zap", "instances": []}],
                    _endpoints(), project_root=lesson)
    assert "runtime_evidence" not in out[0], (
        "Finding dong DA LA bang chung runtime; gan them la vong lap vo nghia"
    )


def test_the_input_list_is_not_mutated(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
              project_root=lesson)
    assert "runtime_evidence" not in findings[0]


def test_strengths_are_ordered_weakest_first():
    assert STRENGTHS[0] == "no_route"
    assert STRENGTHS[-1] == "reachable_and_alerted"
