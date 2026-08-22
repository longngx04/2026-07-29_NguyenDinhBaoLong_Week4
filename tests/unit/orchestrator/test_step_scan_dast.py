"""Nhanh DAST trong step_scan.

SAST la xuong song: DAST hong thi buoc van xong. May dev khong Docker van
phai chay duoc run. Test dung script that trong tmp_path, khong mock.
"""

import json
import stat

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run
from project_sentinel.orchestrator.steps.ingest import (
    _normalise_finding_fields,
    step_scan,
)

RAW = {"version": "1.0", "results": [], "errors": []}


def _script(path, body):
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.fixture
def ctx_and_record(tmp_path):
    record = new_run(tmp_path / "runs")
    scan = _script(
        tmp_path / "scan.sh", f"printf '%s' '{json.dumps(RAW)}' > \"$1\"\n"
    )
    ctx = RunContext.default(tmp_path).replace(scan_command=[scan])
    return ctx, record


def test_dast_success_is_recorded_as_done(tmp_path, ctx_and_record):
    ctx, record = ctx_and_record
    dast = _script(
        tmp_path / "dast.sh",
        'printf \'{"site":[]}\' > "$1"\nprintf \'log\\n\' > "$2"\n',
    )
    result = step_scan(record, ctx.replace(dast_command=[dast]))
    assert result.step("scan").detail["dast"] == "done"
    assert (record.root / "zap-alerts.json").exists()
    assert (record.root / "gateway-access.log").exists()


def test_dast_failure_does_not_fail_the_scan_step(tmp_path, ctx_and_record):
    ctx, record = ctx_and_record
    dast = _script(tmp_path / "dast.sh", 'echo "khong co docker" >&2\nexit 127\n')
    result = step_scan(record, ctx.replace(dast_command=[dast]))
    assert result.step("scan").status == "done", "SAST xong thi buoc phai xong"
    assert result.step("scan").detail["dast"] == "skipped"
    assert result.step("scan").detail["dast_reason"]
    assert (record.root / "raw.json").exists(), "raw.json van phai ra"


def test_no_dast_command_means_skipped_not_error(ctx_and_record):
    ctx, record = ctx_and_record
    result = step_scan(record, ctx.replace(dast_command=[]))
    assert result.step("scan").status == "done"
    assert result.step("scan").detail["dast"] == "skipped"


def test_cwe_and_owasp_are_normalised_to_lists_after_merging(tmp_path):
    """Hai normalizer cho hai hinh dang; sau khi tron chi duoc con mot.

    zap_normalizer cho cwe: ["CWE-693"], normalizer.py cua OpenGrep cho gia
    tri vo huong tu metadata. De ca hai vao findings.json thi moi thu doc no
    ve sau phai xu ly hai truong hop — do la no ky sinh, khong phai tinh nang.
    """
    findings = [
        {"id": "opengrep-001", "tool": "opengrep", "cwe": "CWE-89", "owasp": None},
        {"id": "zap-1", "tool": "zap", "cwe": ["CWE-693"], "owasp": []},
        {"id": "opengrep-002", "tool": "opengrep", "cwe": None, "owasp": ""},
    ]
    _normalise_finding_fields(findings)
    assert findings[0]["cwe"] == ["CWE-89"]
    assert findings[0]["owasp"] == []
    assert findings[1]["cwe"] == ["CWE-693"]
    assert findings[2]["cwe"] == []
    assert findings[2]["owasp"] == []
    assert json.dumps(findings)  # van serialise duoc
