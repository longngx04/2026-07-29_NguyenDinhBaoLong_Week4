# Worklog — Plan 3 Task 3: RunContext và bước 1–2 (quét, chuẩn hoá)

**Ngày:** 2026-08-20 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/orchestrator-context` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 3`

---

## 1. Tóm tắt

Đã xây dựng và củng cố toàn diện `RunContext` (nơi tập trung tiêm toàn bộ phụ thuộc cho orchestrator) và triển khai 2 bước đầu tiên của luồng: `step_scan` (Bước 1: chạy SAST OpenGrep, sinh `raw.json`) và `step_normalize` (Bước 2: chuẩn hoá finding schema, sinh `findings.json`). Đồng thời, đã hoàn thiện 4 điểm an toàn và củng cố luồng: giấu `gateway_api_key` khỏi `repr`/traceback, chuẩn hoá lỗi `StepFailure` cho trường hợp JSON hỏng ở bước normalize, ghi rõ cảnh báo và cờ `used_fallback` khi quét SAST dùng lại báo cáo cũ, và lưu stdout của lệnh thành công vào `run.log.jsonl`. Toàn bộ 13 test unit đều pass 100% bằng cách tiêm subprocess thật mà không dùng bất kỳ test double / mock nào.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** 
  - `RunContext`: Quản lý đường dẫn, cấu hình, khóa API và các lệnh thực thi bên ngoài cho toàn bộ vòng đời của một run.
  - `step_scan`: Kích hoạt scanner SAST và ghi nhận kết quả thô vào `artifacts/runs/<run_id>/raw.json`.
  - `step_normalize`: Chuyển đổi dữ liệu `raw.json` sang định dạng chuẩn `findings.json` của Project Sentinel.
- **Nằm ở đâu trong luồng:** 
  - `RunContext`: Cung cấp ngữ cảnh xuyên suốt 9 bước.
  - `step_scan` & `step_normalize`: Là 2 bước đầu tiên trong pipeline 9 bước.
