# Worklog — Plan 3 Task 4: Bước 3–4 (phân tích, đề xuất probe)

**Ngày:** 2026-08-20 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/orchestrator-analyze-propose` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 4`

---

## 1. Tóm tắt

Đã triển khai thành công 2 bước tiếp theo trong pipeline 9 bước: `step_analyze` (Bước 3: phân tích findings bằng agent, tra cứu kho tri thức, sinh `analysis.jsonl` và `analysis-summary.json`) và `step_propose` (Bước 4: trích xuất verification objective từ agent và kẹp qua allowlist của Gateway, sinh `proposal.json` và `events.jsonl`). Toàn bộ 10 test unit kiểm tra cả trường hợp hợp lệ, trường hợp bị allowlist từ chối, trường hợp agent trả null, và các trường hợp biên/lỗi JSON đều pass 100% không dùng mock/stub.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** 
  - `step_analyze`: Nhận findings đã chuẩn hoá, chuyển giao cho module phân tích nghiệp vụ (`run_pipeline`) và ghi nhận kết quả chi tiết kèm tóm tắt số liệu.
  - `step_propose`: Là cầu nối an toàn giữa đầu ra của AI và công cụ probe. Đề xuất của AI là dữ liệu không tin cậy nên được kẹp chặt qua `Allowlist` và `validate_objective` trước khi chuyển sang bước phê duyệt.
