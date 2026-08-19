# Worklog — Plan 2: Task 6-9 Fixes (Approval Binding, Event Logging, Non-interactive CLI)

**Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-approval-binding` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md) · **Task ID:** `Task 6-9 Fixes`

---

## 1. Tóm tắt

Đã sửa 4 điểm tồn đọng cốt lõi cho các task 6–9 của Plan 2: (1) Ràng buộc phiếu phê duyệt với đúng request qua `request_fingerprint` (SHA-256 của `METHOD|path|payload`), ngăn chặn hoàn toàn việc dùng phiếu duyệt của probe này để gửi probe khác; (2) Nối `append_event` vào 4 điểm quyết định thực tế trong code production (`allowlist_block`, `approval` từ chối/đồng ý trong `probe/tool.py`, và `redaction` trong `llm/redacting.py`); (3) Sửa docstring `approval.py` phản ánh đúng cơ chế in-memory hiện tại; (4) Khắc phục lỗi `EOFError`/`KeyboardInterrupt` trong `prompt_cli()` khi chạy non-interactive stdin, đảm bảo fail-closed an toàn. Kết quả: 302 non-LLM test và 117 guardrails test đều pass 100%.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Bảo đảm tính bất biến an ninh của cổng phê duyệt Human-in-the-Loop và hệ thống sổ sự kiện bảo vệ (guardrail event log).
- **Nằm ở đâu trong luồng:** Nằm tại các chốt chặn `guardrails/approval.py`, `guardrails/events.py`, `probe/tool.py`, và `llm/redacting.py`.
- **Không có nó thì hỏng gì:**
  - Phiếu duyệt chỉ là biến boolean rời rạc, có thể bị bypass hoặc tráo đổi payload sau khi người dùng đã duyệt.
  - Sổ sự kiện `events.jsonl` không ghi nhận được các sự kiện thực tế trong quá trình vận hành, làm hỏng nguồn cấp dữ liệu cho màn hình Security Events và số liệu báo cáo của Plan 3.
  - Chạy CLI trong môi trường automation / pipeline không có TTY sẽ bị văng `EOFError` thay vì fail-closed sạch sẽ.
- **Ngoài phạm vi (cố ý không làm):** Nối `decision.json` từ đĩa vào `send_probe()` (đây là việc của Plan 3 khi Web UI chạy ở tiến trình độc lập).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/approval.py` | Sửa | Thêm hàm `request_fingerprint()`, thêm trường `request_fingerprint` vào `ApprovalRequest` và `ApprovalDecision`, sửa docstring, bọc `input_fn` trong `try / except (EOFError, KeyboardInterrupt)` | Khắc phục Điểm 1, 3, 4 |
| `src/project_sentinel/guardrails/__init__.py` | Sửa | Export `request_fingerprint` | Xuất API công khai của module |
| `src/project_sentinel/probe/tool.py` | Sửa | Thêm kiểm tra `approval.request_fingerprint == expected`, thêm tham số `events_path: str | None = "artifacts/guardrails/events.jsonl"`, gọi `append_event` ở các nhánh allowlist và approval | Khắc phục Điểm 1, 2 |
| `src/project_sentinel/llm/redacting.py` | Sửa | Thêm tham số `events_path` vào constructor, gọi `append_event` với `kind="redaction"` khi `last_redaction_events` không rỗng | Khắc phục Điểm 2 theo Phương án 1 được duyệt |
| `tests/unit/guardrails/test_approval.py` | Sửa | Thêm các test: tính xác định của fingerprint, chuyển fingerprint sang decision, xử lý an toàn EOFError / KeyboardInterrupt | Đảm bảo bao phủ test cho Điểm 1, 4 |
| `tests/unit/probe/test_tool_approval_gate.py` | Sửa | Thêm test chứng minh từ chối fingerprint không khớp, thêm test kiểm tra ghi nhận `events.jsonl` | Chứng minh bắt lỗi cho Điểm 1, 2 |
| `tests/unit/guardrails/test_llm_redaction_chokepoint.py` | Sửa | Thêm test kiểm tra `RedactingProvider` ghi nhận sự kiện `redaction` vào file events | Đảm bảo tính đúng đắn của RedactingProvider |
| `tests/integration/test_guardrails_acceptance.py` | Sửa | Cập nhật `ApprovalDecision` kèm `request_fingerprint` | Đồng bộ với interface mới |

