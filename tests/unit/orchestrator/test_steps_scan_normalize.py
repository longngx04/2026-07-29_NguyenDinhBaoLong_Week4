"""Bước 1 và 2. Lệnh ngoài được tiêm vào, không mock."""

import json
import sys
from pathlib import Path

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import RunState, new_run
from project_sentinel.orchestrator.steps import StepFailure, step_normalize, step_scan


@pytest.fixture
def fake_scan_output(tmp_path):
    """Một báo cáo OpenGrep hợp lệ tối thiểu, dùng làm nguồn cho lệnh sao chép."""
    source = tmp_path / "opengrep.json"
    source.write_text(
        json.dumps({
            "results": [
                {
                    "check_id": "java.sqli",
                    "path": "benchmarks/targets/webgoat/src/Login.java",
                    "start": {"line": 42},
                    "extra": {"severity": "ERROR", "message": "SQLi"},
                }
            ],
            "errors": [],
        }),
        encoding="utf-8",
    )
    return source


def _context(tmp_path, scan_source):
    """Lệnh quét là một lệnh sao chép THẬT — nhanh, và vẫn là subprocess thật."""
    return RunContext.default(repo_root=tmp_path).replace(
        runs_dir=tmp_path / "runs",
        scan_command=[
            sys.executable,
            "-c",
            f"import shutil,sys; shutil.copy({str(scan_source)!r}, sys.argv[1])",
        ],
    )


