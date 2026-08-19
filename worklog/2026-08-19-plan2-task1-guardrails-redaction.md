# Worklog — Plan 2: Task 1 - Guardrails Redaction

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 1 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-redaction` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã tạo package `guardrails` và module `redaction.py` để che các loại dữ liệu nhạy cảm (email, phone VN có dấu cách/gạch, JWT, API key, password mở rộng, CCCD/thẻ tín dụng). Module đã áp dụng cơ chế phát hiện cycle và duyệt tuple/set (từ commit `99b2f00`), khắc phục các lỗi nhận diện mẫu và hồi quy quan trọng (bảo vệ hash provenance Git SHA/sha256, duyệt đệ quy cây con trong `skip_keys`, giữ nguyên key của dict chống mất dữ liệu, tách mẫu password theo Phương án B tránh nuốt câu văn xuôi mô tả đồng thời bỏ giới hạn 64 ký tự ở nhánh `=` để che trọn vẹn mật khẩu dài, loại dấu chấm khỏi phone regex tránh bắt nhầm số thập phân `elapsed_ms`, gộp sự kiện cùng loại trong `redact()`). Kết quả: 28 unit test pass 100%, toàn bộ suite 204 test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp hàm `redact()` để che chuỗi đơn lẻ và `redact_structure()` để duyệt đệ quy cấu trúc dữ liệu (dict, list, tuple, set) nhằm che dữ liệu nhạy cảm, đồng thời thống kê số lượng sự kiện `RedactionEvent`.
- **Nằm ở đâu trong luồng:** Nằm ở tầng nền tảng của package `guardrails/` trong Plan 2, làm dependency trực tiếp cho 2 nút thắt cổ chai ở Task 2 (`llm/redacting.py`) và Task 3 (`gateway/request_log.py`), cũng như `events.py` ở Task 6.
- **Không có nó thì hỏng gì:** Dữ liệu nhạy cảm từ mã nguồn quét được hoặc từ response của ứng dụng đích sẽ bị rò rỉ ra external LLM provider hoặc bị ghi dưới dạng plaintext trong audit log; hoặc ngược lại nếu che nhầm hash provenance hay nuốt câu mô tả thì phá hỏng ngữ nghĩa và bằng chứng chấm điểm.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp trực tiếp vào `build_llm()` hay `log_request()` (thuộc Task 2 và Task 3 của Plan 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/__init__.py` | Tạo mới | Khởi tạo package `guardrails` và export `RedactionEvent`, `redact`, `redact_structure` | Định nghĩa API công khai của package guardrails |
| `src/project_sentinel/guardrails/redaction.py` | Tạo mới / Sửa | 1. Tích hợp xử lý tuple/set và cycle detection (`seen: set[int]`, trả `"[CYCLE]"`) từ commit `99b2f00`.<br>2. Bỏ hex trần khỏi `api_key`, thêm pattern hex có ngữ cảnh bí mật (`api_key=`, `secret=`, v.v.) để bảo vệ Git SHA/sha256 hash.<br>3. Sửa `walk()` để `skip_keys` chỉ bỏ qua scalar, vẫn duyệt đệ quy cây con.<br>4. Giữ nguyên key của dict trong `walk()` để tránh va chạm key làm mất dữ liệu.<br>5. Áp dụng Phương án B cho password: phân cách `=` cho phép giá trị khoảng trắng không giới hạn độ dài `+` (che trọn vẹn mật khẩu dài > 64 ký tự), phân cách `:` chỉ ăn từ đơn để không nuốt văn xuôi.<br>6. Bỏ dấu `.` khỏi phone separator để không ăn nhầm số thập phân `elapsed_ms 0.123...`.<br>7. Gọi `_merge(events)` trong `redact()` để gộp sự kiện trùng loại. | Thực thi logic che dữ liệu nhạy cảm an toàn và chuẩn xác |
| `tests/unit/guardrails/__init__.py` | Tạo mới | Khởi tạo test package cho guardrails unit tests | Test namespace |
| `tests/unit/guardrails/test_redaction.py` | Tạo mới / Mở rộng | 28 unit test cases kiểm thử tất cả các loại dữ liệu nhạy cảm, tuple/set, cycle detection, hash preservation, nested skip_keys, password variants & prose protection & 100-char password, phone formats & decimal protection, dict key integrity, pii false-positive prevention, và event merging | Chứng minh tính đúng đắn |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–7 của Task 1 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md |  14 +-
 src/project_sentinel/guardrails/__init__.py                      |   9 ++
 src/project_sentinel/guardrails/redaction.py                     | 126 +++++++++++++
 tests/unit/guardrails/__init__.py                                |   1 +
 tests/unit/guardrails/test_redaction.py                          | 193 +++++++++++++++++++
 worklog/2026-08-19-plan2-task1-guardrails-redaction.md           | 210 ++++++++++++++++++++++
 6 files changed, 546 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **Phát hiện chu trình (Cycle Detection):** Dùng `seen: set[int]` lưu `id(node)` trong `redact_structure()`, trả `"[CYCLE]"` nếu gặp lại đối tượng đang duyệt trong ngăn xếp đệ quy, hỗ trợ đầy đủ `dict`, `list`, `tuple`, `set`.
