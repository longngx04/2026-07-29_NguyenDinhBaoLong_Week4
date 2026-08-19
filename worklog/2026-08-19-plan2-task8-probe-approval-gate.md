# Worklog — Plan 2: Task 8 - Send Probe Approval Gate

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 8 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-tool-gate` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã tích hợp cổng phê duyệt Human-in-the-Loop trực tiếp vào hàm `send_probe()` trong `probe/tool.py` và cập nhật CLI `probe` command. Bất biến an ninh cốt lõi: cổng duyệt nằm **trong chính công cụ** chứ không phụ thuộc vào giao diện; mọi request POST hoặc có payload đặc biệt thiếu quyết định `approved=True` đều bị chặn lập tức trước transport và ghi nhận `ApprovalRequired` vào audit log. Kết quả: 6/6 unit test mới pass 100%, toàn bộ suite 290 non-LLM test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đảm bảo tính bất biến rằng không một request probe rủi ro nào có thể rời khỏi hệ thống nếu chưa có sự phê duyệt rõ ràng từ con người.
- **Nằm ở đâu trong luồng:** Tại `src/project_sentinel/probe/tool.py` (`send_probe`), nằm ngay sau bước kiểm tra allowlist và payload validity, trước bước gửi HTTP transport qua Gateway.
- **Không có nó thì hỏng gì:** Các module gọi `send_probe` hoặc các giao diện tương lai nếu quên hiển thị UI duyệt có thể gửi nhầm request gây biến đổi dữ liệu sang WebGoat.
- **Ngoài phạm vi (cố ý không làm):** Bộ tích hợp 6 ca kiểm thử nghiệm thu tổng hợp (thuộc Task 9).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/probe/tool.py` | Sửa | Thêm tham số `approval: ApprovalDecision | None = None` vào `send_probe()`, kiểm tra `requires_approval()` và từ chối gửi nếu thiếu quyết định hợp lệ | Thiết lập chốt chặn an toàn trong công cụ |
| `src/project_sentinel/cli.py` | Sửa | Nhánh subcommand `probe` gọi `requires_approval()`, hiển thị `prompt_cli()` hỏi người dùng trước khi gọi `send_probe()` | Tích hợp cổng duyệt vào CLI |
| `tests/unit/probe/test_tool_approval_gate.py` | Tạo mới | 6 unit test: POST thiếu decision bị chặn, rejected decision không gửi, log không có dòng SENT, GET không payload không cần duyệt, approved decision gửi đúng 1 lần, allowlist chặn trước duyệt | Đảm bảo tính bất biến theo TDD |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–7 của Task 8 (`- [x]`) | Cập nhật tiến độ |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md | 14 +--
 src/project_sentinel/cli.py                                       | 16 +++-
 src/project_sentinel/probe/tool.py                                | 26 +++++-
 tests/unit/probe/test_tool_approval_gate.py                       | 87 +++++++++++++++++++
 4 files changed, 126 insertions(+), 17 deletions(-)
```

---

## 4. Làm như thế nào

**Thứ tự thẩm tra an ninh trong `send_probe()`:**
1. **Allowlist check:** Chặn ngay nếu endpoint không nằm trong danh mục allowlist (không hỏi người dùng vô ích cho endpoint cấm).
2. **Payload Kind validity check:** Chặn nếu payload kind không thuộc tập hợp quy định.
3. **Approval Gate:** Kiểm tra `requires_approval(probe)`. Nếu yêu cầu duyệt mà `approval is None` hoặc `not approval.approved`, từ chối gửi với `denied_reason`, ghi log với `error_class="ApprovalRequired"`, và trả về `ProbeOutcome(sent=False)`.
4. **Rate Limiting & Transport:** Chỉ khi vượt qua các bước trên, request mới được gửi tới Gateway.

---

## 5. Output là gì

- `send_probe(..., approval=...)`: Hỗ trợ tham số quyết định phê duyệt.
- CLI `probe` command: Tự động tương tác với người vận hành qua terminal.

---

## 6. Vì sao chọn cách implement này

- **Defense in Depth:** Đặt cổng duyệt ngay trong `send_probe()` đảm bảo không caller nào có thể vô tình bypass việc kiểm tra phê duyệt.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src pytest tests/unit/probe/test_tool_approval_gate.py -v` | 0 | **6 passed** in 0.03s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests` | 0 | **290 passed**, 13 deselected in 2.08s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |

---

## 8. Cần người review kỹ ở đâu

- Thứ tự kiểm tra: Allowlist ➔ Payload validity ➔ Approval ➔ Transport.
- Việc tiếp theo: Task 9 (Sáu ca kiểm thử tổng hợp Plan 2 & Makefile target).
