# Worklog — Sửa 6 lỗi trong repo Project Sentinel

**Ngày:** 2026-08-23 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** N/A (Direct Fix Request) · **Task ID:** `F1, F3, F2, F4, F5, F6`

> Điền đủ 8 mục. Mục nào không có nội dung thì ghi `Không có` — không được xoá mục.
> Mọi số liệu phải là kết quả chạy thật. Che secret bằng `***`.

---

## 1. Tóm tắt

Đã khắc phục tuần tự và độc lập 6 lỗi còn tồn đọng trong repo Project Sentinel bao gồm: chặn bàn giao kết luận `confirmed` dựa trên lời tự khai của LLM qua tầng calibration (F1); cập nhật trạng thái `running` lên đĩa ngay trước khi bước chạy dài thực thi để tránh UI đứng hình (F3); hiệu chỉnh đáp án kỳ vọng của ca đánh giá 01 và thêm ca 12 cấm `confirmed` khi thiếu phép đo độc lập (F2); chuẩn hóa `run_id` và bổ sung `request_id` vào trường `detail` trong `events.jsonl` (F4); thu hồi quyền ghi thế giới (chmod 0600) cho tệp không tin cậy `zap-alerts.json` (F5); và đồng bộ toàn bộ tài liệu tránh trôi số liệu kèm bộ test chống hồi quy (F6). Toàn bộ 6 commit độc lập đều tuân thủ TDD (test đỏ trước, code xanh sau), vượt qua bộ kiểm thử chất lượng `make quality` với 963 tests passed và 83.97% test coverage.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:**
  - **F1:** Đảm bảo tính trung thực của kết luận an ninh — không bao giờ cấp `confirmed` khi chưa có phép đo độc lập (`measured_attacker_control`).
  - **F3:** Cải thiện khả năng quan sát trạng thái (observability) thời gian thực của runner và Web UI trong quá trình chạy các bước nặng (như `analyze`).
  - **F2:** Chuẩn hóa harness đánh giá và bộ ca kiểm thử `eval/cases/`, phản ánh đúng logic trần severity của hệ thống sau calibration.
  - **F4:** Khắc phục lỗi sai lệch trường `run_id` trong nhật ký sự kiện guardrails `events.jsonl`, hỗ trợ audit chính xác theo từng phiên chạy.
  - **F5:** Đóng lỗ hổng bảo mật hạ tầng khi ZAP container xuất file `zap-alerts.json` với quyền 666, ngăn chặn việc can thiệp dữ liệu đầu vào trước khi cấp cho LLM.
  - **F6:** Loại bỏ hiện tượng tài liệu bị trôi so với mã nguồn thực tế (số lượng ca đánh giá, thời gian chạy thực tế của analyze, hướng phát triển DAST/scanner).
- **Nằm ở đâu trong luồng:** Trải rộng từ Ingestion/DAST scan (bước 1), Calibration (bước 3), Proposer/Tool (bước 4 & 6), Runner (điều phối luồng), Harness đánh giá (`eval/`), tới Tài liệu sản phẩm (`docs/`, `README.md`).
- **Không có nó thì hỏng gì:**
  - LLM có thể bịa đặt `attacker_control == "proven"` và cấp kết luận `confirmed` giả mạo.
  - Web UI đứng hình 6 phút ở trạng thái `pending` khi đang phân tích thay vì hiển thị `running`.
  - `make eval` bị fail trên clone sạch do ca 01 mong đợi sai mức severity cũ.
  - Nhật ký `events.jsonl` ghi nhầm `request_id` vào cột `run_id`, làm đứt gãy truy vết audit.
  - Tệp cảnh báo DAST có thể bị sửa đổi bởi các tiến trình khác trên máy chủ do quyền ghi thế giới.
  - Tài liệu trình bày thông tin sai lệch về thời gian chạy và năng lực hệ thống.
