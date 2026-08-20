# Worklog — Plan 3 Task 8: orchestrator runner

**Ngày:** 2026-08-20 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/orchestrator-runner` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 8`

---

## 1. Tóm tắt

Đã tạo runner nối chín bước orchestrator thành hai phase có thể dừng và tiếp tục từ trạng thái trên đĩa. Runner phục vụ CLI Task 9 và web Plan 4 bằng cùng API `start_run`/`resume_run`, đồng thời chuyển lỗi bước thành trạng thái `FAILED` có thể đọc lại. Kết quả cuối là 14 test runner, 104 test orchestrator và 414 test không LLM/live Gateway đều xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Điều phối thứ tự chín bước, lưu `state.json` sau từng bước, dừng tại cổng duyệt và chạy tiếp phase hai khi có quyết định.
- **Nằm ở đâu trong luồng:** Nằm trên các hàm `step_*`; CLI và web gọi runner thay vì tự nối từng bước.
- **Không có nó thì hỏng gì:** Mỗi giao diện sẽ phải tự điều phối, lỗi có thể thoát khỏi tiến trình nền, trạng thái có thể mất hoặc một request đã hoàn tất có thể bị gửi lại.
- **Ngoài phạm vi (cố ý không làm):** Chưa thêm lệnh CLI `run`/`approve` (Task 9), chưa chạy một happy path dùng LLM và Gateway thật vì đó là integration của task kế tiếp.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/runner.py` | Tạo | Thêm hai phase, `start_run`, `resume_run`, bắt lỗi có tên loại ngoại lệ, redaction, lưu state, kiểm tra run ID, chống resume lặp và log lý do khi resume không làm gì. | Đây là deliverable chính của Task 8. |
| `src/project_sentinel/orchestrator/__init__.py` | Sửa | Export API công khai của orchestrator. | CLI và web cần import từ một bề mặt ổn định. |
| `tests/unit/orchestrator/test_runner.py` | Tạo | Thêm 14 test cho lỗi, persistence, redaction, pause/resume, dấu vết no-op, tên ngoại lệ, path traversal, idempotency và trạng thái từ chối. | Chứng minh hợp đồng runner và các nhánh bảo mật. |
| `worklog/2026-08-20-plan3-task8-runner.md` | Tạo | Ghi phạm vi, thiết kế và output kiểm chứng thật. | Bắt buộc theo `AGENTS.md`. |

**`git diff --stat`:**

```text
 src/project_sentinel/orchestrator/__init__.py |  25 ++++
 src/project_sentinel/orchestrator/runner.py   | 150 ++++++++++++++++++++
 tests/unit/orchestrator/test_runner.py        | 188 ++++++++++++++++++++++++++
 worklog/2026-08-20-plan3-task8-runner.md      | 183 +++++++++++++++++++++++++
 4 files changed, 546 insertions(+)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** `PHASE_ONE` chạy scan đến approval; `PHASE_TWO` chạy probe đến finalize. `_execute` gọi tuần tự, lưu state sau mỗi bước và bắt cả `StepFailure` lẫn lỗi bất ngờ; lỗi bất ngờ giữ tên loại rồi toàn bộ thông điệp được redact trước khi vào log/state. `resume_run` chỉ tiếp tục một run `AWAITING_APPROVAL` có `decision.json`, từ chối run ID sai định dạng và trả nguyên run terminal để không gửi lại request. Mọi nhánh trả sớm sau khi đã nạp run đều ghi lý do “Bỏ qua resume” vào `run.log.jsonl`; trạng thái terminal đã có trước report vẫn được giữ “sticky”.

**Luồng dữ liệu:** `RunContext` → `start_run` → `PHASE_ONE` → `state.json/AWAITING_APPROVAL` → `decision.json` → `resume_run` → `PHASE_TWO` → `report.json + metrics.json + state.json`

**Các quyết định kỹ thuật:**

