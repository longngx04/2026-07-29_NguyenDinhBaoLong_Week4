# Worklog — Plan 3 Task 9: CLI run, runs và approve

**Ngày:** 2026-08-20 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/orchestrator-cli` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 9`

---

## 1. Tóm tắt

Đã thêm ba lệnh CLI `run`, `runs`, `approve` và hai Make targets để người vận hành chạy/quan sát orchestrator. Quyết định CLI luôn sao chép fingerprint từ `approval-request.json`, không tự tính lại hoặc đi vòng `decision.json`; scan override chỉ nhận một executable path. Kết quả cuối là 12 test CLI, 117 test orchestrator+CLI và 427 test không LLM/live Gateway đều xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp giao diện dòng lệnh để bắt đầu luồng chín bước, liệt kê run đã lưu và ghi quyết định cho run đang chờ duyệt.
- **Nằm ở đâu trong luồng:** CLI/Make → `RunContext` → `start_run`/`resume_run` → artifact trong `artifacts/runs/<run_id>/`.
- **Không có nó thì hỏng gì:** Người vận hành không có đường chính thức để chạy runner hoặc xem trạng thái; Plan 4 cũng thiếu hành vi tham chiếu cho approve/resume.
- **Ngoài phạm vi (cố ý không làm):** Không chạy E2E tốn token/Gateway trong phiên này vì Docker daemon không sẵn sàng; không thêm UI web và không implement Task 10.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/cli.py` | Sửa | Thêm parser/handler cho `run`, `runs`, `approve`; validate state, key, run ID và fingerprint; hiển thị trạng thái/report. | Bề mặt CLI của Task 9. |
| `src/project_sentinel/orchestrator/context.py` | Sửa | Đọc `SENTINEL_RUNS_DIR`; chỉ nhận `SENTINEL_SCAN_COMMAND` khi nó là đúng một file executable, nếu không cảnh báo và dùng scanner mặc định. | Cho CLI chọn nơi lưu run và test bằng subprocess thật nhanh mà không biến chuỗi môi trường thành argv tùy ý. |
| `Makefile` | Sửa | Thêm `run`, `runs`; target `run` nạp Gateway key từ env/`.env` mà không in key. | Cho người vận hành chạy bằng lệnh ngắn, nhất quán với target Gateway. |
| `tests/integration/test_cli_run.py` | Tạo | Thêm 12 integration test subprocess thật cho failure persistence, listing, approval binding và các ca âm. | Chứng minh hành vi CLI từ ranh giới tiến trình. |
| `tests/unit/orchestrator/test_steps_scan_normalize.py` | Sửa | Thêm test âm chứng minh chuỗi shell trong scan override bị bỏ qua và phát cảnh báo. | Khoá hành vi deny-by-default của `RunContext.default()`. |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Thay hướng dẫn `shlex.split` bằng executable-path-only và đổi fixture CLI sang script thật. | Giữ Task 9 trong plan khớp guardrail đã chọn. |
| `worklog/2026-08-20-plan3-task9-cli.md` | Tạo | Ghi thiết kế, output thật, giới hạn môi trường và cách chạy CLI. | Bắt buộc theo `AGENTS.md`. |

**`git diff --stat`:**

```text
 Makefile                                           |  13 +-
 .../2026-08-17-rebuild-plan-3-w6-orchestrator.md   |  50 +++--
 src/project_sentinel/cli.py                        | 154 ++++++++++++++
 src/project_sentinel/orchestrator/context.py       |  25 ++-
 tests/integration/test_cli_run.py                  | 228 +++++++++++++++++++++
 .../unit/orchestrator/test_steps_scan_normalize.py |  14 +-
 worklog/2026-08-20-plan3-task9-cli.md              | 189 +++++++++++++++++
 7 files changed, 649 insertions(+), 24 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** CLI dựng `RunContext.default()` rồi chỉ gọi API công khai của orchestrator. `run` fail-fast khi thiếu Gateway key, chạy phase đầu, đọc phiếu duyệt từ file và dùng chính fingerprint trong file cho prompt hoặc `--yes`; sau đó ghi `decision.json` và resume. `approve` chỉ nhận run do `list_runs` tìm thấy, chỉ ghi quyết định khi state là `AWAITING_APPROVAL`, và từ chối phiếu có fingerprint rỗng. `runs` chịu được `state.json` hỏng bằng cách in `CORRUPT` thay vì làm sập toàn lệnh.