- **Ngoài phạm vi (cố ý không làm):** Không nới lỏng JSON schema, không giả lập test double (mock/stub/fake/dummy).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/calibration.py` | Sửa | Hạ `attacker_control == "proven"` xuống `"not_proven"`, ghi nhận rule `attacker_control_unverifiable` trước Luật 1 | Chưa có phép đo độc lập cho `attacker_control` |
| `tests/unit/analysis/test_calibration.py` | Sửa | Cập nhật assertion khẳng định `confirmed` bị hạ và `attacker_control_unverifiable` được kích hoạt | Kiểm thử TDD cho F1 |
| `tests/unit/analysis/test_calibration_measured.py` | Sửa | Cập nhật assertion rằng `confirmed` không thể tồn tại chỉ với `reachability="proven"` | Kiểm chứng tính nhất quán của calibration |
| `src/project_sentinel/orchestrator/runner.py` | Sửa | Trong `_execute`, nếu step có trạng thái `pending` thì chuyển `running` và `save_run(record)` trước khi gọi hàm thực thi | Khắc phục UI đứng hình (F3) |
| `tests/unit/orchestrator/test_runner.py` | Sửa | Thêm test `test_step_is_marked_running_on_disk_before_execution` | Kiểm thử TDD cho F3 |
| `eval/cases/01-sql-injection.json` | Sửa | Đổi `severity` thành `medium`, thêm `disposition: needs_review`, bỏ `should_propose_verification` | Khớp với trần severity của hệ thống sau calibration (F2) |
| `eval/cases/12-confirmed-needs-evidence.json` | Tạo | Thêm ca đánh giá 12 cấm kết luận `confirmed` khi chưa có bằng chứng thực nghiệm | Bổ sung ca đánh giá F2 |
| `eval/run_eval.py` | Sửa | Thêm kiểm tra `forbidden_disposition` / `disposition_not` trong `evaluate_case` | Hỗ trợ ca đánh giá 12 |
| `tests/integration/test_eval_harness.py` | Sửa | Cập nhật kỳ vọng cho ca 01 và thêm test cho ca 12 | Kiểm thử TDD cho F2 |
| `src/project_sentinel/probe/tool.py` | Sửa | Thêm tham số `run_id` vào `send_probe`, đưa `request_id` vào `detail`, truyền `run_id` vào `append_event` | Sửa lỗi ghi nhầm `request_id` vào ô `run_id` (F4) |
| `src/project_sentinel/orchestrator/steps/probe.py` | Sửa | Truyền `run_id=record.run_id` khi gọi `send_probe` | Đồng bộ run_id từ orchestrator xuống tool |
| `tests/unit/probe/test_tool_approval_gate.py` | Sửa | Thêm test `test_events_log_records_actual_run_id_and_places_request_id_in_detail` | Kiểm thử TDD cho F4 |
| `tests/unit/orchestrator/test_steps_approval_probe.py` | Sửa | Thêm test `test_all_events_in_run_record_the_actual_run_id` | Khẳng định mọi sự kiện có `run_id` đúng |
| `src/project_sentinel/orchestrator/steps/ingest.py` | Sửa | Gọi `alerts.chmod(0o600)` ngay sau khi lệnh DAST hoàn thành | Loại bỏ quyền world-writable 666 (F5) |
| `tests/unit/orchestrator/test_step_scan_dast.py` | Sửa | Thêm test kiểm tra quyền 0o600 và không có bit ghi `0o022` trên `zap-alerts.json` | Kiểm thử TDD cho F5 |
| `README.md` | Sửa | Đồng bộ số lượng 12 ca đánh giá và thời gian chạy thực tế của analyze (~6 phút / 360–370 s / 41–44 calls) | Sửa trôi tài liệu (F6) |
| `docs/product-brief.md` | Sửa | Đổi sáu ca thành 12 ca; cập nhật hướng phát triển: chứng minh attacker_control và mở rộng scanner rules | Sửa trôi tài liệu (F6) |
| `docs/limitations.md` | Sửa | Ghi nhận Python kẹp cứng `attacker_control`; cập nhật 12 ca; thống nhất thời gian analyze 360–370 s | Sửa trôi tài liệu (F1, F6) |
| `docs/demo-script.md` | Sửa | Đổi "sáu ca" thành "(12 ca)" | Sửa trôi tài liệu (F6) |
| `eval/README.md` | Sửa | Thêm ca 12 vào bảng Ca mở rộng | Đồng bộ tài liệu eval |
| `tests/unit/infra/test_docs_complete.py` | Sửa | Thêm test `test_documentation_does_not_drift_on_eval_case_counts` cấm "sáu ca" / "6 ca" | Test chống hồi quy trôi tài liệu |

**`git diff --stat 0280dfe..HEAD`:**

```text
 README.md                                          |   8 +-
 docs/demo-script.md                                |   2 +-
 docs/limitations.md                                |  33 +++-
 docs/product-brief.md                              |  10 +-
 eval/README.md                                     |   1 +
 eval/cases/01-sql-injection.json                   |   8 +-
 eval/cases/12-confirmed-needs-evidence.json        |  30 ++++
 eval/run_eval.py                                   |   9 +
 src/project_sentinel/analysis/calibration.py       |   8 +
 src/project_sentinel/orchestrator/runner.py        |   3 +
 src/project_sentinel/orchestrator/steps/ingest.py  |   3 +
 src/project_sentinel/orchestrator/steps/probe.py   |   1 +
 src/project_sentinel/probe/tool.py                 |  25 ++-
 tests/integration/test_eval_harness.py             |  36 +++-
 tests/unit/analysis/test_calibration.py            |  33 +++-
 tests/unit/analysis/test_calibration_measured.py   |   6 +-
 tests/unit/infra/test_docs_complete.py             |  20 +++
 tests/unit/orchestrator/test_runner.py             |  22 +++
 tests/unit/orchestrator/test_step_scan_dast.py     |  21 ++-
 .../unit/orchestrator/test_steps_approval_probe.py |  18 ++
 tests/unit/probe/test_tool_approval_gate.py        |  30 ++++
 21 files changed, 290 insertions(+), 37 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Thực hiện theo phương pháp Test-Driven Development (TDD) tuần tự cho từng lỗi: viết unit/integration test mô tả đúng hành vi mong muốn và ghi nhận trạng thái đỏ (FAILED); sau đó bổ sung chỉnh sửa tối thiểu vào mã nguồn chính để chuyển sang trạng thái xanh (PASSED); chạy `make quality` để bảo đảm không có hồi quy nào trong toàn bộ 78 source files và test suite.

