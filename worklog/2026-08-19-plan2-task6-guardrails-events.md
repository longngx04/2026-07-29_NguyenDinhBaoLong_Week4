# Worklog — Plan 2: Task 6 - Guardrails Events Log

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 6 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-events` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã tạo module `guardrails/events.py` quản lý sổ nhật ký sự kiện bảo vệ (guardrail event log) dạng JSONL. Module định nghĩa 4 loại sự kiện được phê duyệt (`redaction`, `injection`, `approval`, `allowlist_block`), tự động che dữ liệu nhạy cảm trong trường `detail` trước khi ghi đĩa qua `redact_structure()`, giữ nguyên trường provenance `run_id`, cung cấp hàm đọc `read_events()` an toàn và hàm thống kê `count_by_kind()`. Kết quả: 8/8 unit test mới pass 100%, toàn bộ test suite 262 non-llm test xanh hoàn toàn.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp hạ tầng ghi nhận sự kiện guardrails dạng JSON Lines (`append_event`), đọc lại nhật ký (`read_events`), và thống kê phân loại sự kiện (`count_by_kind`).
- **Nằm ở đâu trong luồng:** Nằm tại package `guardrails/`, là kho lưu trữ trung tâm để ghi lại mọi sự kiện guardrail phát sinh trong quá trình phân tích và dò quét (Plan 2), đồng thời là nguồn dữ liệu nuôi màn hình Security events và bảng số liệu approve/reject trong báo cáo cuối (Plan 3).
- **Không có nó thì hỏng gì:** Không có nguồn chứng cứ ghi nhận các đòn tấn công injection đã bị phát hiện, các thông tin nhạy cảm đã bị che, các quyết định phê duyệt human-in-the-loop, và các request bị allowlist chặn; không thể tính toán số liệu cho dashboard bảo mật và báo cáo tổng kết.
- **Ngoài phạm vi (cố ý không làm):** Chưa nối `append_event()` vào `approval.py` (Task 7) hay `tool.py` (Task 8).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/events.py` | Tạo mới | Định nghĩa tập hợp `EVENT_KINDS`, hàm `append_event()` (che sensitive data qua `redact_structure`, ghi JSONL atomic append), hàm `read_events()` (đọc an toàn, xử lý file vắng mặt), hàm `count_by_kind()` (thống kê theo kind). | Cung cấp module ghi/đọc sổ sự kiện guardrail theo thiết kế |
| `src/project_sentinel/guardrails/__init__.py` | Sửa | Export các biểu tượng công khai `EVENT_KINDS`, `append_event`, `read_events`, `count_by_kind`. | Xuất API công khai của package guardrails |
| `tests/unit/guardrails/test_events.py` | Tạo mới | 8 unit test kiểm thử: định nghĩa 4 event kind, ghi 1 dòng, ghi nhiều dòng, từ chối kind lạ, che dữ liệu nhạy cảm trong detail, bảo toàn provenance `run_id`, đọc file chưa tồn tại trả mảng rỗng, đếm số lượng theo kind chính xác. | Đảm bảo tính đúng đắn và an toàn của module events theo TDD |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–5 của Task 6 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md | 10 +++---
 src/project_sentinel/guardrails/__init__.py                       | 11 +++++++
 src/project_sentinel/guardrails/events.py                         | 48 ++++++++++++++++++++++++++++
 tests/unit/guardrails/test_events.py                             | 48 ++++++++++++++++++++++++++++
 4 files changed, 112 insertions(+), 5 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **Quy chuẩn danh mục sự kiện:** Định nghĩa tập hợp bất biến `EVENT_KINDS = frozenset({"redaction", "injection", "approval", "allowlist_block"})`. Mọi lời gọi `append_event` với kind nằm ngoài danh mục này đều bị từ chối bằng `ValueError`.
2. **Nút thắt che dữ liệu trước khi chạm đĩa:** Sử dụng `redact_structure()` đã được kiểm chứng ở Task 1 để đệ quy che mọi dữ liệu nhạy cảm (email, phone, API key, JWT token, password, PII...) trong từ điển `detail` trước khi tuần tự hóa JSON và ghi file.
3. **Bảo toàn provenance:** `run_id` là mã định danh chứng cứ, được lưu độc lập ở cấp gốc của bản ghi record (`ts`, `run_id`, `kind`, `detail`), không bị che hoặc làm sai lệch.
4. **An toàn I/O:** Tự động tạo thư mục cha nếu chưa tồn tại (`path.parent.mkdir(parents=True, exist_ok=True)`), mở file ở chế độ append `"a"` với encoding `utf-8`, xử lý đọc file chưa tồn tại trả về `[]` thay vì văng exception.

**Luồng dữ liệu:**
`Event details` → `redact_structure()` → `safe_detail` → `JSON Line Record` → `events.jsonl` đĩa → `read_events()` / `count_by_kind()` → `Dashboard / Report`

