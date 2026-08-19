# Worklog — Plan 2: Task 1 - Guardrails Redaction

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 1 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-redaction` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã tạo package `guardrails` và triển khai module `redaction.py` để che các loại dữ liệu nhạy cảm (email, số điện thoại VN, JWT token, API key, password, PII/CCCD/thẻ tín dụng). Phục vụ bảo vệ thông tin cá nhân và credentials trước khi gửi prompt ra LLM hoặc ghi audit log. Kết quả: 15 unit test mới pass 100%, toàn bộ suite 191 test không regression.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp hàm `redact()` để che chuỗi đơn lẻ và `redact_structure()` để duyệt đệ quy cấu trúc dữ liệu (dict, list) nhằm che dữ liệu nhạy cảm, đồng thời thống kê số lượng sự kiện `RedactionEvent`.
- **Nằm ở đâu trong luồng:** Nằm ở tầng nền tảng của package `guardrails/` trong Plan 2, làm dependency trực tiếp cho 2 nút thắt cổ chai ở Task 2 (`llm/redacting.py`) và Task 3 (`gateway/request_log.py`), cũng như `events.py` ở Task 6.
- **Không có nó thì hỏng gì:** Dữ liệu nhạy cảm từ mã nguồn quét được hoặc từ response của ứng dụng đích sẽ bị rò rỉ ra external LLM provider hoặc bị ghi dưới dạng plaintext trong audit log.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp trực tiếp vào `build_llm()` hay `log_request()` (thuộc Task 2 và Task 3 của Plan 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/__init__.py` | Tạo mới | Khởi tạo package `guardrails` và export `RedactionEvent`, `redact`, `redact_structure` | Định nghĩa API công khai của package guardrails |
| `src/project_sentinel/guardrails/redaction.py` | Tạo mới | Triển khai regex redaction theo thứ tự hẹp trước rộng sau, hàm `redact()` và `redact_structure()`, giữ nguyên `SKIP_KEYS` | Thực thi logic che dữ liệu nhạy cảm |
| `tests/unit/guardrails/__init__.py` | Tạo mới | Khởi tạo test package cho guardrails unit tests | Test namespace |
| `tests/unit/guardrails/test_redaction.py` | Tạo mới | 15 unit test cases kiểm thử tất cả các loại dữ liệu nhạy cảm, đệ quy dict/list, và bảo toàn provenance keys | Chứng minh tính đúng đắn |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–7 của Task 1 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md |  14 +-
 src/project_sentinel/guardrails/__init__.py                      |   9 ++
 src/project_sentinel/guardrails/redaction.py                     | 101 +++++++++++++
 tests/unit/guardrails/__init__.py                                |   1 +
 tests/unit/guardrails/test_redaction.py                          | 106 ++++++++++++++
 worklog/2026-08-19-plan2-task1-guardrails-redaction.md           | 162 +++++++++++++++++++++
 6 files changed, 386 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. Định nghĩa 6 nhóm mẫu regex: password (bắt key-value), JWT token, API key (OpenAI sk-, GitHub ghp-, hex 32+), email RFC, PII (CCCD 12 số, số thẻ 16 số), phone VN (09xx, +84xx).
2. Sắp xếp thứ tự regex theo nguyên tắc: mẫu hẹp/đặc thù chạy trước (password, JWT) để không bị mẫu rộng hơn (hex, PII) bắt nhầm.
3. `redact()` dùng `pattern.subn()` để vừa thay thế vừa đếm số lượng thay đổi, trả về kết quả kèm danh sách `RedactionEvent`.
4. `redact_structure()` duyệt đệ quy cây dict/list, giữ nguyên các trường provenance được định nghĩa trong `SKIP_KEYS` (`prompt_sha256`, `analysis_id`, `request_id`, `run_id`, `group_key`).

**Luồng dữ liệu:** `text / dict / list` → `walk()` → `pattern.subn()` (bỏ qua `skip_keys`) → `(cleaned_data, merged_events)`

**Các quyết định kỹ thuật:**
- Không sửa/che các khóa provenance để tránh làm sai lệch hash đối chiếu chấm điểm.
- Giữ nguyên các kiểu dữ liệu non-string scalars (int, bool, None) trong `redact_structure()`.
- Sử dụng frozen dataclass `RedactionEvent` để đảm bảo immutability.

