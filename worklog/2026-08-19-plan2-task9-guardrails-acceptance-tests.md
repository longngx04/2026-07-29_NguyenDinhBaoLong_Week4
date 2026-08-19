# Worklog — Plan 2: Task 9 - Guardrails Acceptance Tests & Makefile Target

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 9 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-acceptance` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã hoàn thành bộ 6 ca kiểm thử nghiệm thu tổng hợp bắt buộc (`tests/integration/test_guardrails_acceptance.py`) và thêm target `guardrails-test` vào `Makefile`. Bộ 6 ca kiểm thử bao phủ toàn diện các yêu cầu đề bài: (1) Prompt Injection ép lộ prompt; (2) Prompt Injection ép gọi endpoint cấm; (3) Ngăn chặn dữ liệu nhạy cảm lọt vào prompt LLM; (4) Ngăn chặn PII và API key lọt vào log; (5) Từ chối request khi người vận hành chọn Reject; (6) Cho phép request gửi đúng 1 lần khi người vận hành chọn Approve. Kết quả: 6/6 ca kiểm thử nghiệm thu pass 100%, lệnh `make guardrails-test` chạy 113 test xanh in 0.22s, toàn bộ suite 296 non-LLM test xanh hoàn toàn.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Kiểm chứng end-to-end toàn bộ 4 trụ cột Guardrails của Tuần 5: bộ lọc Prompt Injection, cơ chế che dữ liệu nhạy cảm, cổng phê duyệt Human-in-the-Loop, và chốt chặn allowlist/audit log.
- **Nằm ở đâu trong luồng:** Tại `tests/integration/test_guardrails_acceptance.py` và `Makefile`, là tiêu chí nghiệm thu tự động hóa của Sprint 5.
- **Không có nó thì hỏng gì:** Không có bằng chứng kiểm thử tổng hợp chứng minh cả hệ thống hoạt động đồng bộ và đáp ứng đúng 100% yêu cầu đề bài môn học.
- **Ngoài phạm vi (cố ý không làm):** Các ca kiểm thử gọi live OpenRouter tốn token (`make llm-test`).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/integration/test_guardrails_acceptance.py` | Tạo mới | Triển khai 6 ca kiểm thử nghiệm thu độc lập: 2 ca injection, 2 ca dữ liệu nhạy cảm, 2 ca phê duyệt | Bộ kiểm thử bắt buộc theo yêu cầu đề bài |
| `Makefile` | Sửa | Thêm target `guardrails-test` và khai báo vào `.PHONY` | Cung cấp target chạy tự động cho sprint 5 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–6 của Task 9 (`- [x]`) | Đánh dấu kết thúc toàn bộ Plan 2 |

**`git diff --stat`:**

```text
 Makefile                                                          |   6 +
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md |  12 +--
 tests/integration/test_guardrails_acceptance.py                   | 134 ++++++++++++++++++++++
 3 files changed, 146 insertions(+), 6 deletions(-)
```

---

## 4. Làm như thế nào

**6 Ca kiểm thử nghiệm thu:**
1. **Ca 1 (Prompt Injection - Ép lộ prompt):** Quét response `ignore-instructions.json`, xác nhận `verdict == "suspicious"`, đưa qua `wrap_untrusted()` và `RedactingProvider`, kiểm tra `reveal your system prompt` bị loại bỏ và có tag `[REMOVED_INJECTION_ATTEMPT]`.
2. **Ca 2 (Prompt Injection - Gọi endpoint cấm):** Quét response `exfiltrate-endpoint.json`, xác nhận bị phát hiện injection VÀ bị `validate_objective()` từ chối vì endpoint không nằm trong allowlist (phòng thủ 2 lớp).
3. **Ca 3 (Dữ liệu nhạy cảm - Không lọt vào LLM):** Đưa response chứa email, SĐT, thẻ tín dụng (`pii-leak.json`) qua `RedactingProvider`, kiểm tra toàn bộ secret biến mất và được thay bằng tag `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, `[REDACTED_CARD]`.
4. **Ca 4 (Dữ liệu nhạy cảm - Không lọt vào Log):** Gửi request với API key và email, kiểm tra file `requests.jsonl` không chứa API key và email.
5. **Ca 5 (Phê duyệt - Từ chối):** Gửi probe POST với `approved=False`, kiểm tra `outcome.sent == False`, `ExplodingTransport` không bị chạm tới, và log không có trạng thái `SENT`.
6. **Ca 6 (Phê duyệt - Đồng ý):** Gửi probe POST với `approved=True`, kiểm tra `outcome.sent == True` và transport được gọi chính xác 1 lần.

---

## 5. Output là gì

- `tests/integration/test_guardrails_acceptance.py`: 6 ca integration test.
- `make guardrails-test`: Target Makefile chạy toàn bộ 113 test guardrails.

---

## 6. Vì sao chọn cách implement này

- Dùng `ExplodingTransport` ở Ca 4 và 5 để khẳng định một điều KHÔNG xảy ra (không có bất kỳ network request nào được gửi khi bị từ chối).
- Dùng `Recorder` ở Ca 1 và 3 để chụp lại chính xác nội dung prompt mà LLM Provider thật nhận được.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `make guardrails-test` | 0 | **113 passed** in 0.22s |
| `PYTHONPATH=src pytest tests/integration/test_guardrails_acceptance.py -v` | 0 | **6 passed** in 0.03s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests` | 0 | **296 passed**, 13 deselected in 1.99s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |
| `grep -r 'Week\|week' src/project_sentinel/ configs/prompts/` | 0 | **0 match** (không chứa week token) |

---

## 8. Cần người review kỹ ở đâu

- Toàn bộ 9 task của Plan 2 đã hoàn thành 100%.
- Sẵn sàng chuyển sang **Plan 3: Orchestrator, Web App, Đánh giá & Demo**.