def test_scan_writes_raw_json_into_the_run_directory(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    record = step_scan(new_run(ctx.runs_dir), ctx)

    assert (record.root / "raw.json").exists()
    assert record.state is RunState.SCANNING
    assert record.step("scan").status == "done"


def test_scan_records_the_finding_count(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    record = step_scan(new_run(ctx.runs_dir), ctx)
    assert record.step("scan").detail["raw_results"] == 1


def test_scan_failure_raises_step_failure(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output).replace(
        scan_command=[sys.executable, "-c", "import sys; sys.exit(3)"]
    )
    with pytest.raises(StepFailure) as excinfo:
        step_scan(new_run(ctx.runs_dir), ctx)
    assert "quét" in str(excinfo.value).lower() or "scan" in str(excinfo.value).lower()


def test_scan_rejects_output_that_is_not_a_valid_report(tmp_path, fake_scan_output):
    bad = tmp_path / "bad.json"
    bad.write_text("{khong phai json", encoding="utf-8")
    ctx = _context(tmp_path, bad)
    with pytest.raises(StepFailure):
        step_scan(new_run(ctx.runs_dir), ctx)


def test_normalize_produces_findings_json(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    record = step_scan(new_run(ctx.runs_dir), ctx)
    record = step_normalize(record, ctx)

    output = record.root / "findings.json"
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(data.get("findings"), list)
    assert record.step("normalize").status == "done"
    assert record.state is RunState.NORMALIZING


def test_normalize_records_the_normalised_count(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    record = step_normalize(step_scan(new_run(ctx.runs_dir), ctx), ctx)
    assert record.step("normalize").detail["findings"] >= 1


def test_normalize_without_raw_json_fails_clearly(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    with pytest.raises(StepFailure) as excinfo:
        step_normalize(new_run(ctx.runs_dir), ctx)
    assert "raw.json" in str(excinfo.value)


def test_every_step_writes_a_log_line(tmp_path, fake_scan_output):
    from project_sentinel.orchestrator.run_log import read_log

    ctx = _context(tmp_path, fake_scan_output)
    record = step_normalize(step_scan(new_run(ctx.runs_dir), ctx), ctx)
    steps_logged = {entry["step"] for entry in read_log(record.root)}
    assert {"scan", "normalize"} <= steps_logged


def test_context_never_prints_the_gateway_api_key(monkeypatch):
    """Khoá không được xuất hiện trong repr — traceback và log đều dùng repr."""
    monkeypatch.setenv("SENTINEL_GATEWAY_API_KEY", "sk-KHONG-DUOC-LO-0123456789")
    ctx = RunContext.default()
    assert ctx.gateway_api_key == "sk-KHONG-DUOC-LO-0123456789"  # vẫn dùng được
    assert "sk-KHONG-DUOC-LO" not in repr(ctx)
    assert "sk-KHONG-DUOC-LO" not in str(ctx)


def test_scan_command_override_rejects_a_shell_invocation(monkeypatch, caplog):
    """Biến môi trường không được biến thành đường chạy lệnh tùy ý."""
    monkeypatch.setenv(
        "SENTINEL_SCAN_COMMAND", "/bin/sh -c 'echo pwned'"
    )

    ctx = RunContext.default()

    assert "/bin/sh" not in ctx.scan_command
    assert ctx.scan_command == [str(ctx.repo_root / "scripts" / "scan-opengrep.sh")]
    assert "SENTINEL_SCAN_COMMAND" in caplog.text


def test_normalize_with_invalid_json_output_raises_step_failure(
    tmp_path, fake_scan_output
):
    """Runner chỉ bắt StepFailure — mọi lỗi của bước phải về đúng kiểu đó."""
    ctx = _context(tmp_path, fake_scan_output).replace(
        normalize_command=[
            sys.executable,
            "-c",
            'import sys; open(sys.argv[sys.argv.index("--output")+1],"w").write("{ hong")',
        ]
    )
    record = step_scan(new_run(ctx.runs_dir), ctx)
    with pytest.raises(StepFailure):
        step_normalize(record, ctx)


def test_scan_fallback_records_warning_and_detail(tmp_path):
    """Khi lệnh quét không sinh file, dùng fallback và ghi warn rõ ràng."""
    from project_sentinel.orchestrator.run_log import read_log

    fallback_file = tmp_path / "artifacts" / "raw" / "opengrep.json"
    fallback_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_file.write_text(
        json.dumps({
            "results": [
                {
                    "check_id": "test",
                    "path": "benchmarks/targets/webgoat/src/Login.java",
                }
            ],
            "errors": [],
        }),
        encoding="utf-8",
    )

    ctx = RunContext.default(repo_root=tmp_path).replace(
        runs_dir=tmp_path / "runs",
        scan_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
    )
    record = step_scan(new_run(ctx.runs_dir), ctx)
    assert record.step("scan").detail["used_fallback"] is True
    logs = read_log(record.root)
    assert any(
        e["level"] == "warn" and "dùng lại báo cáo cũ" in e["message"] for e in logs
    )


def test_scan_normal_path_marks_used_fallback_false(tmp_path, fake_scan_output):
    ctx = _context(tmp_path, fake_scan_output)
    record = step_scan(new_run(ctx.runs_dir), ctx)
    assert record.step("scan").detail["used_fallback"] is False


def test_run_command_logs_stdout_on_success(tmp_path, fake_scan_output):
    """Stdout của lệnh thành công phải được ghi lại vào log."""
    from project_sentinel.orchestrator.run_log import read_log

    ctx = _context(tmp_path, fake_scan_output).replace(
        normalize_command=[
            sys.executable,
            "-c",
            'import sys; open(sys.argv[sys.argv.index("--output")+1],"w").write(\'{"findings":[]}\'); print("Normalized 0 findings")',
        ]
    )
    record = step_scan(new_run(ctx.runs_dir), ctx)
    record = step_normalize(record, ctx)
    logs = read_log(record.root)
    assert any("Normalized 0 findings" in e["message"] for e in logs)


def test_the_real_scan_script_writes_where_the_orchestrator_asked_it_to():
    """`used_fallback: true` phải nghĩa là "đã dùng lại báo cáo cũ", không hơn.

    `step_scan` truyền `<run>/raw.json` làm argument cho `scripts/scan-opengrep.sh`,
    nhưng script bỏ qua argument đó và luôn ghi vào `artifacts/raw/opengrep.json`.
    Kết quả: mọi lần chạy đều rơi vào nhánh fallback và ghi `used_fallback: true`
    cho một báo cáo vừa quét xong vài giây trước. Timestamp chứng minh file là
    mới, còn provenance thì nói là cũ.
    """
    script = (
        Path(__file__).resolve().parents[3] / "scripts" / "scan-opengrep.sh"
    ).read_text(encoding="utf-8")

    assert 'report_path="${1:-' in script, (
        "script phải nhận đường dẫn output từ argument thứ nhất"
    )
    assert 'mv -f -- "$temporary_report" "$report_path"' in script