- **Nằm ở đâu trong luồng:** Là bước 3 và bước 4 trong chuỗi 9 bước (Scan -> Normalize -> **Analyze** -> **Propose** -> Approval -> Probe -> Scrub -> Report -> Finalize).
- **Không có nó thì hỏng gì:** Hệ thống không có bước suy luận tìm nguyên nhân gốc rễ và không thể sinh đề xuất kiểm thử an toàn cho các bước tiếp theo.
- **Ngoài phạm vi (cố ý không làm):** Bước 5 (cổng phê duyệt `step_approval`) và Bước 6 (thực thi probe `step_probe`) sẽ được triển khai tại Task 5.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/steps.py` | Sửa | Triển khai `step_analyze` và `step_propose` với khuôn xử lý JSON an toàn (bắt `JSONDecodeError`, kiểm tra kiểu dữ liệu dict/list, bọc `StepFailure`) | Triển khai logic thực thi Bước 3 và 4 |
| `tests/unit/orchestrator/test_steps_analyze_propose.py` | Tạo | 10 test cases kiểm tra đề xuất hợp lệ, đề xuất ngoài allowlist, đề xuất null, file phân tích thiếu/rỗng/hỏng JSON, và xử lý lỗi đầu vào findings.json | Kiểm chứng toàn diện chức năng của Bước 3 và Bước 4 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đánh dấu hoàn thành các Step 1–4 của Task 4 | Cập nhật tiến độ plan |

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. `step_analyze` kiểm tra sự tồn tại và tính hợp lệ của `findings.json` (bằng khối `try/except json.JSONDecodeError` và kiểm tra kiểu `isinstance`), chuyển trạng thái sang `ANALYZING`, thiết lập `AppConfig`, chạy `run_pipeline(config)`, trích xuất các số liệu tổng kết (`input_findings`, `groups`, `records`, `llm_calls`, `invalid_outputs`), cập nhật `detail` của `step("analyze")` và ghi nhật ký toàn trình.
2. `step_propose` đọc `analysis.jsonl` (bảo đảm xử lý an toàn từng dòng JSON), tìm `verification_objective` đầu tiên, kẹp qua `Allowlist.from_json` bằng `validate_objective`.
3. Ghi file `proposal.json` chứa đầy đủ thông tin: `accepted`, `reason`, `probe` (nếu accepted), `source_analysis_id`, và nguyên văn `objective` (kể cả khi bị từ chối làm bằng chứng kiểm toán).
4. Nếu đề xuất bị từ chối: ghi sự kiện `allowlist_block` vào `events.jsonl` và ghi log cảnh báo mức `warn` vào `run.log.jsonl`. Nếu được chấp thuận hoặc agent không đề xuất: ghi log mức `info`.
5. Cập nhật `detail={"accepted": decision.accepted}` cho `step("propose")` và đánh dấu `done`.

**Luồng dữ liệu:** 
- `step_analyze`: `findings.json` → `run_pipeline(AppConfig)` → `analysis.jsonl` + `analysis-summary.json` → cập nhật `record.step("analyze")` + `append_log()`
- `step_propose`: `analysis.jsonl` → `validate_objective(objective, allowlist)` → `proposal.json` (+ `events.jsonl` nếu block) → cập nhật `record.step("propose")` + `append_log()`

**Các quyết định kỹ thuật:**
- Áp dụng khuôn xử lý JSON nghiêm ngặt từ `step_normalize` đã sửa: bắt `JSONDecodeError` và kiểm tra kiểu để luôn ném `StepFailure` thay vì để lọt exception lạ.
- Lưu nguyên văn `objective` trong `proposal.json` ngay cả khi bị từ chối để phục vụ audit trail và giải thích nguyên nhân cho người vận hành.
- Ghi nhận sự kiện `allowlist_block` vào `events.jsonl` để màn hình Security Events hiển thị các lần chặn vi phạm chính sách.

**Xử lý lỗi / trường hợp biên:**
- Thiếu `findings.json` hoặc `findings.json` chứa JSON hỏng: ném `StepFailure`.
- `analysis.jsonl` không tồn tại hoặc chứa dòng JSON lỗi: ném `StepFailure`.
- `analysis.jsonl` rỗng hoặc không có finding nào chứa `verification_objective`: `step_propose` hoàn thành bình thường với `accepted=False` và lý do rõ ràng.
- Đề xuất vi phạm allowlist (sai method, endpoint ngoài danh mục): `accepted=False`, sinh sự kiện `allowlist_block`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `step_analyze` | `step_analyze(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 3: Phân tích findings và sinh báo cáo |
| Hàm | `step_propose` | `step_propose(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 4: Trích xuất và kẹp đề xuất kiểm thử qua allowlist |
| Test | `test_steps_analyze_propose.py` | `tests/unit/orchestrator/test_steps_analyze_propose.py` | 10 test unit kiểm tra Bước 3 & 4 |

**Cách chạy:**

```bash
.venv/bin/pytest tests/unit/orchestrator/test_steps_analyze_propose.py -v
```

**Output thật (đã che secret):**

```text
tests/unit/orchestrator/test_steps_analyze_propose.py::test_accepted_objective_produces_a_probe PASSED [ 10%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_objective_outside_allowlist_is_rejected_and_recorded PASSED [ 20%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_rejected_objective_writes_an_allowlist_block_event PASSED [ 30%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_no_objective_at_all_is_not_a_failure PASSED [ 40%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_missing_analysis_file_fails_clearly PASSED [ 50%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_empty_analysis_file_is_handled PASSED [ 60%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_first_record_with_an_objective_wins PASSED [ 70%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_invalid_json_in_analysis_file_raises_step_failure PASSED [ 80%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_step_analyze_missing_findings_fails_clearly PASSED [ 90%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_step_analyze_invalid_findings_json_fails_clearly PASSED [100%]

============================== 10 passed in 0.11s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Sử dụng `validate_objective` kết hợp `Allowlist.from_json` để đánh giá `verification_objective`, ghi nhận đề xuất vào `proposal.json` và bắn sự kiện `allowlist_block` khi bị chặn.

**Lý do:** Kế thừa trọn vẹn lớp bảo vệ đã xây dựng từ Week 4/5, bảo đảm LLM không thể gửi request đến các endpoint ngoài danh mục đã kiểm duyệt.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Bỏ qua việc lưu `proposal.json` khi `verification_objective` là None | Tiết kiệm 1 file ghi đĩa | Phá vỡ tính đồng nhất của hợp đồng pipeline (các bước sau như `step_approval` cần đọc `proposal.json` để biết trạng thái đề xuất). |
| Ném lỗi `StepFailure` khi objective bị allowlist từ chối | Dừng pipeline ngay lập tức | Sai nghiệp vụ: Việc AI đề xuất một mục tiêu không hợp lệ là trường hợp xử lý từ chối bình thường của policy (`accepted=False`), không phải lỗi sập hệ thống. |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/pytest tests/unit/orchestrator/test_steps_analyze_propose.py -v` | 0 | 10 passed in 0.11s |
| `.venv/bin/pytest tests/unit/orchestrator -v` | 0 | 53 passed in 1.80s |
| `.venv/bin/pytest -m "not llm and not live_gateway" -q` | 0 | 362 passed, 15 deselected in 3.62s |
| `python3 -m compileall -q src/project_sentinel` | 0 | Biên dịch không có lỗi cú pháp |

**Test mới thêm:**
- `test_accepted_objective_produces_a_probe`: Khẳng định đề xuất hợp lệ tạo ra `proposal.json` có `accepted: True` và `probe` đầy đủ.
- `test_objective_outside_allowlist_is_rejected_and_recorded`: Khẳng định đề xuất ngoài allowlist bị từ chối và lưu nguyên văn `objective`.
- `test_rejected_objective_writes_an_allowlist_block_event`: Khẳng định khi bị chặn sinh sự kiện `allowlist_block` vào `events.jsonl` và log cảnh báo mức `warn`.
- `test_no_objective_at_all_is_not_a_failure`: Khẳng định agent trả null objective là kết quả hợp lệ (`accepted: False`).
- `test_missing_analysis_file_fails_clearly`: Khẳng định thiếu `analysis.jsonl` ném `StepFailure` rõ ràng.
- `test_empty_analysis_file_is_handled`: Khẳng định file `analysis.jsonl` rỗng được xử lý an toàn.
- `test_first_record_with_an_objective_wins`: Khẳng định lấy đúng objective đầu tiên xuất hiện trong danh sách kết quả phân tích.
- `test_invalid_json_in_analysis_file_raises_step_failure`: Khẳng định dòng JSON hỏng trong `analysis.jsonl` ném `StepFailure`.
- `test_step_analyze_missing_findings_fails_clearly`: Khẳng định thiếu `findings.json` ném `StepFailure`.
- `test_step_analyze_invalid_findings_json_fails_clearly`: Khẳng định `findings.json` hỏng ném `StepFailure`.

**Bất biến đã giữ:** Không mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có, cả 2 bước `step_analyze` và `step_propose` đều được bảo vệ bằng khuôn xử lý JSON nghiêm ngặt và đã kiểm chứng 100% test case.
- **Ghi chú về việc đang treo (Task 8):** `record.error` chưa được khử dữ liệu nhạy cảm khi `save_run` ghi `state.json`. Khi triển khai Task 8, bắt buộc phải áp dụng bộ che `redact_structure` cho `record.error` trước khi serialize ra đĩa.
- **Việc còn nợ:** Task 5 (`steps.py`: `step_approval`, `step_probe`).
- **Câu hỏi cho người dùng:** Không có.
