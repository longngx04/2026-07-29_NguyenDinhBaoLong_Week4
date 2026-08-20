# Worklog — Plan 3 Task 4: Bước 3–4 (phân tích, đề xuất probe)

**Ngày:** 2026-08-20 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/orchestrator-analyze-propose` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 4`

---

## 1. Tóm tắt

Đã triển khai và củng cố toàn diện 2 bước tiếp theo trong pipeline 9 bước: `step_analyze` (Bước 3: phân tích findings bằng agent, tra cứu kho tri thức, sinh `analysis.jsonl` và `analysis-summary.json`) và `step_propose` (Bước 4: trích xuất verification objective từ agent và kẹp qua allowlist của Gateway, sinh `proposal.json` và `events.jsonl`). Đồng thời, đã hoàn thiện 3 điểm củng cố quan trọng: bọc ngoại lệ `Allowlist.from_json` thành `StepFailure` (tránh sập runner khi file allowlist thiếu/hỏng), ghi nhận số lượng và dấu vết của tất cả các đề xuất kiểm chứng qua `objectives_found` và log tường minh, và kiểm soát an toàn việc ép kiểu số liệu tóm tắt trong `step_analyze`. Toàn bộ 14 test unit đều pass 100% không dùng mock/stub.

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
| `src/project_sentinel/orchestrator/steps.py` | Sửa | Triển khai `step_analyze` (bọc ngoại lệ ép kiểu tóm tắt) và `step_propose` (bọc `Allowlist.from_json`, đếm và ghi vết `objectives_found`, bắt `JSONDecodeError`, bọc `StepFailure`) | Triển khai logic thực thi Bước 3 và 4 với khả năng chịu lỗi cao |
| `tests/unit/orchestrator/test_steps_analyze_propose.py` | Tạo / Sửa | 14 test cases kiểm tra đề xuất hợp lệ, đề xuất ngoài allowlist, đề xuất null, file phân tích thiếu/rỗng/hỏng JSON, thiếu/hỏng file allowlist, ghi vết nhiều đề xuất, và xử lý lỗi dữ liệu tóm tắt | Kiểm chứng toàn diện chức năng và 3 điểm củng cố của Bước 3 và Bước 4 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đánh dấu hoàn thành các Step 1–4 của Task 4 | Cập nhật tiến độ plan |

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. `step_analyze` kiểm tra sự tồn tại và tính hợp lệ của `findings.json` (bằng khối `try/except json.JSONDecodeError` và kiểm tra kiểu `isinstance`), chuyển trạng thái sang `ANALYZING`, thiết lập `AppConfig`, chạy `run_pipeline(config)`. Bọc khối khởi tạo `detail` trong `try/except (TypeError, ValueError)` để ném `StepFailure` khi số liệu tóm tắt không thể ép kiểu `int`. Cập nhật `detail` của `step("analyze")` và ghi nhật ký toàn trình.
2. `step_propose` đọc `analysis.jsonl` (bảo đảm xử lý an toàn từng dòng JSON), duyệt qua toàn bộ file để thu thập danh sách `candidates` (gồm `analysis_id` và `objective`), đếm số lượng đề xuất tìm thấy `objectives_found = len(candidates)`.
3. Ghi log `Bắt đầu chọn đề xuất kiểm chứng` kèm `objectives_found` và `chosen_analysis_id` (chọn đề xuất đầu tiên theo thiết kế).
4. Đọc allowlist qua `Allowlist.from_json(ctx.allowlist_path)` trong khối `try/except (OSError, ValueError)` để bọc thành `StepFailure` tường minh nếu file không tồn tại hoặc hỏng JSON.
5. Kẹp `objective` qua `validate_objective(objective, allowlist)`.
6. Ghi file `proposal.json` chứa đầy đủ thông tin: `accepted`, `reason`, `probe` (nếu accepted), `source_analysis_id`, nguyên văn `objective`, và `objectives_found`.
7. Nếu đề xuất bị từ chối: ghi sự kiện `allowlist_block` vào `events.jsonl` và ghi log cảnh báo mức `warn` vào `run.log.jsonl`. Nếu được chấp thuận hoặc agent không đề xuất: ghi log mức `info`.
8. Cập nhật `detail={"accepted": decision.accepted}` cho `step("propose")` và đánh dấu `done`.