**Xử lý lỗi / trường hợp biên:**
- Kind không hợp lệ: Ném `ValueError`.
- Detail là `None` hoặc rỗng: Khởi tạo dict rỗng an toàn.
- File log không tồn tại: `read_events` trả về danh sách rỗng `[]`.
- Dòng trống trong file log: Bỏ qua khi parse JSON.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hằng số | `EVENT_KINDS` | `frozenset[str]` | 4 loại sự kiện được phê duyệt |
| Hàm | `append_event` | `(log_path, *, run_id: str, kind: str, detail: dict) -> None` | Ghi thêm 1 bản ghi sự kiện sau khi đã che dữ liệu |
| Hàm | `read_events` | `(log_path) -> list[dict[str, Any]]` | Đọc toàn bộ sự kiện từ file JSONL |
| Hàm | `count_by_kind` | `(events: list[dict[str, Any]]) -> dict[str, int]` | Thống kê số lượng sự kiện theo từng loại |
| Test file | `test_events.py` | `tests/unit/guardrails/test_events.py` | 8 unit tests bao phủ 100% chức năng của events module |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/guardrails/test_events.py -v
```

**Output thật (đã che secret):**

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/longngx04/VinSOC/project_sentinel_main/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
plugins: respx-0.23.1, xdist-3.8.0, anyio-4.14.2
collecting ... collected 8 items

tests/unit/guardrails/test_events.py::test_four_event_kinds_are_defined PASSED [ 12%]
tests/unit/guardrails/test_events.py::test_append_writes_one_json_line PASSED [ 25%]
tests/unit/guardrails/test_events.py::test_appending_twice_keeps_both_lines PASSED [ 37%]
tests/unit/guardrails/test_events.py::test_unknown_kind_is_rejected PASSED [ 50%]
tests/unit/guardrails/test_events.py::test_detail_is_redacted_before_writing PASSED [ 62%]
tests/unit/guardrails/test_events.py::test_run_id_survives_redaction PASSED [ 75%]
tests/unit/guardrails/test_events.py::test_read_events_on_missing_file_returns_empty PASSED [ 87%]
tests/unit/guardrails/test_events.py::test_count_by_kind_totals_correctly PASSED [100%]

============================== 8 passed in 0.06s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Định dạng JSON Lines lưu trữ append-only cục bộ, bọc qua `redact_structure` trước khi ghi, và danh mục `EVENT_KINDS` tĩnh cố định.

**Lý do:**
- JSONL cho phép append tức thì O(1) mà không cần load toàn bộ file vào bộ nhớ như mảng JSON tiêu chuẩn.
- Bắt buộc kiểm tra `kind` trước khi ghi ngăn chặn việc ô nhiễm sổ nhật ký bởi các sự kiện không xác định.
- Chạy `redact_structure` ngay trước khi ghi đĩa đảm bảo bất biến an ninh: không có bất kỳ secret/PII nào có thể lọt vào file audit nhật ký.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/guardrails/test_events.py -v` | 0 | **8 passed** in 0.06s |
| `.venv/bin/python -m pytest tests/unit/guardrails/ -v` | 0 | **77 passed** in 0.27s |
| `.venv/bin/python -m pytest -m "not llm" -q tests` | 0 | **262 passed**, 4 deselected in 7.43s |
| `.venv/bin/python -m compileall -q src/project_sentinel` | 0 | Thành công, không có lỗi cú pháp |

**Test mới thêm:**
- `test_four_event_kinds_are_defined`: Kiểm tra 4 loại sự kiện được phê duyệt sẵn.
- `test_append_writes_one_json_line`: Kiểm tra ghi đúng format 1 dòng JSONL với timestamp `ts`.
- `test_appending_twice_keeps_both_lines`: Kiểm tra tính chất append-only không ghi đè dữ liệu cũ.
- `test_unknown_kind_is_rejected`: Kiểm tra chặn loại sự kiện ngoài danh mục.
- `test_detail_is_redacted_before_writing`: Kiểm tra dữ liệu nhạy cảm trong detail được che tự động.
- `test_run_id_survives_redaction`: Kiểm tra provenance `run_id` được giữ nguyên vẹn.
- `test_read_events_on_missing_file_returns_empty`: Kiểm tra đọc an toàn khi file chưa tồn tại.
- `test_count_by_kind_totals_correctly`: Kiểm tra hàm thống kê tổng hợp chính xác theo loại.

**Bất biến đã giữ:**
- Không mock/stub; kiểm thử trên filesystem thật bằng `tmp_path`.
- Không có test skip.
- Không để lộ secret ra log.
- Không vi phạm cấu trúc repository.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/guardrails/events.py:12` — 4 giá trị trong `EVENT_KINDS`. Hiện đã bao gồm đủ cho các use cases của Plan 2 và Plan 3.
- **Giả định đã đặt:** `log_path` luôn là đường dẫn hợp lệ hoặc có thể tạo thư mục cha trên hệ thống.
- **Việc còn nợ:** Task 7 (`approval.py`) và Task 8 (`send_probe` human-in-the-loop gate).
- **Câu hỏi cho người dùng:** Không có.
