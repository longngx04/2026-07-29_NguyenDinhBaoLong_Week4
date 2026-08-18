# Worklog — Task 4: Thêm `verification_objective` vào schema record

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/w1-w4-task4-verification-objective-schema` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 4

---

## 1. Tóm tắt

- Mở rộng JSON Schema [`schemas/security-analysis-record.schema.json`](../schemas/security-analysis-record.schema.json) để định nghĩa trường `verification_objective` dạng nullable và không nằm trong `required`, bảo toàn 100% tương thích ngược với các record phân tích cũ.
- Khi có `verification_objective`, bắt buộc phải có đầy đủ 4 trường (`description`, `endpoint_hint`, `payload_kind`, `rationale`), `endpoint_hint` phải khớp pattern `^(GET|POST) /[^ ?]*$`, `payload_kind` bị giới hạn trong đúng 4 enum an toàn (`long_string`, `special_chars`, `empty_value`, `wrong_type`), và chặn mọi `additionalProperties`.
- Chuẩn hoá trường `description` ở đầu schema (loại bỏ tag ngữ cảnh `(Week 3)`).
- Kết quả: 6/6 unit tests mới trong `test_verification_objective_schema.py` pass, 35/35 analysis unit tests pass, và 99/99 toàn bộ offline test suite xanh sạch.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Định nghĩa cấu trúc hợp lệ cho mục tiêu kiểm chứng động (`verification_objective`) mà LLM Security Analysis Agent sẽ đề xuất ở các bước tiếp theo (Task 5 & Task 6).
- **Nằm ở đâu trong luồng:** Schema nằm tại `schemas/security-analysis-record.schema.json`, được sử dụng bởi validator `project_sentinel.analysis.validators.validate_record_schema()` để hậu kiểm kết quả sau khi LLM phân tích finding group.
- **Không có nó thì hỏng gì:** Nếu không cập nhật schema, khi LLM sinh trường `verification_objective` ở Task 5, validator sẽ từ chối record do vi phạm `"additionalProperties": false`. Nếu định nghĩa lỏng lẻo không giới hạn enum hay pattern, các payload/endpoint độc hại hoặc không an toàn có thể lọt qua.
- **Ngoài phạm vi (cố ý không làm):** Chưa thay đổi prompt của LLM hay logic sinh prompt (việc này thuộc về Task 5).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `schemas/security-analysis-record.schema.json` | Sửa | Thêm định nghĩa property `verification_objective` dạng `oneOf: [{type: null}, {type: object, ...}]`, chuẩn hoá description đầu file | Mở rộng schema theo yêu cầu Task 4 |
| `tests/unit/analysis/test_verification_objective_schema.py` | Tạo mới | Viết 6 test cases: tương thích khi thiếu field, chấp nhận null, chấp nhận object hợp lệ, chặn enum payload lạ, chặn thiếu field, chặn field lạ | Kiểm chứng khóa chặt validation schema theo TDD |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành các checkbox Step 1 → Step 6 của Task 4 | Cập nhật tiến độ kế hoạch |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md          |  12 ++--
 schemas/security-analysis-record.schema.json                       |  24 ++++++-
 tests/unit/analysis/test_verification_objective_schema.py          | 104 +++++++++++++++++++++++++++
 3 files changed, 131 insertions(+), 9 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Áp dụng quy trình TDD Red-Green:
   - Tạo trước `tests/unit/analysis/test_verification_objective_schema.py`.
   - Chạy test và xác nhận 2 test case (`test_record_with_null_verification_objective_is_valid` và `test_record_with_full_verification_objective_is_valid`) FAIL do schema cũ chưa có `verification_objective`.
2. Bổ sung định nghĩa `verification_objective` vào `schemas/security-analysis-record.schema.json`:
   ```json
   "verification_objective": {
     "oneOf": [
       { "type": "null" },
       {
         "type": "object",
         "required": ["description", "endpoint_hint", "payload_kind", "rationale"],
         "additionalProperties": false,
         "properties": {
           "description": { "type": "string", "minLength": 1 },
           "endpoint_hint": {
             "type": "string",
             "pattern": "^(GET|POST) /[^ ?]*$"
           },
           "payload_kind": {
             "type": "string",
             "enum": ["long_string", "special_chars", "empty_value", "wrong_type"]
           },
           "rationale": { "type": "string", "minLength": 1 }
         }
       }
     ]
   }
   ```
3. Chạy lại test suite để xác nhận 6/6 tests chuyển sang PASS (Green).
4. Chạy toàn bộ offline test suite (`pytest -m "not llm"`) xác nhận không có regression đối với các record cũ.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Schema Property | `verification_objective` | `schemas/security-analysis-record.schema.json` | Cấu trúc mục tiêu kiểm chứng động an toàn |
| File Test | `test_verification_objective_schema.py` | `tests/unit/analysis/test_verification_objective_schema.py` | 6 unit test cases kiểm thử schema |

**Cách chạy:**

```bash
pytest tests/unit/analysis/test_verification_objective_schema.py -v
pytest -m "not llm" tests/unit/analysis -v
```

**Output thật:**

```text
$ pytest tests/unit/analysis/test_verification_objective_schema.py -v
============================== test session starts ==============================
collected 6 items

