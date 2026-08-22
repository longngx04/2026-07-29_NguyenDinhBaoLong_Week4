"""Static contract for the real ZAP baseline wrapper."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts/scan-zap.sh"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_zap_targets_only_the_dast_gateway():
    text = _script()
    assert "http://gateway-dast:8081/WebGoat/login" in text
    assert "http://webgoat:8080" not in text


def test_zap_report_path_is_relative_to_its_work_directory():
    text = _script()
    assert '-J "raw/$report_name"' in text
    assert '-J "/zap/wrk/' not in text


def test_gateway_evidence_must_come_from_the_current_scan_target():
    text = _script()
    assert 'logs --no-color --since "$scan_started_at" gateway-dast' in text
    assert "path=/WebGoat/login" in text


def test_zap_wrapper_runs_baseline_not_active_scan():
    text = _script()
    assert "zap-baseline.py" in text
    assert "zap-full-scan.py" not in text
    assert "--autooff" in text, "ZAP 2.17 Automation Framework ignores -I exit semantics"