- Dùng tuple tên bước + callable để thứ tự thực thi là dữ liệu rõ ràng và khớp `STEP_NAMES`.
- Redact lỗi trước cả `RunRecord.error` và `append_log`, không chỉ dựa vào bộ che của log.
- Chỉ cho `resume_run` đi tiếp từ `AWAITING_APPROVAL` có file quyết định; run terminal là idempotent.
- Ghi log `info`/`warn` trước cả ba nhánh no-op để CLI Task 9 có lời giải thích cho người vận hành.
- Gắn `type(exc).__name__` vào lỗi bất ngờ vì runner cố ý không để traceback thoát ra ngoài.
- Kiểm tra `run_id` theo định dạng timestamp/suffix do `new_run` sinh để chặn `../` trước khi đọc đĩa.

**Xử lý lỗi / trường hợp biên:** Run không tồn tại hoặc run ID sai ném `FileNotFoundError`; thiếu quyết định giữ nguyên `AWAITING_APPROVAL` và ghi log; run terminal hoặc sai state cũng trả nguyên record kèm log; lỗi bước chuyển run sang `FAILED`; lỗi bất ngờ giữ tên loại và được ghi bền; `REJECTED` không bị report/finalize đổi thành `DONE`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `start_run` | `start_run(ctx: RunContext) -> RunRecord` | Tạo run và chạy phase một; tự chạy phase hai nếu không cần dừng duyệt. |
| Hàm | `resume_run` | `resume_run(ctx: RunContext, run_id: str) -> RunRecord` | Nạp run chờ duyệt và chạy phase hai khi có quyết định. |
| Hằng | `PHASE_ONE`, `PHASE_TWO` | `tuple[tuple[str, StepFunction], ...]` | Khai báo thứ tự chín bước thành hai phase. |
| API package | `orchestrator.__init__` | `RunContext`, state API, runner API, `collect_metrics` | Bề mặt import cho CLI/web. |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_runner.py -v
```

**Output thật (đã che secret):**

```text
collected 14 items
tests/unit/orchestrator/test_runner.py ... 14 PASSED
============================== 14 passed in 0.19s ==============================
```

TDD đỏ ban đầu:

```text
E   ModuleNotFoundError: No module named 'project_sentinel.orchestrator.runner'
=========================== short test summary info ============================
ERROR tests/unit/orchestrator/test_runner.py
EXIT_CODE=2
```

Bằng chứng hai regression mới bắt được lỗi trước khi sửa:

```text
test_resume_explains_itself_when_it_does_nothing FAILED
AssertionError: AWAITING_APPROVAL: không có dòng log nào
test_unexpected_error_message_names_the_exception_type FAILED
assert 'KeyError' in "Lỗi ngoài dự kiến ở bước scan: 'foo'"
============================== 2 failed in 0.13s ===============================
EXIT_CODE=1
```

Sau khi trả implementation về trạng thái đã sửa:

```text
test_resume_explains_itself_when_it_does_nothing PASSED
test_unexpected_error_message_names_the_exception_type PASSED
============================== 2 passed in 0.08s ===============================
EXIT_CODE=0
```

Shell không có alias `python`, nên lệnh đầu tiên dừng trước pytest:

```text
/bin/bash: line 1: python: command not found
EXIT_CODE=127
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Một runner đồng bộ, trạng thái bền trên đĩa, chia hai phase và không giữ coroutine chờ người duyệt.

**Lý do:** Plan yêu cầu “`state.json` là nguồn sự thật duy nhất cho cả CLI lẫn web” và runner “lưu trạng thái sau mỗi bước”. Cách này cho phép tiến trình kết thúc ở `AWAITING_APPROVAL`, rồi một tiến trình khác tiếp tục đúng run sau khi `decision.json` xuất hiện.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ một coroutine chờ input duyệt | Luồng nhìn tuyến tính | Web/CLI khác tiến trình; restart sẽ mất trạng thái và treo worker. |
| Cho resume chạy dù thiếu quyết định | Code ngắn hơn | `step_probe` sẽ chặn nhưng runner vẫn có thể report/finalize thành `DONE`, làm sai kết quả. |
| Cho phép resume run terminal | Có thể “thử lại” dễ dàng | Có nguy cơ gửi lại request đã duyệt; retry phải là hợp đồng riêng, không được ngầm xảy ra. |
| Ghép trực tiếp chuỗi bước vào CLI | Ít một module | Web sẽ phải lặp logic và hai giao diện có thể khác hành vi. |