**Luồng dữ liệu:** 
- `step_analyze`: `findings.json` → `run_pipeline(AppConfig)` → `analysis.jsonl` + `analysis-summary.json` → ép kiểu an toàn → cập nhật `record.step("analyze")` + `append_log()`
- `step_propose`: `analysis.jsonl` → thu thập `candidates` & `objectives_found` → `Allowlist.from_json` (bọc `StepFailure`) → `validate_objective(objective, allowlist)` → `proposal.json` (+ `events.jsonl` nếu block) → cập nhật `record.step("propose")` + `append_log()`

**Các quyết định kỹ thuật:**
- `Allowlist.from_json` được bọc `try/except (OSError, ValueError)` để đảm bảo mọi lỗi I/O hoặc JSON hỏng của file allowlist đều trở thành `StepFailure`, giúp runner chuyển trạng thái sang `FAILED` thay vì sập runner.
- Khi có nhiều `verification_objective`, hệ thống vẫn chọn đề xuất đầu tiên theo thiết kế nhưng đếm và ghi nhận `objectives_found` vào cả log lẫn `proposal.json` để không làm mất dấu vết kiểm toán.
- Áp dụng khuôn xử lý JSON nghiêm ngặt từ `step_normalize` đã sửa: bắt `JSONDecodeError` và kiểm tra kiểu để luôn ném `StepFailure` thay vì để lọt exception lạ.
- Lưu nguyên văn `objective` trong `proposal.json` ngay cả khi bị từ chối để phục vụ audit trail và giải thích nguyên nhân cho người vận hành.
- Ghi nhận sự kiện `allowlist_block` vào `events.jsonl` để màn hình Security Events hiển thị các lần chặn vi phạm chính sách.