**Luồng dữ liệu:** `CLI args + env` → `RunContext` → `start_run` → `approval-request.json` → `ApprovalDecision` cùng fingerprint → `decision.json` → `resume_run` → `report.md/state.json`

**Các quyết định kỹ thuật:**

- `SENTINEL_SCAN_COMMAND` chỉ là một executable path đã qua `is_file()` và `os.access(..., X_OK)`; không tách tham số, test vẫn chạy tiến trình thật.
- Fingerprint đi qua file phiếu duyệt cho cả `run --yes` và `approve`; code mẫu cũ của plan thiếu trường này vì plan cũ hơn guardrail Task 5.
- `approve reject` không cần Gateway key vì không gửi request; `approve approve` và `run` bắt buộc có key.
- `approve` kiểm tra membership trong `list_runs` trước `load_run`, chặn `../run_id`.
- Make target chỉ truyền key vào environment của tiến trình con, không echo giá trị.

**Xử lý lỗi / trường hợp biên:** Run không tồn tại/sai path, run terminal, state hỏng, phiếu duyệt hỏng hoặc thiếu fingerprint đều trả mã khác 0 không có traceback. Scan thất bại vẫn để lại `state.json`; listing tiếp tục hoạt động khi một run bị hỏng.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| CLI | `run` | `python -m project_sentinel.cli run [--yes]` | Chạy toàn bộ pipeline và hỏi duyệt khi cần. |
| CLI | `runs` | `python -m project_sentinel.cli runs` | Liệt kê `run_id` và state; đánh dấu bản ghi hỏng. |
| CLI | `approve` | `python -m project_sentinel.cli approve <run_id> --decision approve\|reject` | Ghi quyết định có fingerprint rồi resume. |
| Env | `SENTINEL_RUNS_DIR` | path | Đổi thư mục run, chủ yếu cho test/automation. |
| Env | `SENTINEL_SCAN_COMMAND` | executable path | Thay scanner bằng đúng một file executable; giá trị có tham số hoặc không executable bị bỏ qua. |
| Make | `run`, `runs` | `make run`, `make runs` | Wrapper vận hành. |

**Cách chạy:**

```bash
make target-up
make run
make runs
```

**Output thật (đã che secret):**

```text
$ make runs
Chưa có lần chạy nào.
EXIT_CODE=0
```

CLI help thật:

```text
usage: cli.py [-h] {analyze,validate,probe,run,runs,approve,demo} ...
    run                 Chạy toàn bộ luồng chín bước
    runs                Liệt kê các lần chạy
    approve             Quyết định phê duyệt cho một lần chạy
```

TDD đỏ trước implementation:

```text
collected 7 items
5 failed, 2 passed in 1.20s
cli.py: error: argument command: invalid choice: 'run'
EXIT_CODE=1
```

Guardrail fingerprint đỏ trước khi thêm validation:

