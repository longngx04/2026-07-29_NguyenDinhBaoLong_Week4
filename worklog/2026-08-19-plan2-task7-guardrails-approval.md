# Worklog — Plan 2: Task 7 - Human-in-the-Loop Approval Gate

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 7 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-approval` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã tạo module `guardrails/approval.py` cung cấp cơ chế phê duyệt Human-in-the-Loop (HITL) cho các request tiềm ẩn rủi ro (phương thức POST hoặc có mang payload đặc biệt). Module định nghĩa các cấu trúc `ApprovalRequest` và `ApprovalDecision`, hàm xác định yêu cầu duyệt `requires_approval()`, hàm dựng phiếu duyệt `build_request()` hiển thị payload thật, các hàm đọc/ghi quyết định `write_decision()` / `read_decision()`, và giao diện dòng lệnh `prompt_cli()` với nguyên tắc từ chối theo mặc định (deny-by-default). Kết quả: 15/15 unit test mới pass 100%, toàn bộ suite 284 test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp cổng phê duyệt trung gian giữa phân tích/đề xuất và thi hành gửi probe request.
- **Nằm ở đâu trong luồng:** Nằm tại package `guardrails/`, là chốt chặn can thiệp của con người trước khi `probe/tool.py` thực hiện bất kỳ request POST hoặc probe nào có payload.
- **Không có nó thì hỏng gì:** Các request có khả năng làm biến đổi trạng thái ứng dụng đích (POST) hoặc các payload thăm dò dị thường sẽ tự động gửi mà không có sự đồng ý của chuyên viên bảo mật, vi phạm yêu cầu Human-in-the-Loop của sprint.
- **Ngoài phạm vi (cố ý không làm):** Chưa nối trực tiếp vào `send_probe` (thuộc Task 8).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/approval.py` | Tạo mới | Định nghĩa `ApprovalRequest`, `ApprovalDecision`, `requires_approval`, `build_request`, `write_decision`, `read_decision`, `prompt_cli` | Triển khai logic phê duyệt an toàn |
| `src/project_sentinel/guardrails/__init__.py` | Sửa | Export các biểu tượng công khai của module approval | Mở rộng API package guardrails |
| `tests/unit/guardrails/test_approval.py` | Tạo mới | 15 unit test bao phủ toàn bộ các trường hợp kiểm thử phê duyệt | Đảm bảo tính đúng đắn |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–5 của Task 7 (`- [x]`) | Cập nhật tiến độ |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md | 10 +--
 src/project_sentinel/guardrails/__init__.py                       | 16 ++++
 src/project_sentinel/guardrails/approval.py                       | 87 +++++++++++++++++++++
 tests/unit/guardrails/test_approval.py                           | 80 +++++++++++++++++++
 4 files changed, 188 insertions(+), 5 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **Tiêu chí bắt buộc phê duyệt (`requires_approval`):**
   - Mọi request có `method.upper() == "POST"` đều cần duyệt (nguy cơ thay đổi trạng thái).
   - Mọi probe có `payload_kind is not None` đều cần duyệt (`long_string`, `special_chars`, `empty_value`, `wrong_type`).
   - Request GET thuần túy không có payload không cần duyệt.
2. **Minh bạch thông tin hiển thị:** `build_request()` lấy giá trị payload thật từ `payload_value_for()` để hiển thị nguyên văn cho người vận hành, không giấu diếm.
3. **Deny-by-default trên CLI:** Chỉ duy nhất chuỗi `"approve"` (không phân biệt hoa thường) mới được chấp nhận; mọi phím khác, chuỗi rỗng hay gõ sai chính tả đều trả về `approved=False`.

---

## 5. Output là gì

**Thành phần mới:**
- `ApprovalRequest`: Dataclass thông tin request cần duyệt.
- `ApprovalDecision`: Dataclass quyết định của con người (`approved: bool`, `decided_at: str`, `decided_by: str`).
- `requires_approval`, `build_request`, `write_decision`, `read_decision`, `prompt_cli`.

**Cách chạy:**
```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_approval.py -v
```

---

## 6. Vì sao chọn cách implement này

- **Deny-by-default:** Đảm bảo an toàn tối đa khi người dùng ấn nhầm hoặc không chắc chắn.
- **Tách biệt file `decision.json`:** Cho phép cả CLI và Web interface (Plan 3) tương tác qua cùng một cơ chế ghi đĩa chuẩn tắc.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src pytest tests/unit/guardrails/test_approval.py -v` | 0 | **15 passed** in 0.02s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests` | 0 | **284 passed**, 13 deselected in 1.83s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |

---

## 8. Cần người review kỹ ở đâu

- Logic `requires_approval`: Đã bao quát POST và mọi payload đặc biệt.
- Kế hoạch tiếp theo: Task 8 (tích hợp cổng vào `send_probe` và CLI).