**Xử lý lỗi / trường hợp biên:**
- Thiếu `findings.json` hoặc `findings.json` chứa JSON hỏng: ném `StepFailure`.
- `analysis.jsonl` không tồn tại hoặc chứa dòng JSON lỗi: ném `StepFailure`.
- File allowlist không tồn tại hoặc JSON hỏng: ném `StepFailure`.
- Dữ liệu tóm tắt từ `run_pipeline` chứa giá trị không thể ép kiểu sang số nguyên: ném `StepFailure`.
- `analysis.jsonl` rỗng hoặc không có finding nào chứa `verification_objective`: `step_propose` hoàn thành bình thường với `accepted=False` và lý do rõ ràng.
- Đề xuất vi phạm allowlist (sai method, endpoint ngoài danh mục): `accepted=False`, sinh sự kiện `allowlist_block`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `step_analyze` | `step_analyze(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 3: Phân tích findings, kiểm soát số liệu tóm tắt |
| Hàm | `step_propose` | `step_propose(record: RunRecord, ctx: RunContext) -> RunRecord` | Thực thi bước 4: Trích xuất và kẹp đề xuất kiểm thử qua allowlist, ghi vết |
| Test | `test_steps_analyze_propose.py` | `tests/unit/orchestrator/test_steps_analyze_propose.py` | 14 test unit kiểm tra Bước 3 & 4 và các điểm củng cố |

**Cách chạy:**

```bash
.venv/bin/pytest tests/unit/orchestrator/test_steps_analyze_propose.py -v
```

**Output thật (đã che secret):**

```text
tests/unit/orchestrator/test_steps_analyze_propose.py::test_accepted_objective_produces_a_probe PASSED [  7%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_objective_outside_allowlist_is_rejected_and_recorded PASSED [ 14%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_rejected_objective_writes_an_allowlist_block_event PASSED [ 21%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_no_objective_at_all_is_not_a_failure PASSED [ 28%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_missing_analysis_file_fails_clearly PASSED [ 35%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_empty_analysis_file_is_handled PASSED [ 42%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_first_record_with_an_objective_wins PASSED [ 50%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_invalid_json_in_analysis_file_raises_step_failure PASSED [ 57%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_step_analyze_missing_findings_fails_clearly PASSED [ 64%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_step_analyze_invalid_findings_json_fails_clearly PASSED [ 71%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_missing_allowlist_raises_step_failure PASSED [ 78%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_corrupt_allowlist_raises_step_failure PASSED [ 85%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_other_objectives_are_recorded_even_when_the_first_is_blocked PASSED [ 92%]
tests/unit/orchestrator/test_steps_analyze_propose.py::test_step_analyze_invalid_summary_metrics_raises_step_failure PASSED [100%]

============================== 14 passed in 0.17s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Sử dụng `validate_objective` kết hợp `Allowlist.from_json` (được bọc trong `try/except` bảo vệ) để đánh giá `verification_objective`, ghi nhận đề xuất vào `proposal.json` kèm `objectives_found` và bắn sự kiện `allowlist_block` khi bị chặn.

**Lý do:** Kế thừa trọn vẹn lớp bảo vệ đã xây dựng từ Week 4/5, bảo đảm LLM không thể gửi request đến các endpoint ngoài danh mục đã kiểm duyệt, đồng thời duy trì audit trail đầy đủ khi có nhiều đề xuất.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Không bọc `Allowlist.from_json` | Ít code hơn | `FileNotFoundError` hoặc `JSONDecodeError` sẽ làm sập runner thay vì đưa run về trạng thái `FAILED`. |
| Dừng đọc `analysis.jsonl` ngay khi gặp objective đầu tiên (`break`) | Nhanh hơn một chút khi file dài | Không đếm được tổng số đề xuất agent đưa ra, làm mất dấu vết nếu đề xuất đầu bị chặn trong khi các đề xuất sau có thể hợp lệ. |
| Ném lỗi `StepFailure` khi objective bị allowlist từ chối | Dừng pipeline ngay lập tức | Sai nghiệp vụ: Việc AI đề xuất một mục tiêu không hợp lệ là trường hợp xử lý từ chối bình thường của policy (`accepted=False`), không phải lỗi sập hệ thống. |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/pytest tests/unit/orchestrator/test_steps_analyze_propose.py -v` | 0 | 14 passed in 0.17s |
| `.venv/bin/pytest tests/unit/orchestrator -v` | 0 | 57 passed in 1.87s |
| `.venv/bin/pytest -m "not llm and not live_gateway" -q` | 0 | 366 passed, 15 deselected in 3.78s |
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
- `test_missing_allowlist_raises_step_failure`: Khẳng định file allowlist không tồn tại ném `StepFailure`.
- `test_corrupt_allowlist_raises_step_failure`: Khẳng định file allowlist hỏng JSON ném `StepFailure`.
- `test_other_objectives_are_recorded_even_when_the_first_is_blocked`: Khẳng định đếm đủ `objectives_found` và ghi log/proposal khi có nhiều đề xuất.
- `test_step_analyze_invalid_summary_metrics_raises_step_failure`: Khẳng định dữ liệu tóm tắt sai kiểu ném `StepFailure`.

**Bất biến đã giữ:** Không mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:**
  - Điểm rủi ro nằm ngoài khuôn xử lý JSON thông thường (lỗi đọc allowlist qua `Allowlist.from_json` và lỗi ép kiểu `int` cho số liệu tóm tắt từ `run_pipeline`) đã được bọc thành `StepFailure` tại `steps.py`.
  - Khi có nhiều `verification_objective`, hệ thống hiện tại ưu tiên đề xuất đầu tiên; việc lưu `objectives_found` và `chosen_analysis_id` đã giúp bảo toàn dấu vết kiểm toán nhưng nếu tương lai muốn hỗ trợ duyệt qua danh sách đề xuất tiếp theo khi đề xuất đầu bị từ chối thì sẽ cần mở rộng logic ở `step_propose`.
- **Ghi chú về việc đang treo (Task 8):** `record.error` chưa được khử dữ liệu nhạy cảm khi `save_run` ghi `state.json`. Khi triển khai Task 8, bắt buộc phải áp dụng bộ che `redact_structure` cho `record.error` trước khi serialize ra đĩa.
- **Việc còn nợ:** Task 5 (`steps.py`: `step_approval`, `step_probe`).
- **Câu hỏi cho người dùng:** Không có.