**Luồng dữ liệu:**
1. **Calibration:** LLM output → Python Calibration (hạ `attacker_control="not_proven"`, thêm rule `attacker_control_unverifiable`) → Rule 1 hạ `disposition="needs_review"` → Rule 4 hạ `severity="medium"`.
2. **Runner State Persistence:** Runner loop → `if status == "pending": mark_step("running"); save_run()` → Function execution → `mark_step("done")` → `save_run()`.
3. **Guardrails Audit:** `send_probe(run_id=record.run_id)` → `append_event(run_id=run_id, detail={"request_id": request_id, ...})` → `events.jsonl`.
4. **DAST Ingestion:** `zap-baseline.py` output `zap-alerts.json` (666) → `alerts.chmod(0o600)` → `zap_normalizer` read → prompt packet.

**Các quyết định kỹ thuật:**
- **F1 Hard Capping:** Ghi rõ trong chú thích mã nguồn rằng đây là rào cản tạm thời ở tầng Python do codebase hiện chưa có cơ chế đo đạc thực nghiệm cho `attacker_control`. Khi nào có `measured_attacker_control` thì sẽ thay thế lời tự khai của mô hình bằng phép đo.
- **F4 Audit Traceability:** Không làm mất `request_id` khi đổi `run_id` mà đưa `request_id` vào trong từ điển `detail` của event.
- **F5 Defensive Ingest:** Thực hiện `chmod(0o600)` ngay tại điểm vào sau khi sub-command trả về, trước khi bất kỳ module nào mở tệp để đọc.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Logic | `calibrate_record` | `src/project_sentinel/analysis/calibration.py` | Hạ attacker_control tự khai và ghi rule |
| Logic | `_execute` | `src/project_sentinel/orchestrator/runner.py` | Lưu trạng thái running trước khi chạy bước |
| Logic | `send_probe` | `src/project_sentinel/probe/tool.py` | Nhận `run_id` và đưa `request_id` vào `detail` |
| Config | `12-confirmed-needs-evidence.json` | `eval/cases/12-confirmed-needs-evidence.json` | Ca đánh giá cấm `confirmed` |
| Test | `test_docs_complete.py` | `tests/unit/infra/test_docs_complete.py` | Test cấm trôi số lượng ca đánh giá |