**Đánh đổi đã chấp nhận:** `resume_run` chỉ tiếp tục đúng trạng thái chờ duyệt; phục hồi giữa phase từ một trạng thái không terminal khác chưa được tự động hóa để tránh đoán sai bước an toàn cần chạy lại.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `source .venv/bin/activate && python -m pytest tests/unit/orchestrator/test_runner.py -v` | 0 | 14 passed trong 0.19s. |
| `source .venv/bin/activate && python -m pytest tests/unit/orchestrator -v` | 0 | 104 passed trong 1.67s. |
| `source .venv/bin/activate && python -m pytest -m "not llm and not live_gateway" -q` | 0 | 414 passed, 15 deselected trong 3.15s. |
| `.venv/bin/python -m compileall -q src/project_sentinel` | 0 | Không có lỗi biên dịch. |
| `git diff --check` | 0 | Không có whitespace error. |

**Test mới thêm:**

- `test_failing_first_step_marks_the_run_failed` — lỗi bước đầu thành `FAILED`.
- `test_failure_is_persisted_to_disk` — lỗi đọc lại được từ `state.json`.
- `test_failure_is_redacted_before_state_and_log_are_written` — canary không rò vào state/log.
- `test_failure_does_not_raise_out_of_the_runner` — `StepFailure` không thoát runner.
- `test_unexpected_step_error_is_also_persisted_as_failed` — lỗi không dự kiến cũng thành `FAILED`.
- `test_unexpected_error_message_names_the_exception_type` — lỗi bất ngờ giữ `KeyError` để còn khả năng debug.
- `test_later_steps_are_not_run_after_a_failure` — dừng chuỗi khi lỗi.
- `test_resume_on_unknown_run_id_raises` — run không tồn tại báo đúng kiểu.
- `test_resume_rejects_a_run_id_that_escapes_the_runs_directory` — chặn path traversal.
- `test_resume_without_a_decision_stays_awaiting_approval` — không đi vòng `decision.json`.
- `test_resume_does_not_run_a_terminal_record_again` — resume idempotent cho run terminal.
- `test_resume_explains_itself_when_it_does_nothing` — cả ba nhánh no-op đều ghi lý do vào run log.
- `test_resume_after_rejection_ends_in_rejected` — vẫn tạo report/metrics và giữ `REJECTED`.
- `test_state_json_is_saved_after_every_step` — kết quả lỗi có trên đĩa.

**Bất biến đã giữ:** Không mock/stub/fake; subprocess test là lệnh thật; không skip; lỗi được redact; không bỏ fingerprint/decision guardrail; không đụng historical reports; không thêm dependency.

**Còn fail / chưa chạy được:** Lệnh `python ...` không tồn tại trong PATH (`exit 127`); đã dùng interpreter khóa của repo là `.venv/bin/python`. Không có test pytest nào còn fail.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `runner.py::_execute` giữ terminal state qua report/finalize; đây là cần thiết để `REJECTED` không biến thành `DONE`, nhưng nên được review cùng hợp đồng state của Plan 4.
- **Giả định đã đặt:** `resume_run` chỉ hợp lệ cho `AWAITING_APPROVAL`; nếu tương lai cần khôi phục giữa một bước đang chạy, phải thiết kế retry/idempotency riêng.
- **Việc còn nợ:** Happy path với LLM và Gateway thật thuộc integration CLI Task 9; Task 8 chỉ kiểm chứng điều phối offline và nhánh từ chối không gửi request.
- **Câu hỏi cho người dùng:** Không có.