2. **Bảo vệ Hash Provenance:** Tách `api_key` thành 2 nhánh:
   - Các API key có prefix định danh: `sk-[A-Za-z0-9_-]{16,}`, `ghp_[A-Za-z0-9]{20,}`.
   - Các chuỗi Hex 32+ chỉ bị che khi đi liền với từ khóa ngữ cảnh: `(?i)(\b(?:api[_-]?key|secret|token|passwd|SENTINEL_GATEWAY_API_KEY)\s*[:=]\s*["']?)[A-Fa-f0-9]{32,}(["']?)`.
3. **Duyệt sâu qua `skip_keys` & Bảo toàn key của dict:** Khi `key in skip_keys`, chỉ trả nguyên `node` nếu nó là scalar. Giữ nguyên key của dict `name: walk(item, name)` để tránh va chạm làm mất dữ liệu khi nhiều key bị che thành cùng một chuỗi placeholder.
4. **Bảo vệ văn xuôi mô tả & Che trọn vẹn mật khẩu dài (Phương án B):**
   - Phân cách `:`: `(\"?\b(?:password|passwd|pwd|pass)\"?\s*:\s*)("[^"]*"|'[^']*'|[^\s&,};)]+)` — chỉ ăn tới khoảng trắng đầu tiên nếu không có nháy (bảo vệ các câu như `"Reset password: click here"`).
   - Phân cách `=`: `(\"?\b(?:password|passwd|pwd|pass)\"?\s*=\s*)("[^"]*"|'[^']*'|[^\r\n&,};)]+)` — dùng `+` thay vì giới hạn `{1,64}` để che trọn vẹn mật khẩu dài (ví dụ 100 ký tự không bị sót 36 ký tự đuôi).
5. **Số điện thoại Việt Nam & Bảo vệ số thập phân:** Regex `(?:\+84|(?:\b84)|\b0)(?:[\s-]?\d){9}\b` chỉ cho phép dấu cách và gạch nối (không cho phép dấu chấm), tránh ăn nhầm `elapsed_ms 0.123456789` hay version `0.1.2.3...`.
6. **Gộp sự kiện trong `redact()`:** Gọi `_merge(events)` trước khi trả về từ `redact()` để các sự kiện trùng `kind` được tính tổng `count` chính xác.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Dataclass | `RedactionEvent` | `RedactionEvent(kind: str, count: int)` | Lưu trữ loại và số lượng dữ liệu đã che |
| Constant | `SKIP_KEYS` | `frozenset[str]` | Tập hợp các khoá provenance không che |
| Function | `redact` | `redact(text: str) -> tuple[str, list[RedactionEvent]]` | Che dữ liệu trong chuỗi, gộp sự kiện theo loại |
| Function | `redact_structure` | `redact_structure(value: Any, skip_keys: frozenset[str]) -> tuple[Any, list[RedactionEvent]]` | Che dữ liệu đệ quy trong dict/list/tuple/set, chống cycle, bảo toàn dict keys |
| Test file | `test_redaction.py` | `tests/unit/guardrails/test_redaction.py` | 28 unit tests toàn diện |

**Cách chạy:**

```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_redaction.py -v
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Regex tĩnh theo ngữ cảnh kết hợp logic đệ quy duyệt cây thuần Python, dùng `id()` set tracker cho cycle detection, và áp dụng Phương án B phân tách dấu phân cách cho password kết hợp `+` tham lam đầy đủ cho nhánh `=`.

**Lý do:**
- Thỏa mãn ràng buộc của đề bài và Plan 2: *"Python ≥3.10, `re` thư viện chuẩn, pytest. Không thêm dependency mới."*
- Tốc độ microsecond, deterministic 100%, không bị tràn stack khi cấu trúc dữ liệu tự tham chiếu.
- Phân biệt rạch ròi giữa hash kỹ thuật và secret thông qua keyword boundary context.
- Bảo vệ các trường số thực như `elapsed_ms` và văn xuôi mô tả của các finding bảo mật, đồng thời không để sót mẩu mật khẩu dài nào khi gán qua dấu `=`.

---

## 7. Kiểm chứng

### Bằng chứng test bắt lỗi mật khẩu dài > 64 ký tự bị sót (khi dùng `{1,64}`)

```text
=================================== FAILURES ===================================
_______________ test_very_long_password_value_is_fully_redacted ________________

    def test_very_long_password_value_is_fully_redacted():
        """Mật khẩu dài hơn 64 ký tự không được để sót một mảnh nào."""
        out, _ = redact("password=" + "X" * 100)
>       assert "X" not in out
E       AssertionError: assert 'X' not in 'password=[R...XXXXXXXXXXXX'
E         'X' is contained here:
E           password=[REDACTED_PASSWORD]XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
E         ?                                                                +