**Xử lý lỗi / trường hợp biên:**
- Chuỗi rỗng `""` hoặc `None`: trả về an toàn `("", [])` hoặc `(None, [])` không crash.
- Key đóng ngoặc kép hoặc gán bằng dấu hai chấm/dấu bằng trong password.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Dataclass | `RedactionEvent` | `RedactionEvent(kind: str, count: int)` | Lưu trữ loại và số lượng dữ liệu đã che |
| Constant | `SKIP_KEYS` | `frozenset[str]` | Tập hợp các khoá provenance không che |
| Function | `redact` | `redact(text: str) -> tuple[str, list[RedactionEvent]]` | Che dữ liệu trong chuỗi |
| Function | `redact_structure` | `redact_structure(value: Any, skip_keys: frozenset[str]) -> tuple[Any, list[RedactionEvent]]` | Che dữ liệu đệ quy trong cấu trúc dict/list |
| Test file | `test_redaction.py` | `tests/unit/guardrails/test_redaction.py` | 15 unit tests cho redaction |

**Cách chạy:**

```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_redaction.py -v
```

**Output thật (đã che secret):**

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 15 items

tests/unit/guardrails/test_redaction.py::test_email_is_redacted PASSED   [  6%]
tests/unit/guardrails/test_redaction.py::test_vietnamese_phone_is_redacted PASSED [ 13%]
tests/unit/guardrails/test_redaction.py::test_jwt_is_redacted PASSED     [ 20%]
tests/unit/guardrails/test_redaction.py::test_openai_style_api_key_is_redacted PASSED [ 26%]
tests/unit/guardrails/test_redaction.py::test_long_hex_secret_is_redacted PASSED [ 33%]
tests/unit/guardrails/test_redaction.py::test_password_value_is_redacted_but_key_name_survives PASSED [ 40%]
tests/unit/guardrails/test_redaction.py::test_password_in_query_string_form_is_redacted PASSED [ 46%]
tests/unit/guardrails/test_redaction.py::test_card_number_is_redacted PASSED [ 53%]
tests/unit/guardrails/test_redaction.py::test_cccd_twelve_digits_is_redacted PASSED [ 60%]
tests/unit/guardrails/test_clean_text_is_returned_unchanged_with_no_events PASSED [ 66%]
tests/unit/guardrails/test_redaction.py::test_multiple_occurrences_are_counted PASSED [ 73%]
tests/unit/guardrails/test_redaction.py::test_empty_and_non_string_inputs_are_safe PASSED [ 80%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_walks_nested_dicts_and_lists PASSED [ 86%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_does_not_touch_provenance_fields PASSED [ 93%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_preserves_non_string_scalars PASSED [100%]

============================== 15 passed in 0.03s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Sử dụng `re.Pattern` đã biên dịch tĩnh và `subn` kết hợp duyệt cây thuần Python, không thêm external dependencies (như Microsoft Presidio hay spaCy).

**Lý do:**
- Thỏa mãn ràng buộc của đề bài và Plan 2: *"Python ≥3.10, `re` thư viện chuẩn, pytest. Không thêm dependency mới."*
- Tốc độ xử lý microsecond, deterministic 100%, không phát sinh tải CPU từ NLP models.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Dùng thư viện NER (Presidio, Spacy) | Nhận diện ngữ cảnh linh hoạt hơn | Thêm heavy dependencies, chậm, không deterministic và vi phạm quy định zero new dependency |
| Thay thế bằng chuỗi rỗng `""` | Gọn hơn | Khó phân biệt giữa dữ liệu rỗng tự nhiên và dữ liệu bị che bảo mật |

**Đánh đổi đã chấp nhận:** Regex có thể có false positive ở một số chuỗi hex ngẫu nhiên 32+ ký tự không phải key (nhưng đã có `SKIP_KEYS` bảo vệ các khoá cốt lõi).

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_redaction.py -v` | 0 | 15 passed in 0.03s |
| `PYTHONPATH=src python3 -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 191 passed, 13 deselected in 1.71s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |

**Test mới thêm:**
- `tests/unit/guardrails/test_redaction.py` (15 test cases bao phủ email, phone, jwt, sk- key, hex secret, password query/json, cccd, credit card, provenance preservation, scalar preservation).

**Bất biến đã giữ:**
- Zero test doubles (no mock/stub/fake).
- Không có week identifier trong code production.
- Không log/print secret.
- Đầy đủ `__init__.py` và `__all__`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/guardrails/redaction.py:211-244` — Regex bắt `password` hỗ trợ cả JSON `{"password": "val"}` lẫn query parameter `password=val&next=...`. Cần kiểm tra xem có trường hợp format password đặc thù nào khác trong WebGoat cần hỗ trợ không.
- **Giả định đã đặt:** Giả định các khóa provenance trong `SKIP_KEYS` đủ để bao quát mọi trường không được che trong pipeline phân tích.
- **Việc còn nợ:** Task 2 của Plan 2 (kết nối `RedactingProvider` vào `build_llm()`).
- **Câu hỏi cho người dùng:** Không có.