tests/unit/analysis/test_verification_objective_schema.py::test_record_without_verification_objective_is_still_valid PASSED [ 16%]
tests/unit/analysis/test_verification_objective_schema.py::test_record_with_null_verification_objective_is_valid PASSED [ 33%]
tests/unit/analysis/test_verification_objective_schema.py::test_record_with_full_verification_objective_is_valid PASSED [ 50%]
tests/unit/analysis/test_verification_objective_schema.py::test_unknown_payload_kind_is_rejected PASSED [ 66%]
tests/unit/analysis/test_verification_objective_schema.py::test_missing_field_inside_objective_is_rejected PASSED [ 83%]
tests/unit/analysis/test_verification_objective_schema.py::test_extra_field_inside_objective_is_rejected PASSED [100%]

============================== 6 passed in 0.13s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** `oneOf` với `{ "type": "null" }` và `{ "type": "object", ... }`, không đưa vào mảng `required`.

**Lý do:**
- Đảm bảo tương thích ngược hoàn hảo: các record phân tích cũ không có trường này hoặc có giá trị `null` đều hợp lệ.
- Kiểm soát bảo mật chặt chẽ: khi có object, bắt buộc phải có đầy đủ 4 trường, cấm các trường bổ sung ngoài ý muốn (`additionalProperties: false`), chặn các URL/path ngoài quy chuẩn qua regex pattern, và giới hạn đúng 4 payload an toàn qua enum.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest tests/unit/analysis/test_verification_objective_schema.py -v` | 0 | 6 passed (100%) |
| `pytest -m "not llm" tests/unit/analysis -v` | 0 | 35 passed, 1 deselected (100%) |
| `pytest -m "not llm" tests/unit/retrieval tests/unit/infra tests/unit/ingestion tests/unit/analysis tests/test_no_doubles.py -v` | 0 | 99 passed, 1 deselected (100%) |
| `python3 -m compileall -q src/project_sentinel` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, không skip test, không phá vỡ tương thích ngược, không xâm phạm báo cáo lịch sử `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Pattern regex của `endpoint_hint`: `^(GET|POST) /[^ ?]*$` — kiểm tra phương thức HTTP viết hoa và path bắt đầu bằng `/`, không chứa query param `?` hoặc khoảng trắng.
- **Giả định đã đặt:** `verification_objective` được sinh ở Task 5 chỉ sử dụng 4 loại payload an toàn đã thống nhất.
- **Việc còn nợ:** Task 5 (Đưa allowlist vào packet và dạy agent chọn endpoint/payload phù hợp).
- **Câu hỏi cho người dùng:** Bạn có muốn commit Task 4 lên nhánh `feat/w1-w4-task4-verification-objective-schema` ngay bây giờ không?