```text
test_approve_rejects_an_approval_request_with_empty_fingerprint FAILED
assert 0 != 0
EXIT_CODE=1
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** CLI mỏng gọi runner, còn trạng thái và quyết định nằm trong artifact trên đĩa.

**Lý do:** Plan quy định orchestrator là động cơ duy nhất và `state.json` là nguồn sự thật chung cho CLI/web. Việc đọc fingerprint từ phiếu duyệt còn giữ đúng ràng buộc Task 5: UI/CLI chỉ có file để biết request nào đang được duyệt.

**Hardening scan override — chọn phương án A:** Chỉ chấp nhận đường dẫn tới một file executable, không nhận tham số. Cách này chặn `/bin/sh -c ...`, giữ được integration test subprocess thật bằng script trong `tmp_path`, và có diff nhỏ hơn việc tạo test-mode/config surface mới; đánh đổi còn lại là người kiểm soát cả environment lẫn một file executable vẫn có thể chọn file đó.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| CLI tự gọi từng `step_*` | Dễ tùy biến output | Lặp logic runner, có thể khác hành vi web và mất persistence. |
| Tự tính fingerprint từ `SafeProbe` trong CLI | Ít đọc file | Chỉ chứng minh hàm băm; không chứng minh phiếu mà người vận hành thấy là phiếu được duyệt. |
| Tin mọi `run_id` rồi gọi `load_run` | Code ngắn | Cho phép path traversal và đọc/ghi ngoài `runs_dir`. |
| Cho approve trên run terminal | Có vẻ tiện retry | Có thể ghi đè quyết định lịch sử hoặc gửi lại request; retry cần hợp đồng riêng. |
| Tách scan override thành argv bằng `shlex.split` | Hỗ trợ executable kèm tham số | Cho phép `/bin/sh -c ...`; thay bằng một executable path duy nhất. |
| Bỏ hẳn override production | Bề mặt production sạch nhất | Cần thiết kế test entrypoint/config riêng và có nguy cơ chỉ chuyển điểm bypass; quá rộng cho hardening Task 9 này. |
| Chỉ bật override khi có `PYTEST_CURRENT_TEST` | Diff rất nhỏ | Biến này cũng do người gọi đặt được và tạo test-only branch trong production. |

**Đánh đổi đã chấp nhận:** `run` yêu cầu Gateway key ngay từ đầu dù một số lần phân tích có thể không đề xuất probe; fail-fast tránh một pipeline dài kết thúc bằng request thiếu xác thực.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `.venv/bin/python -m pytest tests/integration/test_cli_run.py -v` | 0 | 12 passed trong 2.64s. |
| `.venv/bin/python -m pytest tests/unit/orchestrator/test_steps_scan_normalize.py::test_scan_command_override_rejects_a_shell_invocation -v` trước implementation | 1 | FAIL đúng tại `assert "/bin/sh" not in ctx.scan_command`; giá trị cũ là `['/bin/sh', '-c', 'echo pwned']`. |
| `.venv/bin/python -m pytest tests/unit/orchestrator tests/integration/test_cli_run.py -v` | 0 | 117 passed trong 4.20s. |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q` | 0 | 427 passed, 15 deselected trong 6.21s. |
| `source .venv/bin/activate && python -m compileall -q src/project_sentinel` | 0 | Không có lỗi biên dịch. |
| `git diff --check` | 0 | Không có whitespace error. |
| `make -n run runs` | 0 | Hai target resolve đúng interpreter; key không được in giá trị. |
| `make runs` | 0 | `Chưa có lần chạy nào.` |

**Test mới thêm:**

- `test_runs_command_exits_zero_even_with_no_runs` — empty listing là thành công.
- `test_run_reports_failure_clearly_when_scan_cannot_start` — lỗi scan không có traceback.
- `test_run_without_a_gateway_key_fails_before_creating_a_run` — thiếu key không tạo artifact nửa vời.
- `test_failed_run_still_leaves_state_on_disk` — failure có state bền.
- `test_runs_command_lists_the_failed_run` — CLI nhìn thấy run lỗi.
- `test_runs_command_marks_a_corrupt_state_without_crashing` — một state hỏng không xóa sổ listing.
- `test_approve_on_unknown_run_fails_clearly` — unknown run fail rõ.
- `test_approve_reject_copies_fingerprint_from_the_request_file` — fingerprint đi qua file và reject không gửi request.
- `test_approve_rejects_an_approval_request_with_empty_fingerprint` — chuỗi rỗng không hợp lệ.
- `test_approve_rejects_a_run_id_outside_the_runs_directory` — chặn path traversal.
- `test_approve_does_not_overwrite_a_terminal_run` — không sửa run đã kết thúc.
- `test_approve_requires_a_gateway_key_only_when_approving` — approve cần key, reject không cần.
- `test_scan_command_override_rejects_a_shell_invocation` — chuỗi `/bin/sh -c ...` bị bỏ qua, scanner mặc định được dùng và có cảnh báo.

### Happy path thật (Gateway + WebGoat + LLM thật)

Chạy ngày 2026-08-20, Docker `sentinel-sec-gateway-1` và `sentinel-sec-webgoat-1` đang lên.

