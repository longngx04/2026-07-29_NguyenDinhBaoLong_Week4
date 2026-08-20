# Worklog — Plan 3 Task 2: Nhật ký toàn trình đi qua bộ che (run_log.py)

**Ngày:** 2026-08-20 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/orchestrator-run-log` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 2`

---

## 1. Tóm tắt

Đã xây dựng và củng cố toàn diện module nhật ký toàn trình `src/project_sentinel/orchestrator/run_log.py`. Module cung cấp hai hàm `append_log` và `read_log`, tự động khử PII và bí mật qua chokepoint `redact_structure` trước khi ghi vào `run.log.jsonl`. Đồng thời, đã hoàn thiện các điểm phòng vệ: kiểm tra kiểu `message` là chuỗi, chặn người gọi giả mạo timestamp (`ts`), giới hạn kích thước message sau khi che (`MAX_MESSAGE_BYTES = 2048`), và xử lý chống sập khi gặp dòng log hỏng trong `read_log`. Toàn bộ 13 test unit đều pass 100% không dùng mock/stub.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Ghi lại nhật ký có cấu trúc theo thời gian thực cho từng bước của lần chạy dưới `artifacts/runs/<run_id>/run.log.jsonl`, đáp ứng yêu cầu Bước 9 của đề bài: *"Toàn bộ quá trình được ghi log."*
- **Nằm ở đâu trong luồng:** Chạy xuyên suốt 9 bước (quét, chuẩn hoá, phân tích, đề xuất, phê duyệt, gửi request, lọc response, dựng báo cáo, tổng kết).
- **Không có nó thì hỏng gì:** Không có bằng chứng kiểm toán (audit trail) toàn trình; người vận hành và giao diện Web không thể theo dõi diễn biến chi tiết hoặc chẩn đoán nguyên nhân khi một bước gặp lỗi.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp vào các hàm bước `step_*` (sẽ thực hiện tại Task 3–6); chưa cắt các trường trong `extra` (chỉ cắt `message`).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/run_log.py` | Tạo / Sửa | Triển khai `LOG_LEVELS`, `LOG_FILENAME`, `MAX_MESSAGE_BYTES`, `RESERVED_FIELDS`, `append_log` (chặn đè trường hệ thống, validate kiểu `message` là chuỗi, tích hợp `redact_structure`, cắt message sau khi che), và `read_log` (bỏ qua dòng hỏng) | Triển khai module nhật ký toàn trình an toàn và bền bỉ |
| `tests/unit/orchestrator/test_run_log.py` | Tạo / Sửa | 13 test cases kiểm tra: trường bắt buộc, trường phụ, thứ tự, log level, che nhạy cảm, che email, đọc log rỗng, lọc lỗi, che extra lồng nhau, chặn giả mạo timestamp, giới hạn message sau che, chịu lỗi dòng hỏng, và từ chối `message` không phải chuỗi | Kiểm chứng toàn diện chức năng và các điểm củng cố phòng vệ |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Cập nhật tiến độ Task 2 | Đồng bộ kế hoạch |

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. `append_log` nhận thông tin bước (`step`), mức log (`level`), thông điệp (`message`) và các trường bổ sung (`**extra`).
2. Kiểm tra `level` hợp lệ, sau đó chặn ngay các trường hệ thống (`ts`, `step`, `level`, `message`) nếu người gọi truyền trong `extra` để chống giả mạo timestamp.
3. Kiểm tra kiểu `message` phải là `str`, ném `ValueError` nếu truyền sai kiểu để tránh sập không kiểm soát.
4. Chuyển payload qua `redact_structure()`.
5. Cắt ngắn `message` nếu vượt quá `MAX_MESSAGE_BYTES = 2048` (cắt theo byte UTF-8 và thực hiện **sau khi che** để tính đúng độ giãn nở chuỗi do redact).
6. Gán timestamp UTC ISO 8601 (`ts`) do hệ thống sinh và ghi nối tiếp vào `run.log.jsonl`.
7. `read_log` đọc từng dòng, bỏ qua các dòng không phải JSON hợp lệ để đảm bảo một dòng hỏng/đang ghi dở không làm sập toàn bộ lần đọc.

**Luồng dữ liệu:** `append_log(root, step, level, message, **extra)` → `check RESERVED_FIELDS & message type` → `redact_structure({...})` → `bound message (MAX_MESSAGE_BYTES)` → `{"ts": now, ...}` → `json.dumps()` → `run.log.jsonl` → `read_log(root)`

**Các quyết định kỹ thuật:**
- Chặn `RESERVED_FIELDS = frozenset({"ts", "step", "level", "message"})` trước khi redact để bảo vệ tính toàn vẹn của audit trail.
- Validate `isinstance(message, str)` để ném lỗi tường minh thay vì lỗi `AttributeError` khi encode.
- Giới hạn `MAX_MESSAGE_BYTES = 2048` theo byte sau khi redact (tránh trường hợp chuỗi phình to sau khi thay thế token nhạy cảm).
- `read_log` sử dụng `try/except ValueError` cho từng dòng để chống sập khi đọc đồng thời với tiến trình ghi.

**Xử lý lỗi / trường hợp biên:**
- Người gọi cố tình truyền `ts`: ném `ValueError("Không được ghi đè trường hệ thống: ['ts']")`.
- Người gọi truyền `message` không phải chuỗi: ném `ValueError("message phải là chuỗi, nhận được <type>")`.
- Thông điệp cực dài (> 2048 bytes sau che): tự động cắt theo byte và thêm hậu tố `…[cat]`.
- File chứa dòng rác/hỏng: `read_log` tự động bỏ qua dòng lỗi và trả về các dòng hợp lệ còn lại.
- File `run.log.jsonl` chưa tồn tại: trả về `[]`.
- Mức log không hợp lệ: ném `ValueError`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hằng số | `LOG_LEVELS` | `frozenset({"info", "warn", "error"})` | Các mức log được phép |
| Hằng số | `LOG_FILENAME` | `"run.log.jsonl"` | Tên file log của mỗi run |
| Hằng số | `MAX_MESSAGE_BYTES` | `2048` | Giới hạn dung lượng byte tối đa cho trường message |
| Hằng số | `RESERVED_FIELDS` | `frozenset({"ts", "step", "level", "message"})` | Các trường hệ thống cấm người gọi ghi đè |
| Hàm | `append_log` | `append_log(root: str \| Path, *, step: str, level: str, message: str, **extra: Any) -> None` | Ghi thêm một dòng nhật ký đã che nhạy cảm và giới hạn kích thước |
| Hàm | `read_log` | `read_log(root: str \| Path) -> list[dict[str, Any]]` | Đọc toàn bộ nhật ký của một run, bỏ qua dòng hỏng |
| Test | `test_run_log.py` | `tests/unit/orchestrator/test_run_log.py` | 13 test unit kiểm tra run_log |

**Cách chạy:**

```bash
.venv/bin/pytest tests/unit/orchestrator/test_run_log.py -v
```

**Output thật (đã che secret):**

```text
tests/unit/orchestrator/test_run_log.py::test_append_writes_one_line_with_required_fields PASSED [  7%]
tests/unit/orchestrator/test_run_log.py::test_extra_fields_are_kept PASSED [ 15%]
tests/unit/orchestrator/test_run_log.py::test_entries_accumulate_in_order PASSED [ 23%]
tests/unit/orchestrator/test_unknown_level_is_rejected PASSED [ 30%]
tests/unit/orchestrator/test_run_log.py::test_sensitive_data_is_redacted_before_writing PASSED [ 38%]
tests/unit/orchestrator/test_run_log.py::test_email_in_message_is_redacted PASSED [ 46%]
tests/unit/orchestrator/test_run_log.py::test_read_log_on_missing_file_returns_empty PASSED [ 53%]
tests/unit/orchestrator/test_run_log.py::test_error_entries_are_findable PASSED [ 61%]
tests/unit/orchestrator/test_run_log.py::test_sensitive_data_in_extra_fields_is_redacted PASSED [ 69%]
tests/unit/orchestrator/test_run_log.py::test_caller_cannot_forge_the_timestamp PASSED [ 76%]
tests/unit/orchestrator/test_run_log.py::test_message_is_bounded_after_redaction PASSED [ 84%]
tests/unit/orchestrator/test_run_log.py::test_one_corrupt_line_does_not_break_the_whole_read PASSED [ 92%]
tests/unit/orchestrator/test_run_log.py::test_non_string_message_is_rejected_clearly PASSED [100%]