**Cách chạy:**

```bash
make quality
```

**Output thật (đã che secret):**

```text
All checks passed!
Success: no issues found in 78 source files
........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
........................................................................ [ 29%]
........................................................................ [ 37%]
........................................................................ [ 44%]
........................................................................ [ 52%]
........................................................................ [ 59%]
........................................................................ [ 67%]
........................................................................ [ 74%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 97%]
...........................                                              [100%]
================================ tests coverage ================================
Required test coverage of 78.0% reached. Total coverage: 83.97%
963 passed, 41 deselected, 1 warning in 22.69s
No known vulnerabilities found
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:**
- Tại `calibration.py`: Chèn logic hạ `attacker_control` ngay trước Luật 1 thay vì sửa các luật phía sau, đảm bảo Luật 1 và Luật 4 tự động phát huy hiệu lực một cách tự nhiên.
- Tại `runner.py`: Lưu `state.json` với trạng thái `running` ngay trước lệnh gọi bước, không cần thêm luồng nền phức tạp.
- Tại `eval/run_eval.py`: Bổ sung kiểm tra `forbidden_disposition` dạng phủ định giúp test suite tổng quát hóa được các yêu cầu kiểm soát ranh giới an toàn.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Sửa schema để bỏ `confirmed` | Đơn giản | Vi phạm bất biến JSON Schema; `confirmed` là trạng thái hợp lệ của kiến trúc khi có bằng chứng đầy đủ |
| Thêm background thread cập nhật status | Realtime hơn | Gây race condition khi đọc/ghi file `state.json` và làm phức tạp runner |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest -m "not llm and not live_gateway" -q tests` | 0 | 963 passed, 41 deselected |
| `make lint` | 0 | All checks passed (Ruff clean) |
| `make typecheck` | 0 | Success: no issues found in 78 source files (Mypy clean) |
| `make quality` | 0 | Lint + Typecheck + Coverage (83.97% >= 78.0%) + Dep-audit clean |

**Test mới thêm:**
- `test_confirmed_with_both_proven_cannot_stand_because_attacker_control_is_unverifiable` (F1)
- `test_step_is_marked_running_on_disk_before_execution` (F3)
- `test_case_12_forbids_confirmed_disposition` (F2)
- `test_events_log_records_actual_run_id_and_places_request_id_in_detail` (F4)
- `test_all_events_in_run_record_the_actual_run_id` (F4)
- `test_zap_alerts_permissions_are_set_to_0600` (F5)
- `test_documentation_does_not_drift_on_eval_case_counts` (F6)

**Bất biến đã giữ:**
- Không sử dụng test doubles vi phạm nguyên tắc D9 (`test_no_doubles.py` xanh 100%).
- Không sửa JSON schema và không thay đổi public API.
- Không rò rỉ secret hoặc API key trong logs/events.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có — các thay đổi đều có test bảo vệ chặt chẽ.
- **Giả định đã đặt:** Giả định khi hệ thống phát triển cơ chế xác minh `measured_attacker_control` (ví dụ thông qua module kiểm chứng khai thác tự động), cờ kẹp cứng ở `calibration.py` sẽ được mở ra.
- **Việc còn nợ:** Không có.
- **Câu hỏi cho người dùng:** Không có.
