"""
Command-line interface for Project Sentinel.
Provides commands:
- analyze: run end-to-end security analysis pipeline
- validate: validate output JSONL records against schema
- probe: gửi một request kiểm thử an toàn qua Gateway
- demo: chạy kịch bản demo tầng guardrails
- run: chạy luồng orchestrator chín bước
- runs: liệt kê các lần chạy orchestrator
- approve: ghi quyết định rồi tiếp tục một lần chạy
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from project_sentinel.commands import (
    cmd_analyze,
    cmd_approve,
    cmd_demo,
    cmd_probe,
    cmd_run,
    cmd_runs,
    cmd_validate,
)

# Bảng điều phối. Thêm một lệnh con nghĩa là thêm một dòng ở đây và một file
# trong `commands/`, không phải thêm một nhánh nữa vào một hàm đã quá dài.
COMMAND_HANDLERS = {
    "validate": cmd_validate,
    "demo": cmd_demo,
    "runs": cmd_runs,
    "run": cmd_run,
    "approve": cmd_approve,
    "probe": cmd_probe,
    "analyze": cmd_analyze,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # analyze sub-command
    analyze_parser = subparsers.add_parser("analyze", help="Run end-to-end security analysis pipeline")
    analyze_parser.add_argument("--input", type=Path, default=Path("artifacts/normalized/findings.json"), help="Input normalized findings JSON")
    analyze_parser.add_argument("--output", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Output security analysis JSONL")
    analyze_parser.add_argument("--summary", type=Path, default=Path("artifacts/analysis/run-summary.json"), help="Output run summary JSON")
    analyze_parser.add_argument("--target-root", type=Path, default=None, help="Target project root directory")
    analyze_parser.add_argument("--knowledge-dir", type=Path, default=Path("data/knowledge-base"), help="Knowledge base directory")

    # validate sub-command
    validate_parser = subparsers.add_parser("validate", help="Validate output JSONL file against JSON schema")
    validate_parser.add_argument("--input", type=Path, default=Path("artifacts/analysis/security-analysis.jsonl"), help="Input JSONL file")
    validate_parser.add_argument("--schema", type=Path, default=Path("schemas/security-analysis-record.schema.json"), help="JSON schema path")

    # probe sub-command
    probe_parser = subparsers.add_parser("probe", help="Gửi một request kiểm thử an toàn qua Gateway")
    probe_parser.add_argument("--method", choices=["GET", "POST"], default="GET")
    probe_parser.add_argument("--path", type=str, default="/WebGoat/actuator/health")
    probe_parser.add_argument(
        "--payload-kind",
        choices=["long_string", "special_chars", "empty_value", "wrong_type"],
        default=None,
    )
    probe_parser.add_argument("--allowlist", type=Path, default=Path("configs/gateway/endpoint-allowlist.json"))
    probe_parser.add_argument("--log", type=Path, default=Path("artifacts/gateway/requests.log.jsonl"))

    run_parser = subparsers.add_parser("run", help="Chạy toàn bộ luồng chín bước")
    run_parser.add_argument(
        "--yes",
        action="store_true",
        help="Tự động phê duyệt (chỉ dùng cho môi trường tự động)",
    )

    run_parser.add_argument(
        "--probe-method",
        choices=["GET", "POST"],
        help="Chỉ định method cho bước kiểm chứng thay vì để agent chọn",
    )
    run_parser.add_argument(
        "--probe-path",
        type=str,
        help="Chỉ định path cho bước kiểm chứng; phải có trong allowlist Gateway",
    )
    run_parser.add_argument(
        "--probe-payload-kind",
        choices=["long_string", "special_chars", "empty_value", "wrong_type"],
        default="empty_value",
        help="Loại payload lành tính đi kèm probe do người vận hành chỉ định",
    )

    subparsers.add_parser("runs", help="Liệt kê các lần chạy")

    approve_parser = subparsers.add_parser(
        "approve", help="Quyết định phê duyệt cho một lần chạy"
    )
    approve_parser.add_argument("run_id", type=str)
    approve_parser.add_argument(
        "--decision", choices=["approve", "reject"], required=True
    )

    # demo sub-command
    demo_parser = subparsers.add_parser("demo", help="Chạy kịch bản demo tầng guardrails")
    demo_parser.add_argument(
        "--auto",
        action="store_true",
        help="Trả lời sẵn phần phê duyệt, không dừng chờ nhập",
    )

    args = parser.parse_args(argv)

    # Không có lệnh con thì mặc định là analyze.
    if args.command is None:
        args = parser.parse_args(["analyze"] + (argv if argv else []))

    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.error(f"Lệnh không được hỗ trợ: {args.command}")
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