- **Không có nó thì hỏng gì:** Hệ thống không thể khởi chạy quét mã nguồn và chuẩn hoá finding đầu vào để làm tiền đề cho bước phân tích LLM (Bước 3).
- **Ngoài phạm vi (cố ý không làm):** Các bước 3–9 (`step_analyze`, `step_propose`, `step_approval`, `step_probe`, `step_scrub`, `step_report`, `step_finalize`) sẽ được triển khai ở Task 4–6.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/context.py` | Tạo / Sửa | Triển khai dataclass `RunContext` bất biến (`frozen=True`) với `gateway_api_key: str = field(default="", repr=False)`, `default()` và `replace()` | Cung cấp dependency injection sạch và an toàn cho orchestrator |
| `src/project_sentinel/orchestrator/steps.py` | Tạo / Sửa | Triển khai `StepFailure`, `_run_command` (ghi stdout vào log), `step_scan` (xử lý fallback rõ ràng), `step_normalize` (bọc `StepFailure` cho JSON hỏng/sai kiểu) | Triển khai 2 bước đầu của quy trình 9 bước với khả năng chịu lỗi cao |
| `tests/unit/orchestrator/test_steps_scan_normalize.py` | Tạo / Sửa | 13 test cases kiểm tra ghi file `raw.json`, `findings.json`, đếm số finding, xử lý lỗi lệnh/lỗi JSON, ghi nhật ký từng bước, giấu API key trong repr, cảnh báo fallback, và lưu stdout | Kiểm chứng chức năng và 4 điểm củng cố của Bước 1 và Bước 2 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đánh dấu hoàn thành các Step 1–5 của Task 3 | Cập nhật tiến độ plan |

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. `RunContext` định nghĩa các phụ thuộc dưới dạng các trường dữ liệu (`repo_root`, `runs_dir`, `allowlist_path`, `scan_command`, `normalize_command`, `gateway_api_key`, `llm_provider`). Thiết lập `gateway_api_key: str = field(default="", repr=False)` để bảo đảm khóa bí mật không bao giờ xuất hiện trong `repr(ctx)`, `str(ctx)` hay traceback.
2. `_run_command` nhận thêm tham số `root` để tự động ghi `result.stdout` vào `run.log.jsonl` qua `append_log` (mức `info`) khi lệnh thực thi thành công.
3. `step_scan` chuyển trạng thái sang `SCANNING`, ghi nhật ký bắt đầu, chạy lệnh `scan_command` để xuất `raw.json` vào thư mục của run. Nếu phải dùng fallback từ `artifacts/raw/opengrep.json`, ghi log mức `warn` và đánh dấu `used_fallback: True` trong `detail`. Cập nhật số lượng `raw_results` vào `StepRecord` và ghi nhật ký hoàn thành.
4. `step_normalize` kiểm tra sự tồn tại của `raw.json`, chuyển trạng thái sang `NORMALIZING`, ghi nhật ký bắt đầu, chạy `normalize_command` để chuyển `raw.json` thành `findings.json`. Bắt ngoại lệ `json.JSONDecodeError` và kiểm tra kiểu dữ liệu `payload` để ném `StepFailure` tường minh (tránh lỗi trần làm sập runner).
5. Cập nhật số lượng `findings` vào `StepRecord` và ghi nhật ký hoàn thành.

**Luồng dữ liệu:** 
- `step_scan`: `RunRecord` + `RunContext` → `_run_command(scan_command)` → `raw.json` (hoặc fallback + warn) → cập nhật `record.step("scan", detail={"raw_results": count, "used_fallback": ...})` + `append_log()`
- `step_normalize`: `raw.json` → `_run_command(normalize_command)` → `findings.json` (validate JSON & dict) → cập nhật `record.step("normalize")` + `append_log()`

**Các quyết định kỹ thuật:**
- `gateway_api_key` dùng `field(default="", repr=False)` để tránh rò rỉ khóa qua log in biến cục bộ hoặc exception formatting.
- `_run_command` ghi stdout thành công vào log giúp lưu giữ output của tiến trình quét/chuẩn hoá mà không cần thêm tầng xử lý riêng.
- Cả `step_scan` và `step_normalize` đều bọc mọi lỗi phân tích dữ liệu đầu ra thành `StepFailure` để tầng runner xử lý thống nhất.

**Xử lý lỗi / trường hợp biên:**
- `SENTINEL_GATEWAY_API_KEY` được set: `repr(ctx)` và `str(ctx)` không chứa chuỗi khóa.
- Lệnh quét không tạo ra `raw.json`: dùng fallback và ghi rõ log cảnh báo + đánh dấu `used_fallback: True`.
- Lệnh chuẩn hoá sinh file hỏng/không phải JSON: ném `StepFailure` thay vì để lọt `JSONDecodeError`.
- File `findings.json` không phải JSON object: ném `StepFailure`.
- `step_normalize` được gọi khi chưa có `raw.json`: ném `StepFailure("Không có raw.json để chuẩn hoá; bước scan chưa chạy")`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Class | `RunContext` | `src/project_sentinel/orchestrator/context.py` | Dataclass quản lý phụ thuộc của orchestrator, giấu API key trong repr |
| Class | `StepFailure` | `src/project_sentinel/orchestrator/steps.py` | Ngoại lệ báo lỗi bước có thông điệp tường minh |
| Hàm | `_run_command` | `_run_command(command, *, cwd, step, root) -> None` | Thực thi lệnh ngoài, ném StepFailure khi lỗi, ghi stdout khi thành công |
| Hàm | `step_scan` | `step_scan(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 1: Quét SAST, theo dõi fallback |
| Hàm | `step_normalize` | `step_normalize(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 2: Chuẩn hoá findings, bọc StepFailure cho JSON lỗi |
| Test | `test_steps_scan_normalize.py` | `tests/unit/orchestrator/test_steps_scan_normalize.py` | 13 test unit kiểm tra Bước 1 & 2 và 4 điểm củng cố |

**Cách chạy:**

```bash
.venv/bin/pytest tests/unit/orchestrator/test_steps_scan_normalize.py -v
```

**Output thật (đã che secret):**

```text
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_writes_raw_json_into_the_run_directory PASSED [  7%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_records_the_finding_count PASSED [ 15%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_failure_raises_step_failure PASSED [ 23%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_rejects_output_that_is_not_a_valid_report PASSED [ 30%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_normalize_produces_findings_json PASSED [ 38%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_normalize_records_the_normalised_count PASSED [ 46%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_normalize_without_raw_json_fails_clearly PASSED [ 53%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_every_step_writes_a_log_line PASSED [ 61%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_context_never_prints_the_gateway_api_key PASSED [ 69%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_normalize_with_invalid_json_output_raises_step_failure PASSED [ 76%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_fallback_records_warning_and_detail PASSED [ 84%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_normal_path_marks_used_fallback_false PASSED [ 92%]
tests/unit/orchestrator/test_steps_scan_normalize.py::test_run_command_logs_stdout_on_success PASSED [100%]

============================== 13 passed in 0.61s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Đóng gói toàn bộ lệnh gọi ngoài vào `RunContext` (giấu API key trong repr) và truyền tường minh qua từng bước; `_run_command` quản lý tập trung logging stdout và bọc `StepFailure`.

**Lý do:** Đảm bảo tính khép kín, an toàn bí mật và khả năng kiểm thử độc lập cao mà không cần bất kỳ mock library nào.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Để `gateway_api_key` in bình thường trong repr | Mặc định của dataclass | Rò rỉ bí mật ra traceback và log khi in biến context. |
| Để `JSONDecodeError` tự do nổi lên trong `step_normalize` | Ít code hơn | Runner ở Task 8 chỉ bắt `StepFailure`, để lọt exception khác sẽ làm crash runner thay vì chuyển trạng thái sang `FAILED`. |
| Im lặng copy file cũ khi `scan_command` không sinh `raw.json` | Đơn giản | Che giấu lỗi thực thi của scanner, tạo ra kết quả sai lệch mà người vận hành không hay biết. |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/pytest tests/unit/orchestrator/test_steps_scan_normalize.py -v` | 0 | 13 passed in 0.61s |
| `.venv/bin/pytest tests/unit/orchestrator -v` | 0 | 43 passed in 1.63s |
| `.venv/bin/pytest -m "not llm and not live_gateway" -q` | 0 | 352 passed, 15 deselected in 3.60s |
| `python3 -m compileall -q src/project_sentinel` | 0 | Biên dịch không có lỗi cú pháp |

**Test mới thêm:**
- `test_scan_writes_raw_json_into_the_run_directory`: Khẳng định `step_scan` ghi `raw.json` và cập nhật trạng thái `SCANNING` / `done`.
- `test_scan_records_the_finding_count`: Khẳng định `step_scan` đếm đúng số lượng kết quả thô trong `detail["raw_results"]`.
- `test_scan_failure_raises_step_failure`: Khẳng định lệnh quét thất bại ném `StepFailure` có thông điệp rõ ràng.
- `test_scan_rejects_output_that_is_not_a_valid_report`: Khẳng định file đầu ra không phải JSON hợp lệ bị từ chối với `StepFailure`.
- `test_normalize_produces_findings_json`: Khẳng định `step_normalize` sinh ra `findings.json` và cập nhật trạng thái `NORMALIZING` / `done`.
- `test_normalize_records_the_normalised_count`: Khẳng định `step_normalize` đếm đúng số finding được chuẩn hoá trong `detail["findings"]`.
- `test_normalize_without_raw_json_fails_clearly`: Khẳng định chạy normalize khi thiếu `raw.json` báo lỗi tường minh.
- `test_every_step_writes_a_log_line`: Khẳng định cả hai bước đều ghi nhật ký vào `run.log.jsonl`.
- `test_context_never_prints_the_gateway_api_key`: Khẳng định `gateway_api_key` không bao giờ xuất hiện trong `repr(ctx)` hay `str(ctx)`.
- `test_normalize_with_invalid_json_output_raises_step_failure`: Khẳng định JSON không hợp lệ ở output của normalize được bọc thành `StepFailure`.
- `test_scan_fallback_records_warning_and_detail`: Khẳng định khi dùng fallback từ `artifacts/raw/`, ghi log mức `warn` và đánh dấu `used_fallback: True`.
- `test_scan_normal_path_marks_used_fallback_false`: Khẳng định đường chạy bình thường đánh dấu `used_fallback: False`.
- `test_run_command_logs_stdout_on_success`: Khẳng định stdout của lệnh thành công được ghi lại vào `run.log.jsonl`.

**Bất biến đã giữ:** Không mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Bộ che và xử lý lỗi bước khép kín nhưng 4 điểm ngoài (giấu API key khỏi `repr`, bọc `StepFailure` cho lỗi JSON normalize, đánh dấu rõ ràng khi dùng fallback report, và lưu lại stdout của lệnh thành công) đã được giải quyết triệt để tại tầng `context.py`/`steps.py`.
- **Ghi chú về môi trường subprocess:** `subprocess.run` hiện không truyền `env=` nên script quét thừa hưởng cả `SENTINEL_GATEWAY_API_KEY` lẫn `LLM_API_KEY`. Nếu muốn thắt chặt hơn nữa ở các task sau thì cần truyền danh sách biến môi trường tối thiểu (cần quyết định ở task tích hợp).
- **Ghi chú về lỗi StepFailure và state.json:** `StepFailure` mang 400 ký tự stderr của công cụ ngoài; Task 8 sẽ gán nó vào `record.error`, mà `save_run` ghi `state.json` hiện chưa qua bộ che. Khi triển khai Task 8, bắt buộc phải khử dữ liệu nhạy cảm cho `record.error` trước khi lưu vào `state.json`.
- **Việc còn nợ:** Task 4 (`steps.py`: `step_analyze`, `step_propose`).
- **Câu hỏi cho người dùng:** Không có.

