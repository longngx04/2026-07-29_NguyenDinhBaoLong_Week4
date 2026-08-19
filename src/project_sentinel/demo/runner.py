"""Chạy tuần tự bảy bước demo và kết luận đạt hay không đạt.

Hai chế độ dùng chung một đường code: chế độ mặc định hỏi người vận hành qua
`prompt_cli`, chế độ `--auto` đưa sẵn câu trả lời vào đúng tham số `input_fn`
mà hàm đó vốn đã nhận.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from project_sentinel.demo.guardrails import (
    REPO_ROOT,
    StepResult,
    load_allowlist,
    scripted_answers,
    step_approve,
    step_forged_tag,
    step_injection_scan,
    step_preflight,
    step_redaction_to_llm,
    step_redaction_to_log,
    step_reject,
)

DEMO_LOG_PATH = REPO_ROOT / "artifacts" / "demo" / "requests.log.jsonl"
API_KEY_ENV = "SENTINEL_GATEWAY_API_KEY"

_RULE = "─" * 68


def _render(index: int, step: StepResult, out: Callable[[str], None]) -> None:
    out("")
    out(_RULE)
    out(f"§{index}  {step.title.upper()}")
    out(_RULE)
    for line in step.lines:
        out(f"  {line}")
    out("  " + ("[ĐẠT]" if step.passed else "[KHÔNG ĐẠT]"))


def run_demo(
    *,
    auto: bool = False,
    out: Callable[[str], None] = print,
    input_fn: Callable[[str], str] = input,
) -> int:
    """Chạy demo, trả 0 nếu mọi bước đạt và 1 nếu có bước không đạt."""
    api_key = os.environ.get(API_KEY_ENV, "")
    if not api_key:
        out(f"Thiếu {API_KEY_ENV}. Đặt biến này trong .env rồi chạy lại.")
        return 2

    out("")
    out("PROJECT SENTINEL — DEMO GUARDRAILS")
    out("Chế độ: " + ("tự động (--auto)" if auto else "tương tác — bạn sẽ tự duyệt"))

    try:
        preflight = step_preflight(api_key)
    except Exception as exc:  # hạ tầng chưa sẵn sàng
        out("")
        out(f"Không kết nối được Gateway: {exc}")
        out("Chạy `make gateway-up` rồi thử lại. Demo cần Gateway và WebGoat thật.")
        return 2

    _render(0, preflight, out)
    if not preflight.passed:
        out("")
        out("Gateway chưa sẵn sàng. Chạy `make gateway-up` rồi thử lại.")
        return 2

    DEMO_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_path: Path = DEMO_LOG_PATH

    reject_input = scripted_answers(["reject"]) if auto else input_fn
    approve_input = scripted_answers(["approve"]) if auto else input_fn
    allowlist = load_allowlist()

    steps = [
        step_injection_scan(),
        step_forged_tag(),
        step_redaction_to_llm(),
        step_redaction_to_log(log_path.with_name("canary.log.jsonl")),
        step_reject(api_key, allowlist, log_path, input_fn=reject_input, output_fn=out),
        step_approve(api_key, allowlist, log_path, input_fn=approve_input, output_fn=out),
    ]

    for index, step in enumerate(steps, start=1):
        _render(index, step, out)

    every_step = [preflight, *steps]
    passed = sum(1 for step in every_step if step.passed)
    failed = len(every_step) - passed

    out("")
    out(_RULE)
    out(f"TỔNG KẾT: {passed} đạt / {failed} không đạt")
    out(_RULE)
    out("")
    return 0 if failed == 0 else 1
