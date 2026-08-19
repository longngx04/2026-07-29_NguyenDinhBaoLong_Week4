# Worklog — Plan 2: Task 2 - LLM Redaction Chokepoint

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 2 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-llm-chokepoint` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã thiết lập nút thắt cổ chai bảo mật thứ nhất tại `build_llm()` bằng việc tạo `RedactingProvider` bọc ngoài mọi `LLMProvider`. Đã áp dụng nguyên tắc "che mặc định mọi trường trong `AnalysisPacket` trừ danh sách được miễn trừ rõ ràng (`_UNREDACTED_FIELDS`)", khóa chặt không cho phép bất kỳ module production nào khởi tạo thô `OpenRouterClient`, và gộp danh sách `last_redaction_events` qua `_merge()`. Kết quả: 10 unit test chokepoint pass 100%, toàn bộ suite 214 test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đóng vai trò là chokepoint (nút thắt cổ chai bắt buộc) bao bọc quanh `LLMProvider`, tự động làm sạch các trường dữ liệu nhạy cảm (email, credentials, tokens, PII) trong `AnalysisPacket` và các prompt trước khi gửi tới external LLM.
- **Nằm ở đâu trong luồng:** Nằm tại tầng `llm/`, giữa pipeline phân tích (`analysis/pipeline.py`) và client gọi API bên ngoài (`llm/openrouter.py`).
- **Không có nó thì hỏng gì:** Các module gọi LLM có thể vô tình gửi trực tiếp nội dung chứa PII / credentials của khách hàng hoặc source code lên OpenRouter / External LLM provider, hoặc khi `AnalysisPacket` được mở rộng thêm trường mới trong tương lai sẽ bị rò rỉ dữ liệu do bỏ sót che.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp bộ che log tại `log_request()` (thuộc Task 3 của Plan 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/llm/redacting.py` | Tạo mới / Sửa | 1. Tạo class `RedactingProvider` triển khai `LLMProvider` protocol.<br>2. Đảo logic sang che mặc định mọi trường của `AnalysisPacket` (duyệt `fields(packet)`), chỉ giữ nguyên tập `_UNREDACTED_FIELDS` (`group_key`, `task`, `output_language`, `output_schema`, `allowed_endpoints`).<br>3. Gộp `last_redaction_events` qua `_merge()` ở cả `analyze()` và `generate()`. | Thực thi lớp proxy bọc ngoài LLM provider an toàn mặc định |
| `src/project_sentinel/llm/factory.py` | Sửa | `build_llm()` luôn bọc provider thật bên trong `RedactingProvider` | Nơi duy nhất khởi tạo provider, đảm bảo không code path nào lách được |
| `tests/unit/guardrails/test_llm_redaction_chokepoint.py` | Tạo mới / Mở rộng | 10 unit test: kiểm tra che email, password trong evidence, giữ nguyên group_key, kiểm tra factory, kiểm tra tính toàn vẹn của `_UNREDACTED_FIELDS`, kiểm tra che mọi trường non-exempt, guard test chống tạo thô `OpenRouterClient` trong production, và kiểm tra gộp `last_redaction_events`. | Chứng minh tính đúng đắn và bất biến bảo mật |
| `tests/unit/llm/test_openrouter.py` | Sửa | Cập nhật `test_provider_factory_openrouter` để kiểm tra `llm.inner` là `OpenRouterClient` | Khớp với kiến trúc bọc provider mới |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–7 của Task 2 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md   |  14 +--
 src/project_sentinel/llm/factory.py                                |  23 ++--
 src/project_sentinel/llm/redacting.py                              |  63 +++++++++++
 tests/unit/guardrails/test_llm_redaction_chokepoint.py            | 121 ++++++++++++++++++++
 tests/unit/llm/test_openrouter.py                                  |   2 +-
 worklog/2026-08-19-plan2-task2-llm-redaction-chokepoint.md         | 160 ++++++++++++++++++++++++++
 6 files changed, 362 insertions(+), 21 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **An toàn mặc định (Deny-by-default on fields):** Thay vì hardcode che 3 trường cụ thể, `analyze()` duyệt qua toàn bộ `dataclasses.fields(packet)`:
   - Nếu trường nằm trong `_UNREDACTED_FIELDS`: giữ nguyên giá trị (chỉ dành cho metadata tĩnh và provenance).
   - Mọi trường khác: tự động chạy qua `redact_structure()`. Thêm trường mới vào `AnalysisPacket` trong tương lai sẽ tự động được che, tránh rò rỉ âm thầm.