tests/unit/guardrails/test_redaction.py:240: AssertionError
======================= 1 failed, 27 deselected in 0.08s =======================
```

### Bằng chứng sau khi sửa `{1,64}` thành `+`

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 28 items

tests/unit/guardrails/test_redaction.py::test_email_is_redacted PASSED   [  3%]
tests/unit/guardrails/test_redaction.py::test_vietnamese_phone_is_redacted PASSED [  7%]
tests/unit/guardrails/test_redaction.py::test_jwt_is_redacted PASSED     [ 10%]
tests/unit/guardrails/test_redaction.py::test_openai_style_api_key_is_redacted PASSED [ 14%]
tests/unit/guardrails/test_redaction.py::test_long_hex_secret_is_redacted PASSED [ 17%]
tests/unit/guardrails/test_redaction.py::test_password_value_is_redacted_but_key_name_survives PASSED [ 21%]
tests/unit/guardrails/test_redaction.py::test_password_in_query_string_form_is_redacted PASSED [ 25%]
tests/unit/guardrails/test_redaction.py::test_card_number_is_redacted PASSED [ 28%]
tests/unit/guardrails/test_redaction.py::test_cccd_twelve_digits_is_redacted PASSED [ 32%]
tests/unit/guardrails/test_redaction.py::test_clean_text_is_returned_unchanged_with_no_events PASSED [ 35%]
tests/unit/guardrails/test_redaction.py::test_multiple_occurrences_are_counted PASSED [ 39%]
tests/unit/guardrails/test_redaction.py::test_empty_and_non_string_inputs_are_safe PASSED [ 42%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_walks_nested_dicts_and_lists PASSED [ 46%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_does_not_touch_provenance_fields PASSED [ 50%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_preserves_non_string_scalars PASSED [ 53%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_handles_tuples_and_sets PASSED [ 57%]
tests/unit/guardrails/test_redaction.py::test_redact_structure_handles_self_referential_cycle PASSED [ 60%]
tests/unit/guardrails/test_redaction.py::test_git_commit_sha_and_sha256_hashes_are_not_redacted PASSED [ 64%]
tests/unit/guardrails/test_redaction.py::test_contextual_hex_secret_is_redacted PASSED [ 67%]
tests/unit/guardrails/test_redaction.py::test_skip_keys_walks_nested_structures PASSED [ 71%]
tests/unit/guardrails/test_redaction.py::test_password_field_name_variants_and_spaced_values PASSED [ 75%]
tests/unit/guardrails/test_redaction.py::test_password_pattern_does_not_swallow_prose_descriptions PASSED [ 78%]
tests/unit/guardrails/test_redaction.py::test_vietnamese_phone_formats_with_spaces_and_dashes PASSED [ 82%]
tests/unit/guardrails/test_redaction.py::test_phone_pattern_does_not_flag_decimals_or_line_numbers PASSED [ 85%]
tests/unit/guardrails/test_redaction.py::test_dict_keys_are_kept_intact_to_avoid_key_collisions PASSED [ 89%]
tests/unit/guardrails/test_redaction.py::test_pii_pattern_does_not_flag_build_ids_or_byte_counts PASSED [ 92%]
tests/unit/guardrails/test_redaction.py::test_redact_merges_multiple_events_of_same_kind PASSED [ 96%]
tests/unit/guardrails/test_redaction.py::test_very_long_password_value_is_fully_redacted PASSED [100%]

============================== 28 passed in 0.04s ==============================
```

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_redaction.py -v` | 0 | **28 passed** in 0.04s |
| `PYTHONPATH=src python3 -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **204 passed**, 13 deselected in 1.61s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |

---

## 8. Cần người review kỹ ở đâu

- **Ghi nhận về quyết định thiết kế Password:** Ở lần sửa trước, khi xử lý vấn đề password nuốt văn xuôi, hai phương án đã được đưa ra:
  - *(A) An toàn hơn: Giá trị không dấu nháy chỉ ăn tới khoảng trắng đầu tiên với mọi dấu phân cách.*
  - *(B) Phân tách theo dấu phân cách: Dấu `:` chỉ ăn từ đơn để bảo vệ văn xuôi; dấu `=` cho phép khoảng trắng để che trọn vẹn mật khẩu.*
  Phương án (B) đã được lựa chọn và duyệt, sau đó được tinh chỉnh bỏ giới hạn `{1,64}` sang `+` ở nhánh `=` để đảm bảo mật khẩu dài (ví dụ > 64 ký tự) không bị sót bất kỳ ký tự nào.
- **Giả định đã đặt:** Giả định các chuỗi hex trần (không có keyword ngữ cảnh bí mật) là hash provenance (Git commit SHA, SHA256) nên được giữ nguyên.
- **Việc còn nợ:** Task 2 của Plan 2 (kết nối `RedactingProvider` vào `build_llm()`).
- **Câu hỏi cho người dùng:** Không có.