```bash
KEY=$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env)
SENTINEL_GATEWAY_API_KEY="$KEY" .venv/bin/python -m project_sentinel.cli run --yes
```

```text
Lần chạy 20260820T165022Z: AWAITING_APPROVAL
Kết thúc: DONE
Báo cáo: .../artifacts/runs/20260820T165022Z/report.md
exit=0
```

Cả chín bước `done`, `state.json` = `DONE`, `error` = `null`.

**16 artifact sinh ra:** `raw.json`, `findings.json`, `analysis.jsonl`, `analysis-summary.json`,
`proposal.json`, `approval-request.json`, `decision.json`, `probe-result.json`, `scrubbed.json`,
`report.md`, `report.json`, `metrics.json`, `events.jsonl`, `gateway-requests.jsonl`,
`run.log.jsonl` (16 dòng), `state.json`.

**`metrics.json` của lần chạy thật:**

```json
{
  "total_elapsed_ms": 294978.82,
  "step_elapsed_ms": {"scan": 6402.96, "normalize": 42.5, "analyze": 288500.79,
                      "propose": 1.42, "approval": 0.6, "probe": 23.58,
                      "scrub": 0.21, "report": 6.76},
  "requests_total": 1, "requests_denied": 0, "findings_total": 23,
  "approvals": {"approved": 1, "rejected": 0},
  "errors": {"llm": 0, "app": 0, "other": 0, "total": 0}
}
```

Bước `analyze` chiếm 288,5s trên tổng 295s — 98% thời gian chạy là gọi LLM thật.

**Request duy nhất rời hệ thống, qua Gateway:**

```json
{"method": "POST", "path": "/WebGoat/attack", "payload_type": "special_chars",
 "status": "SENT", "status_code": 302, "policy_decision": "ALLOWED"}
```

Agent đề xuất 17 objective; `step_propose` lấy cái đầu tiên, allowlist duyệt
`POST /WebGoat/attack`. Cổng phê duyệt ghi đúng một sự kiện:

```json
{"kind": "approval", "detail": {"approved": true, "method": "POST",
 "path": "/WebGoat/attack", "decided_by": "cli-auto"}}
```

**Hai điều lần chạy này KHÔNG chứng minh được:**

1. WebGoat trả `302` (chuyển hướng đăng nhập) nên `body_preview` rỗng — bước `scrub`
   chạy trên chuỗi rỗng, tức là **đường phát hiện injection và che PII chưa được
   kích hoạt** trong lần chạy thật này. `events.jsonl` chỉ có 1 sự kiện `approval`,
   không có `injection`/`redaction`/`allowlist_block`.
2. Không có nhánh từ chối nào được chạy (dùng `--yes`), nên `requests_denied` = 0.

Muốn trình diễn guardrail thì cần một response có nội dung thật — hoặc probe tới
endpoint trả 200, hoặc đăng nhập WebGoat trước.

**Bất biến đã giữ:** Không mock/stub/fake; subprocess thật; không skip; không in secret; fingerprint qua file; request chỉ qua runner/probe/Gateway; không dependency mới; không đụng historical reports.

**Còn fail / chưa chạy được:** Không có test nào fail trong phạm vi hardening này. Test LLM/live Gateway bị loại khỏi full suite theo marker; một CLI run thật riêng đã hoàn tất với 21/21 analysis records hợp lệ và `invalid_outputs=0` sau khi cấu hình OpenRouter được sửa, nhưng không được tính thay cho suite trên.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/cli.py` nhánh `run --yes`; integration không gọi happy path LLM/Gateway thật vì Docker chưa sẵn sàng, nhưng fingerprint chung được kiểm chứng qua nhánh `approve reject` và helper dùng chung.
- **Giả định đã đặt:** `.env` chứa cùng Gateway key mà `make target-up` và `make run` sử dụng; nếu hai tiến trình dùng key khác, Gateway sẽ trả 401.
- **Việc còn nợ:** Người vận hành chạy happy path thật sau khi bật Docker; output và report cần được xem thủ công như hướng dẫn bàn giao.
- **Câu hỏi cho người dùng:** Không có.