2. **Gộp sự kiện thống nhất:** Mọi sự kiện phát sinh từ việc che các trường của packet và `system_prompt`/`user_prompt` đều được chuyển qua hàm `_merge()` trước khi gán vào `self.last_redaction_events`.
3. **Khóa cửa sau bằng Guard Test:** Thêm test `test_no_production_module_constructs_the_raw_provider` quét cây `src/project_sentinel/` để đảm bảo không file production nào (ngoài `factory.py` và `openrouter.py`) tự ý gọi constructor `OpenRouterClient(...)`.
4. **Tại `build_llm()` trong `llm/factory.py`:** Luôn trả về `RedactingProvider(OpenRouterClient(...))`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Set | `_UNREDACTED_FIELDS` | `frozenset[str]` trong `llm/redacting.py` | Danh sách trắng các trường không che của AnalysisPacket |
| Class | `RedactingProvider` | `src/project_sentinel/llm/redacting.py` | LLMProvider wrapper che sạch prompt trước khi gọi inner provider |
| Function | `build_llm` | `src/project_sentinel/llm/factory.py` | Factory luôn trả provider đã được bọc RedactingProvider |
| Test file | `test_llm_redaction_chokepoint.py` | `tests/unit/guardrails/test_llm_redaction_chokepoint.py` | 10 unit tests bảo vệ nút thắt LLM redaction |

**Cách chạy:**

```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_llm_redaction_chokepoint.py -v
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Deny-by-default wrapper pattern tại `build_llm()` kết hợp `dataclasses.fields()` reflection và guard test.

**Lý do:**
- Bất kỳ trường dữ liệu mới nào thêm vào `AnalysisPacket` đều mặc định được bảo vệ ngay lập tức mà không cần sửa `redacting.py`.
- Khóa chặt việc khởi tạo trực tiếp client ở tầng test, ngăn ngừa "cửa sau" đi tắt qua factory.
- Đảm bảo `last_redaction_events` không bị phân mảnh thành nhiều sự kiện cùng loại.

---

## 7. Kiểm chứng

### Bằng chứng test chạy thật

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 10 items

tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_analyze_redacts_email_inside_the_packet PASSED [ 10%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_analyze_redacts_nested_source_evidence PASSED [ 20%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_analyze_leaves_clean_content_untouched PASSED [ 30%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_analyze_preserves_group_key_provenance PASSED [ 40%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_generate_redacts_both_prompts PASSED [ 50%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_factory_returns_a_redacting_provider PASSED [ 60%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_every_packet_field_is_either_redacted_or_explicitly_exempt PASSED [ 70%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_every_non_exempt_packet_field_is_actually_redacted PASSED [ 80%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_no_production_module_constructs_the_raw_provider PASSED [ 90%]
tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_last_redaction_events_merges_same_kind_events PASSED [100%]

============================== 10 passed in 0.03s ==============================
```

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_llm_redaction_chokepoint.py -v` | 0 | **10 passed** in 0.03s |
| `PYTHONPATH=src python3 -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **214 passed**, 13 deselected in 1.77s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |
| `grep -r 'Week\|week' src/project_sentinel/` | 0 | **0 match** (không chứa week token trong production code) |

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/llm/redacting.py:14-20` — Danh sách `_UNREDACTED_FIELDS` bao gồm `group_key`, `task`, `output_language`, `output_schema`, `allowed_endpoints`.
- **Giả định đã đặt:** Mọi trường trong `_UNREDACTED_FIELDS` đều là hằng số hoặc metadata cấu hình không chứa PII từ người dùng.
- **Việc còn nợ:** Task 3 của Plan 2 (nút thắt thứ 2: che trước khi ghi log trong `gateway/request_log.py`).
- **Câu hỏi cho người dùng:** Không có.
