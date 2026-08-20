# Worklog — Plan 3 Task 5: cổng phê duyệt và gửi probe

**Ngày:** 2026-08-20 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/orchestrator-approval-probe` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 5`

---

## 1. Tóm tắt

Task thêm bước 5 tạo phiếu duyệt bền trên đĩa và bước 6 gửi probe qua Gateway sau khi đọc quyết định từ đĩa. Luồng này phục vụ CLI/web ở các task sau bằng một nguồn sự thật chung, không giữ coroutine chờ trong bộ nhớ; chốt `send_probe` là nơi duy nhất ghi kết quả approval thực tế và `objective=null` dùng purpose an toàn. Kết quả là mười test Task 5 và toàn bộ 376 test không dùng LLM/live Gateway đều đạt.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Nối đề xuất probe với cổng phê duyệt thủ công và Safe Probe Tool, đồng thời ràng buộc quyết định với đúng request bằng fingerprint.
- **Nằm ở đâu trong luồng:** Sau `step_propose` (bước 4), trước scrub/report/finalize (bước 7–9).
- **Không có nó thì hỏng gì:** Orchestrator không thể dừng ở `AWAITING_APPROVAL`, Plan 4 không có phiếu duyệt để hiển thị, và quyết định của người dùng không thể điều khiển bước gửi request.
- **Ngoài phạm vi (cố ý không làm):** Không thêm runner/CLI/web; không sửa `send_probe`, fingerprint guard, Gateway, allowlist hoặc dependency.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/steps.py` | Sửa | Thêm ghi JSON qua redaction, nạp proposal, `step_approval` và `step_probe` | Đây là module sở hữu chín bước orchestrator theo plan |
| `tests/unit/orchestrator/test_steps_approval_probe.py` | Tạo | Thêm mười test cho pause/skip/reject/approve, event kết quả, đúng một request, fingerprint lệch và `objective=null` | Chứng minh cả happy path lẫn fail-closed path |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đồng bộ Task 5 với fingerprint contract, event do chốt ghi, fallback objective và mười test | Plan cũ không còn khớp code bảo mật hiện tại |
| `worklog/2026-08-20-plan3-task5-approval-probe.md` | Tạo | Ghi phạm vi, thiết kế và bằng chứng kiểm chứng thật | Báo cáo bắt buộc của repository |

**`git diff --cached --stat`:**

```text
 .../2026-08-17-rebuild-plan-3-w6-orchestrator.md   | 161 +++++++++---
 src/project_sentinel/orchestrator/steps.py         | 160 +++++++++++-
 .../unit/orchestrator/test_steps_approval_probe.py | 275 +++++++++++++++++++++
 worklog/2026-08-20-plan3-task5-approval-probe.md   | 168 +++++++++++++
 4 files changed, 732 insertions(+), 32 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** `step_approval` đọc `proposal.json`, bỏ qua proposal bị từ chối hoặc GET trơn, còn request rủi ro được chuyển thành `approval-request.json` chứa fingerprint và run chuyển sang `AWAITING_APPROVAL`. Một tiến trình khác ghi `decision.json`; `step_probe` đọc file này và chuyển nguyên `ApprovalDecision` cùng đường dẫn event của run vào `send_probe`. `send_probe` tự so fingerprint, quyết định request có thật sự được gửi hay bị chặn, rồi ghi đúng kết quả đó vào `events.jsonl`. `objective` không phải dict được coi như rỗng để phiếu duyệt vẫn có purpose mặc định. Mọi artifact mới do orchestrator ghi đều đi qua `redact_structure`; audit request tiếp tục đi qua logger bảo mật hiện hữu.

**Luồng dữ liệu:** `proposal.json` → `step_approval` → `approval-request.json` → người dùng/Plan 4 ghi `decision.json` → `step_probe` → `send_probe` → `gateway-requests.jsonl` + `probe-result.json`

**Các quyết định kỹ thuật:**

- Fingerprint dùng cho test approve phải được đọc từ `approval-request.json`, không tính lại trực tiếp từ probe.
- `decision.json` luôn được đọc bằng `read_decision`; không truyền một quyết định được dựng trong bộ nhớ vòng qua file.
- `step_probe` không tự ghi quyết định operator thành event; nó đưa `events_path` của run cho `send_probe`, để chốt ghi kết quả thực tế (`approved=False` khi fingerprint lệch, `approved=True` khi đã gửi).
- `objective=null` hoặc sai kiểu dùng purpose mặc định `Kiểm chứng finding`, thay vì để `AttributeError` thoát khỏi contract `StepFailure` của runner.
- Không sửa hoặc nới điều kiện `approval.request_fingerprint != expected` trong `probe/tool.py`.