============================== 13 passed in 0.05s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Tích hợp trực tiếp `redact_structure` vào `append_log`, kiểm tra `RESERVED_FIELDS` và kiểu `message` trước khi redact, giới hạn `MAX_MESSAGE_BYTES` sau khi redact, và dùng `try/except ValueError` từng dòng trong `read_log`.

**Lý do:** Đảm bảo tính toàn vẹn của audit trail, chống tràn bộ nhớ/phình log không kiểm soát, và tăng tính chịu lỗi của hệ thống khi đọc/ghi đồng thời.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Cắt ngắn `message` trước khi redact | Tránh redact chuỗi dài | Sai luồng: Redaction làm chuỗi dài ra (e.g. `a@b.com` 7 bytes -> `[REDACTED_EMAIL]` 16 bytes), chuỗi sau redact vẫn có thể vượt giới hạn. |
| Để `json.loads` trong `read_log` ném lỗi khi gặp dòng hỏng | Báo lỗi ngay lập tức | Làm tê liệt toàn bộ giao diện Web khi chỉ có 1 dòng ghi dở hoặc hỏng cục bộ. |
| Cho phép người gọi truyền `ts` tuỳ ý | Linh hoạt khi import log cũ | Phá vỡ tính xác thực thời gian thực của nhật ký toàn trình (người gọi có thể giả mạo thời điểm thực thi). |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/pytest tests/unit/orchestrator/test_run_log.py -v` | 0 | 13 passed in 0.05s |
| `.venv/bin/pytest tests/unit/orchestrator -v` | 0 | 30 passed in 1.12s |
| `.venv/bin/pytest -m "not llm and not live_gateway" -q` | 0 | 339 passed, 15 deselected in 3.26s |
| `python3 -m compileall -q src/project_sentinel` | 0 | Biên dịch không có lỗi cú pháp |

**Test mới thêm:**
- `test_append_writes_one_line_with_required_fields`: Ghi đủ các trường bắt buộc (`ts`, `step`, `level`, `message`)
- `test_extra_fields_are_kept`: Giữ nguyên các trường bổ sung
- `test_entries_accumulate_in_order`: Các dòng log tích luỹ đúng thứ tự
- `test_unknown_level_is_rejected`: Từ chối log level không hợp lệ
- `test_sensitive_data_is_redacted_before_writing`: Khử khóa API/hex secret trong log
- `test_email_in_message_is_redacted`: Khử email trong message
- `test_read_log_on_missing_file_returns_empty`: Đọc log khi file chưa tồn tại trả về `[]`
- `test_error_entries_are_findable`: Lọc được các dòng log lỗi
- `test_sensitive_data_in_extra_fields_is_redacted`: Khử bí mật trong cả các trường `extra` lồng nhau
- `test_caller_cannot_forge_the_timestamp`: Khẳng định `ts` không thể bị người gọi giả mạo qua `extra`
- `test_message_is_bounded_after_redaction`: Khẳng định message luôn bị chặn ở `MAX_MESSAGE_BYTES` sau khi redact
- `test_one_corrupt_line_does_not_break_the_whole_read`: Khẳng định dòng log hỏng không làm chết cả lần đọc
- `test_non_string_message_is_rejected_clearly`: Khẳng định `message` không phải chuỗi bị từ chối rõ ràng bằng `ValueError`

**Bất biến đã giữ:** Không mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Bộ che `redact_structure` khép kín nhưng 3 rủi ro ngoài bộ che (giả mạo `ts` qua `**extra`, thông điệp quá dài sau khi che, và dòng log bị lỗi/đang ghi dở làm hỏng toàn bộ `read_log`) đã được phát hiện và xử lý triệt để tại tầng `run_log.py` với 3 test kiểm chứng tương ứng.
- **Giả định đã đặt:** `append_log` được gọi tuần tự trong ngữ cảnh một run, các tiến trình mở file với mode `"a"` UTF-8.
- **Việc còn nợ:** Task 3 (`orchestrator/context.py` & Bước 1–2).
- **Câu hỏi cho người dùng:** Không có.

