"""So lieu phai noi ro hai loai hat finding, khong tron im lang.

DAST gop theo loai alert nen mot finding ZAP khong cung don vi voi mot
finding OpenGrep. findings_total ma dung mot minh la con so gay hieu nham.
"""

import json

from project_sentinel.orchestrator.metrics import collect_metrics
from project_sentinel.orchestrator.state import new_run


def _write(root, findings, log_lines=None):
    (root / "findings.json").write_text(
        json.dumps({"count": len(findings), "findings": findings}), encoding="utf-8"
    )
    if log_lines is not None:
        (root / "gateway-access.log").write_text(
            "\n".join(log_lines) + "\n", encoding="utf-8"
        )


def test_findings_are_counted_per_tool(tmp_path):
    record = new_run(tmp_path / "runs")
    _write(
        record.root,
        [
            {"id": "opengrep-001", "tool": "opengrep"},
            {"id": "opengrep-002", "tool": "opengrep"},
            {"id": "zap-10021-a", "tool": "zap", "instances": [{}],
             "instances_total": 9},
        ],
        log_lines=[
            "2026-08-22T09:00:00+00:00 channel=dast method=GET "
            "path=/WebGoat/login query=- status=200 bytes=9 rt=0.01"
        ],
    )
    metrics = collect_metrics(record)
    assert metrics["findings_total"] == 3, "Nghia cu giu nguyen"
    assert metrics["findings_by_tool"] == {"opengrep": 2, "zap": 1}
    assert metrics["dast"]["alerts_total"] == 1
    assert metrics["dast"]["instances_total"] == 9
    assert metrics["dast"]["endpoints_discovered"] == 1


def test_a_run_without_dast_reports_zeros_not_missing_keys(tmp_path):
    record = new_run(tmp_path / "runs")
    _write(record.root, [{"id": "opengrep-001", "tool": "opengrep"}])
    metrics = collect_metrics(record)
    assert metrics["dast"] == {
        "endpoints_discovered": 0, "alerts_total": 0, "instances_total": 0
    }
    assert metrics["findings_by_tool"] == {"opengrep": 1}