**Xử lý lỗi / trường hợp biên:** Thiếu hoặc hỏng `proposal.json` tạo `StepFailure`; proposal không có probe được skip; thiếu, reject hoặc fingerprint lệch đều tạo kết quả `sent: false` trước transport; allowlist hỏng cũng trở thành `StepFailure` đọc được.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `step_approval` | `step_approval(record: RunRecord, ctx: RunContext) -> RunRecord` | Dựng phiếu duyệt hoặc skip request không rủi ro |
| Hàm | `step_probe` | `step_probe(record: RunRecord, ctx: RunContext, *, transport=None) -> RunRecord` | Đọc quyết định từ file và gọi Safe Probe Tool |
| Artifact | Phiếu duyệt | `<run>/approval-request.json` | Chứa method, endpoint, payload, purpose, risk và fingerprint |
| Artifact | Kết quả probe | `<run>/probe-result.json` | Chứa sent/status/preview/error/denial đã qua redaction |
| Audit | Request log | `<run>/gateway-requests.jsonl` | Ghi `DENIED` hoặc `ALLOWED` qua logger hiện hữu |
| Test | Task 5 suite | `tests/unit/orchestrator/test_steps_approval_probe.py` | Mười ca kiểm thử approval/probe |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py -v
```

**Output thật (đã che secret):**

```text
collected 8 items
tests/unit/orchestrator/test_steps_approval_probe.py::test_risky_probe_pauses_for_approval PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_plain_get_skips_approval PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_rejected_proposal_skips_straight_past_approval PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_probe_without_a_decision_sends_nothing PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_rejected_decision_marks_the_run_rejected PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_rejection_writes_an_approval_event PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_approved_decision_sends_exactly_one_request PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_decision_from_a_different_request_sends_nothing PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_fingerprint_mismatch_leaves_a_trace_in_the_event_log PASSED
tests/unit/orchestrator/test_steps_approval_probe.py::test_proposal_with_null_objective_does_not_crash PASSED
============================== 10 passed in 0.09s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Giữ nguyên fingerprint guard của `send_probe`; tạo phiếu duyệt ở bước 5, buộc bước 6 đọc lại fingerprint qua file, và để chính chốt ghi event theo kết quả thực tế.

**Lý do:** Plan Task 5 cũ hơn code Plan 2 và plan là phần sai: test cũ tạo `ApprovalDecision` với fingerprint rỗng, trong khi code đúng phải từ chối quyết định không khớp request. Vì Plan 4 chỉ đọc được file, test phải chứng minh `step_approval` thật sự xuất fingerprint vào `approval-request.json`. Do đó đã sửa plan thay vì nới lỏng guardrail.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Cho fingerprint rỗng là hợp lệ | Làm test plan cũ xanh nhanh | Cho phép duyệt một request rồi gửi request khác; phá guardrail Plan 2 |
| Tính lại fingerprint trực tiếp từ probe trong test | Test ngắn | Không chứng minh file mà Plan 4 đọc có fingerprint |
| Truyền approval trực tiếp vào `send_probe` | Ít I/O | Bỏ qua `decision.json`, phá nguồn sự thật chung giữa CLI và web |
| `step_probe` tự ghi `approved=True` trước khi gọi chốt | Dễ thấy quyết định operator | Ghi quyết định thay vì kết quả; fingerprint mismatch bị che và màn hình Security events hiểu sai |
| Dùng request thật trong từng unit test Task 5 | Chứng minh network end-to-end | Không cô lập được orchestration call count; live Gateway đã có suite riêng và full suite vẫn được chạy |

