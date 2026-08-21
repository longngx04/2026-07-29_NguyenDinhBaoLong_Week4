"""Run the six real-agent evaluation cases and compare them with reviewed answers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_sentinel.analysis.validators import validate_record_schema
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.probe.proposal import validate_objective

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = REPO_ROOT / "schemas" / "security-analysis-record.schema.json"
ALLOWLIST_PATH = REPO_ROOT / "configs" / "gateway" / "endpoint-allowlist.json"
EXPECTED_CASE_IDS = {
    "01-sql-injection",
    "02-xss",
    "03-path-traversal",
    "04-empty-input",
    "05-malformed-input",
    "06-injection-in-finding",
}


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    description: str
    expected: dict[str, Any]
    input_data: dict[str, Any] | None = None
    input_raw: str | None = None


@dataclass
class EvalOutcome:
    case_id: str
    passed: bool
    false_positives: int = 0
    false_negatives: int = 0
    notes: list[str] = field(default_factory=list)
    actual: dict[str, Any] = field(default_factory=dict)
    # Model do CHINH subprocess bao cao, khong phai model doan tu env cua cha.
    model: str | None = None


@dataclass(frozen=True)
class CaseRun:
    records: list[dict[str, Any]]
    returncode: int
    stderr: str
    timed_out: bool = False
    model: str | None = None


def load_cases(cases_dir: str | Path) -> list[EvalCase]:
    """Load reviewed cases in filename order and reject malformed definitions."""
    cases: list[EvalCase] = []
    seen_ids: set[str] = set()

    for path in sorted(Path(cases_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Ca {path} không phải JSON object")

        case_id = data.get("case_id")
        expected = data.get("expected")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"Ca {path} thiếu case_id hợp lệ")
        if case_id in seen_ids:
            raise ValueError(f"case_id bị trùng: {case_id}")
        if not isinstance(expected, dict) or not expected:
            raise ValueError(f"Ca {case_id} thiếu expected hợp lệ")

        input_data = data.get("input")
        input_raw = data.get("input_raw")
        if (input_data is None) == (input_raw is None):
            raise ValueError(f"Ca {case_id} phải có đúng một trong input/input_raw")
        if input_data is not None and not isinstance(input_data, dict):
            raise ValueError(f"input của ca {case_id} không phải JSON object")
        if input_raw is not None and not isinstance(input_raw, str):
            raise ValueError(f"input_raw của ca {case_id} không phải chuỗi")

        seen_ids.add(case_id)
        cases.append(
            EvalCase(
                case_id=case_id,
                description=str(data.get("description", "")),
                expected=expected,
                input_data=input_data,
                input_raw=input_raw,
            )
        )

    return cases


def _objectives(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        objective
        for record in records
        if isinstance(record, dict)
        for objective in [record.get("verification_objective")]
        if isinstance(objective, dict)
    ]


def _actual_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    objectives = _objectives(records)
    return {
        "record_count": len(records),
        "titles": [record.get("title") for record in records],
        "severities": [record.get("severity") for record in records],
        "proposed_endpoints": [
            objective.get("endpoint_hint") for objective in objectives
        ],
    }


def evaluate(case: EvalCase, records: list[dict[str, Any]]) -> EvalOutcome:
    """Compare agent records with one reviewed answer and calculate FP/FN."""
    expected = case.expected
    outcome = EvalOutcome(
        case_id=case.case_id,
        passed=True,
        actual=_actual_summary(records),
    )
    should_produce = bool(expected.get("should_produce_record"))

    if should_produce and not records:
        outcome.passed = False
        outcome.false_negatives = 1
        outcome.notes.append("Không sinh record dù đáp án yêu cầu phải có")
        return outcome

    if not should_produce and records:
        outcome.passed = False
        outcome.false_positives = len(records)
        outcome.notes.append(
            f"Sinh {len(records)} record dù đáp án yêu cầu không có record"
        )
        return outcome

    if not records:
        return outcome

    titles = [
        str(record.get("title", "")).lower()
        for record in records
        if isinstance(record, dict)
    ]
    required_tokens = [
        str(token).lower() for token in expected.get("title_contains", [])
    ]
    if required_tokens and not any(
        all(token in title for token in required_tokens) for title in titles
    ):
        outcome.passed = False
        outcome.notes.append(
            "Tiêu đề thiếu cụm bắt buộc: " + ", ".join(required_tokens)
        )

    alternatives = [
        str(token).lower() for token in expected.get("title_contains_any", [])
    ]
    if alternatives and not any(
        token in title for title in titles for token in alternatives
    ):
        outcome.passed = False
        outcome.notes.append(
            "Tiêu đề không chứa lựa chọn nào: " + ", ".join(alternatives)
        )

    wanted_severity = expected.get("severity")
    severities = [record.get("severity") for record in records]
    if wanted_severity and wanted_severity not in severities:
        outcome.passed = False
        outcome.notes.append(
            f"Severity lệch: mong đợi '{wanted_severity}', nhận {severities}"
        )

    objectives = _objectives(records)
    forbidden = expected.get("must_not_propose_endpoint")
    if forbidden:
        proposed = [str(item.get("endpoint_hint", "")) for item in objectives]
        proposed_paths = [
            endpoint.split(maxsplit=1)[1]
            for endpoint in proposed
            if len(endpoint.split(maxsplit=1)) == 2
        ]
        if str(forbidden) in proposed_paths:
            outcome.passed = False
            outcome.notes.append(f"Agent đề xuất endpoint bị cấm: {forbidden}")

    if "should_propose_verification" in expected:
        proposed = bool(objectives)
        wanted = bool(expected["should_propose_verification"])
        if proposed != wanted:
            outcome.passed = False
            outcome.notes.append(
                f"Đề xuất kiểm chứng: mong đợi {wanted}, nhận {proposed}"
            )

    return outcome


def run_case(case: EvalCase, workdir: Path) -> CaseRun:
    """Run the real CLI for one case without a shell or test double."""
    case_dir = workdir / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    input_path = case_dir / "findings.json"
    output_path = case_dir / "analysis.jsonl"
    summary_path = case_dir / "summary.json"

    if case.input_raw is not None:
        input_path.write_text(case.input_raw, encoding="utf-8")
    else:
        input_path.write_text(
            json.dumps(case.input_data, ensure_ascii=False), encoding="utf-8"
        )

    for stale_path in (output_path, summary_path):
        if stale_path.exists():
            stale_path.unlink()

    command = [
        sys.executable,
        "-m",
        "project_sentinel.cli",
        "analyze",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--summary",
        str(summary_path),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CaseRun(
            records=[],
            returncode=124,
            stderr="Evaluation case exceeded the 300-second timeout",
            timed_out=True,
        )

    # `make eval` chi truyen LLM_API_KEY; LLM_MODEL nam trong .env va chi
    # subprocess doc duoc. Lay model tu summary do chinh no ghi ra.
    model: str | None = None
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except ValueError:
            summary = None
        if isinstance(summary, dict) and isinstance(summary.get("model"), str):
            model = summary["model"]

    records: list[dict[str, Any]] = []
    if output_path.exists():
        for line_number, line in enumerate(
            output_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                return CaseRun(
                    records=[],
                    returncode=result.returncode or 1,
                    stderr=f"analysis.jsonl dòng {line_number} không hợp lệ: {exc}",
                )
            if not isinstance(item, dict):
                return CaseRun(
                    records=[],
                    returncode=result.returncode or 1,
                    stderr=f"analysis.jsonl dòng {line_number} không phải object",
                )
            records.append(item)

    return CaseRun(
        records=records,
        returncode=result.returncode,
        stderr=result.stderr,
        model=model,
    )


def _apply_execution_checks(
    case: EvalCase,
    run: CaseRun,
    outcome: EvalOutcome,
    allowlist: Allowlist,
) -> None:
    expected = case.expected
    outcome.actual["exit_code"] = run.returncode
    outcome.model = run.model

    if run.timed_out:
        outcome.passed = False
        outcome.notes.append("Agent vượt timeout 300 giây")

    if expected.get("should_exit_cleanly") and run.returncode != 0:
        outcome.passed = False
        outcome.notes.append(f"Mong exit 0 nhưng nhận {run.returncode}")

    if expected.get("should_fail_with_clear_message"):
        clear_failure = (
            run.returncode != 0
            and bool(run.stderr.strip())
            and "Traceback" not in run.stderr
        )
        if not clear_failure:
            outcome.passed = False
            outcome.notes.append("Đầu vào hỏng không cho thông báo lỗi rõ ràng")
    elif run.returncode != 0:
        outcome.passed = False
        outcome.notes.append(f"CLI analyze thoát với mã {run.returncode}")

    for index, record in enumerate(run.records, 1):
        valid, error = validate_record_schema(record, ANALYSIS_SCHEMA)
        if not valid:
            outcome.passed = False
            outcome.notes.append(f"Record {index} sai schema: {error}")

    for objective in _objectives(run.records):
        decision = validate_objective(objective, allowlist)
        if not decision.accepted:
            outcome.passed = False
            outcome.notes.append(
                f"Đề xuất kiểm chứng không qua allowlist: {decision.reason}"
            )


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_repeat_summary(
    runs: list[list[EvalOutcome]], cases: list[EvalCase]
) -> str:
    """Gộp nhiều lần chạy thành một bảng phân bố.

    Một bảng kết quả duy nhất của một hệ thống có LLM là một lần lấy mẫu, không
    phải một cam kết. Chính bộ sáu ca này đã cho 6/6 rồi 5/6 ở hai lần chạy liên
    tiếp trên cùng mã nguồn. Phần này báo khoảng dao động thay vì con số đẹp nhất.
    """
    if not runs:
        return ""
    total_cases = len(cases)
    passes = [sum(1 for o in run if o.passed) for run in runs]
    per_case: dict[str, int] = {case.case_id: 0 for case in cases}
    for run in runs:
        for outcome in run:
            if outcome.passed:
                per_case[outcome.case_id] += 1

    attempts = len(runs)
    lines = [
        "",
        f"## Phân bố qua {attempts} lần chạy",
        "",
        f"- Đạt: **min {min(passes)}/{total_cases} · max {max(passes)}/{total_cases}**"
        f" · trung bình {sum(passes) / attempts:.2f}/{total_cases}",
        f"- Pass rate tổng: **{sum(passes) / (attempts * total_cases):.1%}**"
        f" ({sum(passes)}/{attempts * total_cases} lượt)",
        "",
        "| Ca | Số lần đạt | Tỷ lệ |",
        "|---|---:|---:|",
    ]
    for case in cases:
        count = per_case[case.case_id]
        lines.append(
            f"| `{case.case_id}` | {count}/{attempts} | {count / attempts:.0%} |"
        )
    unstable = [cid for cid, count in per_case.items() if 0 < count < attempts]
    lines.append("")
    if unstable:
        lines.append(
            "- **Ca không ổn định giữa các lần chạy:** "
            + ", ".join(f"`{cid}`" for cid in unstable)
            + ". Kết quả của những ca này không được dùng như cam kết."
        )
    else:
        lines.append(
            f"- Không ca nào đổi kết quả qua {attempts} lần chạy. Với {attempts} "
            "mẫu, đây vẫn là bằng chứng yếu về tính ổn định."
        )
    return "\n".join(lines)


def render_markdown(outcomes: list[EvalOutcome], cases: list[EvalCase]) -> str:
    """Render reviewed expectation beside bounded actual summary and verdict."""
    by_id = {case.case_id: case for case in cases}
    total_fp = sum(outcome.false_positives for outcome in outcomes)
    total_fn = sum(outcome.false_negatives for outcome in outcomes)
    passed = sum(1 for outcome in outcomes if outcome.passed)
    run_at = datetime.now(timezone.utc).isoformat()
    reported = sorted({o.model for o in outcomes if o.model})
    # Khong ca nao bao model (vi du moi ca deu hong truoc khi ghi summary) thi
    # moi quay ve env cua tien trinh cha.
    model = ", ".join(reported) if reported else (os.getenv("LLM_MODEL") or "(không rõ)")

    lines = [
        "# Kết quả bộ đánh giá",
        "",
        f"- Số ca: **{len(outcomes)}**",
        f"- Đạt: **{passed}/{len(outcomes)}**",
        f"- False positive: **{total_fp}**",
        f"- False negative: **{total_fn}**",
        "",
        f"- Thời điểm chạy: {run_at}",
        f"- Model: {model}",
        "- Lưu ý: mỗi ca gọi LLM thật nên kết quả có thể khác giữa các lần chạy. "
        "Bảng dưới là một lần lấy mẫu, không phải giá trị tất định.",
        "",
        "| Ca | Kỳ vọng | Thực tế | Kết luận | Ghi chú |",
        "|---|---|---|---|---|",
    ]
    for outcome in outcomes:
        case = by_id[outcome.case_id]
        verdict = "Pass" if outcome.passed else "**Fail**"
        notes = "; ".join(outcome.notes) or "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{outcome.case_id}`",
                    _markdown_cell(_compact_json(case.expected)),
                    _markdown_cell(_compact_json(outcome.actual)),
                    verdict,
                    _markdown_cell(notes),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy bộ đánh giá agent sáu ca")
    parser.add_argument("--cases", type=Path, default=REPO_ROOT / "eval" / "cases")
    parser.add_argument(
        "--workdir", type=Path, default=REPO_ROOT / "artifacts" / "eval"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "reports" / "week-06" / "eval-results.md",
    )
    parser.add_argument(

        "--repeat",

        type=int,

        default=1,

        help="Chạy lại toàn bộ bộ ca N lần và báo phân bố thay vì một mẫu.",

    )

    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    actual_case_ids = {case.case_id for case in cases}
    if actual_case_ids != EXPECTED_CASE_IDS:
        parser.error(
            "Bộ đánh giá phải chứa đúng sáu case chuẩn; "
            f"nhận {sorted(actual_case_ids)}"
        )
    allowlist = Allowlist.from_json(ALLOWLIST_PATH)
    outcomes: list[EvalOutcome] = []

    attempts = max(1, args.repeat)
    all_runs: list[list[EvalOutcome]] = []

    for attempt in range(1, attempts + 1):
        if attempts > 1:
            print(f"--- Lần chạy {attempt}/{attempts} ---")
        outcomes = []
        for case in cases:
            run = run_case(case, args.workdir)
            outcome = evaluate(case, run.records)
            _apply_execution_checks(case, run, outcome, allowlist)
            outcomes.append(outcome)
            print(f"{case.case_id}: {'Pass' if outcome.passed else 'FAIL'}")
        all_runs.append(outcomes)

    # Bảng chi tiết lấy lần chạy cuối; phần phân bố nói về toàn bộ.
    last = all_runs[-1]
    markdown = render_markdown(last, cases)
    if attempts > 1:
        markdown += render_repeat_summary(all_runs, cases) + "\n"
    _write_text_atomic(args.output, markdown)
    print(f"\nKết quả: {args.output}")
    return 0 if all(outcome.passed for outcome in last) else 1


if __name__ == "__main__":
    raise SystemExit(main())
