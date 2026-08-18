# Worklog — Task 7: Ba tình huống kiểm thử cho Agent (rỗng, hỏng, bình thường)

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/analysis-agent-verification-scenarios` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 7

---

## 1. Tóm tắt

- Tạo hai fixture đầu vào: `tests/fixtures/analysis/empty-findings.json` (danh sách findings rỗng) và `tests/fixtures/analysis/malformed-findings.json` (JSON cú pháp hỏng).
- Xây dựng bộ kiểm thử tích hợp `tests/integration/test_analysis_edge_cases.py` với 4 test case thực thi CLI `analyze` qua subprocess mà không cần gọi LLM (không tốn token).
- Kiểm chứng chặt chẽ hành vi hệ thống: đầu vào rỗng thoát êm với exit code 0 và không sinh record bịa đặt; đầu vào hỏng hoặc thiếu file trả về exit code khác 0, có thông báo lỗi rõ ràng và không lộ traceback; đầu vào bình thường sử dụng dữ liệu chuẩn hoá thật.
- Kết quả: 4/4 integration tests pass, và 124/124 toàn bộ offline test suite xanh sạch.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đóng vai trò là bộ kiểm thử nghiệm thu bảo vệ tính ổn định (robustness) và tính trung thực (evidence grounding) của pipeline phân tích bảo mật khi xử lý các trường hợp biên của dữ liệu đầu vào.
- **Nằm ở đâu trong luồng:** 
  - Nằm ở tầng kiểm thử tích hợp CLI: `tests/integration/test_analysis_edge_cases.py` và các fixture tương ứng `tests/fixtures/analysis/`.
  - Kiểm tra toàn bộ chu trình xử lý của lệnh `project_sentinel.cli analyze`.
- **Không có nó thì hỏng gì:** Nếu không có các ca kiểm thử này, hệ thống có thể bị crash khi người dùng truyền file hỏng (lộ traceback xấu ra ngoài) hoặc tệ hơn là LLM tự động bịa đặt các bản ghi phân tích khi đầu vào không có finding nào.
- **Ngoài phạm vi (cố ý không làm):** Không gọi mô hình LLM tốn token trong bài test này (chỉ kiểm tra các nhánh fail-fast và dữ liệu đầu vào).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/fixtures/analysis/empty-findings.json` | Tạo mới | Fixture JSON rỗng `{"schema_version": "1.0", "findings": []}` | Kiểm tra tình huống không có finding đầu vào |
| `tests/fixtures/analysis/malformed-findings.json` | Tạo mới | Fixture JSON cố ý bị cắt cụt sai cú pháp | Kiểm tra tình huống file đầu vào bị hỏng cú pháp |
| `tests/integration/test_analysis_edge_cases.py` | Tạo mới | 4 test case integration kiểm thử subprocess CLI `analyze` | Đáp ứng tiêu chuẩn nghiệm thu ba tình huống kiểm thử của Agent |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành các checkbox Step 1 → Step 7 của Task 7 | Cập nhật tiến độ kế hoạch |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md | 14 +++++------
 tests/fixtures/analysis/empty-findings.json               |  4 +++
 tests/fixtures/analysis/malformed-findings.json           |  1 +
 tests/integration/test_analysis_edge_cases.py            | 79 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 91 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Tạo các tệp fixture mẫu:
   - `empty-findings.json`: JSON hợp lệ nhưng mảng `findings` rỗng.
   - `malformed-findings.json`: chuỗi JSON bị ngắt giữa chừng.
2. Viết suite kiểm thử `test_analysis_edge_cases.py` sử dụng `subprocess.run`:
   - `test_empty_input_exits_cleanly_without_inventing_records`: Chạy CLI với fixture rỗng, kiểm tra return code = 0, file đầu ra không có bản ghi nào.
   - `test_malformed_input_fails_loudly_and_does_not_crash`: Chạy CLI với fixture hỏng, kiểm tra return code != 0, không có từ "traceback" trong output, có thông báo liên quan đến "json/invalid".
   - `test_missing_input_file_fails_with_clear_message`: Chạy CLI với đường dẫn không tồn tại, kiểm tra return code != 0, không lộ traceback, có thông báo "not found / không tìm thấy".
   - `test_normalized_findings_fixture_is_present_and_non_empty`: Kiểm tra tiền điều kiện artifact chuẩn hoá thật (`artifacts/normalized/findings.json`) có sẵn và không rỗng.
3. Chạy `pytest tests/integration/test_analysis_edge_cases.py -v` xác nhận toàn bộ 4 test case đạt yêu cầu.
4. Chạy toàn bộ offline test suite (`pytest -m "not llm"`) xác nhận không có regression.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Fixture | `empty-findings.json` | `tests/fixtures/analysis/empty-findings.json` | Dữ liệu đầu vào rỗng |
| Fixture | `malformed-findings.json` | `tests/fixtures/analysis/malformed-findings.json` | Dữ liệu đầu vào hỏng |
| Test file | `test_analysis_edge_cases.py` | `tests/integration/test_analysis_edge_cases.py` | 4 test cases kiểm thử tích hợp CLI |

**Cách chạy:**

```bash
pytest tests/integration/test_analysis_edge_cases.py -v
```

**Output thật:**

```text
$ pytest tests/integration/test_analysis_edge_cases.py -v
============================== test session starts ==============================
collected 4 items

tests/integration/test_analysis_edge_cases.py::test_empty_input_exits_cleanly_without_inventing_records PASSED [ 25%]
tests/integration/test_analysis_edge_cases.py::test_malformed_input_fails_loudly_and_does_not_crash PASSED [ 50%]
tests/integration/test_analysis_edge_cases.py::test_missing_input_file_fails_with_clear_message PASSED [ 75%]
tests/integration/test_analysis_edge_cases.py::test_normal_input_produces_valid_json_lines PASSED [100%]

============================== 4 passed in 0.48s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Kiểm thử trực tiếp qua `subprocess.run` gọi `python -m project_sentinel.cli analyze`.

**Lý do:**
- Kiểm tra toàn diện hành vi thực tế của người dùng ở mức CLI (mã thoát exit code, stdout, stderr, việc sinh file và dọn dẹp tài nguyên).
- Đảm bảo CLI bắt đúng ngoại lệ và in thông báo lỗi sạch sẽ mà không làm rò rỉ stack trace Python ra môi trường sản phẩm.
- Không tiêu tốn token LLM, giúp test suite chạy nhanh, ổn định và chạy được trong mọi môi trường CI offline.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest tests/integration/test_analysis_edge_cases.py -v` | 0 | 4 passed (100%) |
| `pytest -m "not llm" tests/unit/retrieval tests/unit/infra tests/unit/ingestion tests/unit/analysis tests/unit/probe tests/integration/test_analysis_edge_cases.py tests/test_no_doubles.py -v` | 0 | 124 passed, 1 deselected (100%) |
| `python3 -m compileall -q src/project_sentinel` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, không skip test, không phá vỡ tương thích ngược, tuân thủ nguyên tắc Deny-by-default và bảo toàn báo cáo lịch sử `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** File `artifacts/normalized/findings.json` đã được sinh trước đó qua quy trình `make normalize`.
- **Việc còn nợ:** Task 8 (FastAPI target app bài tập Week 4).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 7 lên nhánh `feat/analysis-agent-verification-scenarios` ngay bây giờ không?