**Đánh đổi đã chấp nhận:** Test Task 5 dùng transport seam hiện hữu để đếm chính xác zero/one call; bảo chứng Gateway thật thuộc test live riêng, không bị thay thế trong production.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `python -m pytest tests/unit/orchestrator -v` trước khi activate venv | 127 | `/bin/bash: python: command not found` |
| `python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py -v` | 1 | TDD đỏ đúng dự kiến: ImportError vì hai hàm chưa tồn tại |
| `python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py -k "fingerprint_mismatch_leaves_a_trace or proposal_with_null_objective" -v` | 1 | 2 failed: thiếu event `approved=False`; `objective=null` ném `AttributeError` |
| `python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py::test_fingerprint_mismatch_leaves_a_trace_in_the_event_log -v` sau khi hoàn tác fix event | 1 | 1 failed đúng assertion thiếu event `approved=False` |
| `python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py::test_fingerprint_mismatch_leaves_a_trace_in_the_event_log -v` sau khi khôi phục fix event | 0 | 1 passed in 0.07s |
| `python -m pytest tests/unit/orchestrator/test_steps_approval_probe.py -v` | 0 | 10 passed in 0.09s |
| `python -m pytest tests/unit/orchestrator -v` | 0 | 67 passed in 1.52s |
| `python -m pytest tests/unit/guardrails tests/unit/probe -m "not live_gateway" -v` | 0 | 149 passed, 3 deselected in 0.17s |
| `python -m pytest -m "not llm and not live_gateway" -q` | 0 | 376 passed, 15 deselected in 2.87s |
| `python -m compileall -q src/project_sentinel` | 0 | Không có output lỗi |
| `python -m pytest tests/test_no_doubles.py -q` | 0 | 2 passed in 0.12s |
| `git diff --check` | 0 | Không có whitespace error |
| `rg -n "class (Fake\|Mock\|Stub\|Dummy)\|provider.*fake" src tests` | 0 | Chỉ khớp docstring của guard test; không có class/provider bị cấm |

Các lệnh Python trên đã được chạy lại trong checkout chính sau khi local `main` được
fast-forward tới `origin/main` (`a458db7`) và branch
`feat/orchestrator-approval-probe` được tạo trực tiếp từ commit đó. Không còn worktree phụ.
Máy không có lệnh `python` toàn cục, nên các lượt test thành công chạy sau
`source .venv/bin/activate`; không dùng `PYTHONPATH`.

**Test mới thêm:**

- `test_risky_probe_pauses_for_approval` — phiếu duyệt có đủ dữ liệu và fingerprint.
- `test_plain_get_skips_approval` — GET trơn không bị dừng.
- `test_rejected_proposal_skips_straight_past_approval` — proposal không hợp lệ không mở cổng.
- `test_probe_without_a_decision_sends_nothing` — thiếu quyết định fail closed.
- `test_rejected_decision_marks_the_run_rejected` — reject chuyển run sang `REJECTED`.
- `test_rejection_writes_an_approval_event` — quyết định được audit trong run.
- `test_approved_decision_sends_exactly_one_request` — fingerprint từ file cho phép đúng một call.
- `test_decision_from_a_different_request_sends_nothing` — đổi probe sau duyệt tạo `DENIED` và zero call.
- `test_fingerprint_mismatch_leaves_a_trace_in_the_event_log` — chốt chặn ghi `approval approved=False`; hoàn tác fix làm test đỏ.
- `test_proposal_with_null_objective_does_not_crash` — file proposal nối lại vẫn tạo phiếu với purpose mặc định.

**Bất biến đã giữ:** Không sửa fingerprint guard; decision đi qua file; không thêm dependency; không skip; không lộ API key; không đổi Gateway/allowlist; không đụng reports/WebGoat; artifact mới đi qua redaction.

**Còn fail / chưa chạy được:** Không có trong các lệnh được yêu cầu. Test LLM và live Gateway bị loại đúng theo marker của lệnh nghiệm thu.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/orchestrator/steps.py`, nhánh `step_probe` khi fingerprint không khớp vẫn giữ state `PROBING` và đánh dấu step `skipped`; đây là hành vi plan hiện tại, nhưng Task 8 runner có thể muốn một state chi tiết hơn.
- **Giả định đã đặt:** `probe` trong proposal vẫn phải khớp shape `SafeProbe`; sai shape được đổi thành `StepFailure`. Riêng `objective` là metadata hiển thị nên null/sai kiểu dùng fallback an toàn.
- **Việc còn nợ:** Tích hợp hai bước vào runner/CLI thuộc Task 8–9, không thuộc Task 5.
- **Câu hỏi cho người dùng:** Không có.