**`git diff --stat`:**

```text
 src/project_sentinel/guardrails/__init__.py        |  2 +
 src/project_sentinel/guardrails/approval.py        | 36 ++++++++++---
 src/project_sentinel/llm/redacting.py              | 30 ++++++++++-
 src/project_sentinel/probe/tool.py                 | 48 +++++++++++++++--
 tests/integration/test_guardrails_acceptance.py    | 12 +++--
 tests/unit/guardrails/test_approval.py             | 40 ++++++++++++++
 .../guardrails/test_llm_redaction_chokepoint.py    | 18 +++++++
 tests/unit/probe/test_tool_approval_gate.py        | 62 +++++++++++++++++-----
 8 files changed, 219 insertions(+), 29 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **Ràng buộc Request Fingerprint:**
   - Hàm `request_fingerprint(probe: SafeProbe) -> str` tính toán SHA-256 hash chuẩn hóa từ `f"{probe.method.upper()}|{probe.path}|{payload}"` (payload được format JSON với `sort_keys=True`).
   - Phiếu duyệt `ApprovalRequest` và quyết định `ApprovalDecision` mang theo `request_fingerprint`.
   - Hàm `send_probe()` kiểm tra 3 điều kiện: `approval is not None`, `approval.approved is True`, và `approval.request_fingerprint == request_fingerprint(probe)`. Nếu không khớp, từ chối với lý do rõ ràng.
2. **Ghi nhận sự kiện thực tế (`append_event`):**
   - `probe/tool.py`:
     - Nhánh allowlist từ chối: ghi sự kiện `kind="allowlist_block"`
     - Nhánh approval từ chối: ghi sự kiện `kind="approval"` với `detail={"approved": False, ...}`
     - Nhánh approval đồng ý và gửi: ghi sự kiện `kind="approval"` với `detail={"approved": True, ...}`
   - `llm/redacting.py`:
     - Sau khi che, nếu có sự kiện trong `last_redaction_events`: ghi sự kiện `kind="redaction"` với `run_id` là `packet.group_key`.
3. **Chống crash non-interactive stdin:**
   - Bọc lệnh `input_fn()` trong khối `try ... except (EOFError, KeyboardInterrupt)`. Khi gặp lỗi luồng nhập, tự động gán `approved = False`, in thông báo `"→ KHÔNG ĐỌC ĐƯỢC CÂU TRẢ LỜI — coi như TỪ CHỐI"` và trả về decision từ chối an toàn.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `request_fingerprint` | `(probe: SafeProbe) -> str` | Tính toán SHA-256 fingerprint ràng buộc method, path và payload thật |
| Dataclass | `ApprovalRequest` | `src/project_sentinel/guardrails/approval.py` | Thêm trường `request_fingerprint: str` |
| Dataclass | `ApprovalDecision` | `src/project_sentinel/guardrails/approval.py` | Thêm trường `request_fingerprint: str` |
| Hàm | `send_probe` | `src/project_sentinel/probe/tool.py` | Thêm tham số `events_path` và kiểm tra fingerprint |
| Class | `RedactingProvider` | `src/project_sentinel/llm/redacting.py` | Thêm tham số `events_path` vào `__init__` |

**Cách chạy kiểm chứng:**

```bash
# 1. Chạy toàn bộ test guardrails và acceptance
PYTHONPATH=src make guardrails-test

# 2. Chạy toàn bộ test suite non-llm
PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests

# 3. Chạy kiểm chứng non-interactive CLI probe
PYTHONPATH=src SENTINEL_GATEWAY_API_KEY=x python3 -m project_sentinel.cli probe --method POST --path /WebGoat/attack --payload-kind long_string < /dev/null
```

**Output thật:**

```text
$ PYTHONPATH=src make guardrails-test
============================= 117 passed in 0.23s ==============================

$ PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests
302 passed, 13 deselected in 2.07s

$ PYTHONPATH=src SENTINEL_GATEWAY_API_KEY=x python3 -m project_sentinel.cli probe --method POST --path /WebGoat/attack --payload-kind long_string < /dev/null
═══ CẦN PHÊ DUYỆT TRƯỚC KHI GỬI REQUEST ═══
  Endpoint  : POST /WebGoat/attack
  Payload   : {"value": "AAAA..."}
  Mục đích  : Probe khởi động thủ công từ CLI
  Rủi ro    : Request POST có thể làm thay đổi trạng thái phía ứng dụng.

Gõ 'approve' để đồng ý, bất kỳ phím nào khác để từ chối: → KHÔNG ĐỌC ĐƯỢC CÂU TRẢ LỜI — coi như TỪ CHỐI
→ ĐÃ TỪ CHỐI — không request nào được gửi
DENIED: Người vận hành đã từ chối request này.
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:**
- SHA-256 fingerprint canonical (`method|path|payload_json_sorted_keys`) để ràng buộc tính toàn vẹn giữa phiếu duyệt và request.
- Thêm tham số tùy chọn `events_path` với giá trị mặc định `"artifacts/guardrails/events.jsonl"` vào `send_probe()` và `RedactingProvider.__init__()`.

**Lý do:**
- Fingerprint ngăn chặn triệt để lỗ hổng "duyệt một đằng, gửi một nẻo" mà không cần phải truyền toàn bộ object probe qua lại giữa các tầng.
- Giữ nguyên giao diện công khai của `LLMProvider` trên `RedactingProvider` (không làm thay đổi chữ ký `analyze` hay `generate`).

**Phương án đã cân nhắc và loại bỏ:**
- *Phương án dùng ID ngẫu nhiên không ràng buộc nội dung:* Bị loại vì không bảo đảm được việc payload bên trong bị sửa đổi sau khi duyệt.
- *Phương án đọc file `decision.json` trực tiếp bên trong `send_probe()`:* Bị loại vì `send_probe` là tầng nghiệp vụ thuần túy, việc quản lý file I/O của decision thuộc về tầng giao diện / orchestrator của Plan 3.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src make guardrails-test` | 0 | **117 passed** in 0.23s |
| `PYTHONPATH=src pytest tests/unit/guardrails tests/unit/probe -m "not live_gateway" -v` | 0 | **149 passed**, 3 deselected in 0.30s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests` | 0 | **302 passed**, 13 deselected in 2.07s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |

**Test mới thêm:**
- `tests/unit/guardrails/test_approval.py::test_request_fingerprint_is_deterministic_and_sensitive_to_fields`: Khẳng định fingerprint thay đổi khi đổi method, path hoặc payload.
- `tests/unit/guardrails/test_approval.py::test_cli_handles_eof_error_as_rejection`: Khẳng định CLI từ chối an toàn khi stdin bị đóng.
- `tests/unit/guardrails/test_approval.py::test_cli_handles_keyboard_interrupt_as_rejection`: Khẳng định CLI từ chối khi bị ngắt quãng.
- `tests/unit/probe/test_tool_approval_gate.py::test_decision_for_a_different_probe_is_rejected`: Khẳng định duyệt probe A nhưng gửi probe B sẽ bị chặn lập tức trước transport.
- `tests/unit/probe/test_tool_approval_gate.py::test_events_log_records_allowlist_block_and_approval`: Khẳng định ghi nhận đúng các loại sự kiện vào `events.jsonl`.
- `tests/unit/guardrails/test_llm_redaction_chokepoint.py::test_redacting_provider_appends_event_to_events_path`: Khẳng định `RedactingProvider` ghi sự kiện `redaction` vào `events.jsonl`.

**Bất biến đã giữ:**
- Không sử dụng test double (mock/stub/fake).
- Kiểm thử fail loud, không có test skip.
- Không để lộ API key hay dữ liệu nhạy cảm ra log.
- Cổng phê duyệt nằm chặt chẽ bên trong công cụ `send_probe()`.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/probe/tool.py:175` — Gọi `append_event` khi request được duyệt và gửi thành công (chỉ ghi nhận khi `requires_approval(probe)` là True).
- **Giả định đã đặt:** `request_fingerprint` sử dụng format `sort_keys=True` trong json.dumps của payload để đảm bảo tính tất định trên mọi môi trường.
- **Việc còn nợ:** Việc kết nối `decision.json` từ Web UI vào luồng phê duyệt của `send_probe()` là nhiệm vụ thuộc Plan 3 (khi Web UI chạy ở tiến trình riêng biệt).
- **Câu hỏi cho người dùng:** Không có.
