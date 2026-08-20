# Worklog — Plan 3 Task 7: năm nhóm metrics

**Ngày:** 2026-08-20 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/orchestrator-scrub-report-finalize` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 7`

---

## 1. Tóm tắt

Task tạo bộ thu năm nhóm số liệu của một run: thời gian, request, findings, approve/reject và lỗi. Metrics nay phân biệt request thật sự `SENT` với quyết định guardrail `DENIED`, giữ tổng lỗi đầy đủ qua nhóm `other`, và dung được artifact JSONL có dòng hỏng hoặc approval `detail=null`. Task cũng đóng dependency của Task 6; toàn bộ suite nghiệm thu hiện xanh với 400 test pass.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp dữ liệu định lượng cho `metrics.json`, báo cáo cuối và màn Overview của Plan 4.
- **Nằm ở đâu trong luồng:** Được gọi bởi `step_finalize` sau report và trước khi run kết thúc.
- **Không có nó thì hỏng gì:** Finalize ném `ModuleNotFoundError`, run không thể chuyển sang terminal state, report không nhận state cuối và main bị đỏ.
- **Ngoài phạm vi (cố ý không làm):** Không nối runner/CLI hoặc tổng hợp nhiều run; các phần đó thuộc Task 8–9 và Plan 4.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/metrics.py` | Tạo | Thêm `collect_metrics` và phân loại bước LLM/app | Module Task 7 chịu trách nhiệm thu năm nhóm số liệu |
| `tests/unit/orchestrator/test_metrics.py` | Tạo | Mười hai test cho thời gian, SENT/DENIED, JSONL hỏng, findings, approval và mọi nhóm errors | Chứng minh số liệu lấy từ artifact thật và không thổi phồng guardrail denial |
| `tests/unit/orchestrator/test_steps_scrub_report.py` | Sửa | Bỏ marker xfail của test final-state | Dependency metrics đã tồn tại nên regression state phải fail thật nếu tái xuất hiện |
| `src/project_sentinel/guardrails/events.py` | Sửa | Bỏ qua riêng dòng JSONL hỏng khi đọc security events | Một dòng hỏng không được làm sập metrics/report của cả run |
| `tests/unit/guardrails/test_events.py` | Sửa | Thêm test hai event hợp lệ bao quanh một dòng hỏng | Bảo vệ khuôn dung lỗi giống `read_log` |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đồng bộ SENT/DENIED, `errors.other`, null detail, tolerant events và elapsed `0.0ms` | Không để plan tiếp tục mô tả metric sai |
| `worklog/2026-08-20-plan3-task6-scrub-report-finalize.md` | Sửa | Chuyển nghiệm thu Task 6 từ partial sang pass sau Task 7 | Phản ánh trạng thái kiểm chứng cuối của PR gộp |
| `worklog/2026-08-20-plan3-task7-metrics.md` | Tạo | Ghi chức năng, quyết định và output thật của Task 7 | Báo cáo bắt buộc cho từng task |

**`git diff --cached --stat`:**

```text
 .../2026-08-17-rebuild-plan-3-w6-orchestrator.md   | 196 +++++++++++++++++--
 src/project_sentinel/guardrails/events.py          |   6 +-
 src/project_sentinel/orchestrator/metrics.py       |  96 ++++++++++
 src/project_sentinel/orchestrator/report.py        | 147 ++++++++++++++
 src/project_sentinel/orchestrator/steps.py         | 146 +++++++++++++-
 tests/unit/guardrails/test_events.py               |  17 ++
 tests/unit/orchestrator/test_metrics.py            | 183 ++++++++++++++++++
 tests/unit/orchestrator/test_steps_scrub_report.py | 212 +++++++++++++++++++++
 ...2026-08-20-plan3-task6-scrub-report-finalize.md | 172 +++++++++++++++++
 worklog/2026-08-20-plan3-task7-metrics.md          | 163 ++++++++++++++++
 10 files changed, 1316 insertions(+), 22 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** `collect_metrics` đọc thời gian từ các `StepRecord` đã hoàn thành, parse từng dòng gateway audit và chỉ tăng `requests_total` cho `status=SENT`; `DENIED` được giữ riêng trong `requests_denied`. Findings lấy từ `findings.json`; approval lấy từ events với `detail` được kiểm tra kiểu; error log được phân loại thành `llm`, `app`, `other`, còn `total` cộng cả ba. Cả gateway audit và security events đều bỏ qua riêng dòng JSONL không parse được để giữ các record hợp lệ còn lại.

**Luồng dữ liệu:** `RunRecord` + `gateway-requests.jsonl` + `findings.json` + `events.jsonl` + `run.log.jsonl` → `collect_metrics(record)` → dict metrics → `step_finalize` → `metrics.json` + terminal state

**Các quyết định kỹ thuật:**

- Lọc thời gian bằng `finished_at is not None`, không bằng truthiness của `elapsed_ms`, vì bước hợp lệ có thể hoàn thành trong `0.0ms` sau khi làm tròn.
- Lỗi LLM chỉ thuộc bước `analyze`; lỗi ứng dụng thuộc `scan`, `normalize`, `probe`, `scrub`; mọi error step khác vào `other` để `total` luôn là tổng thật.
- `findings.json` sai JSON/sai shape trả zero; không đoán số cảnh báo.
- Bỏ `xfail(strict=True)` ngay khi metrics có thật để test write-back terminal state trở thành guard bắt buộc.
- Audit entry là bằng chứng một quyết định đã được ghi, không phải bằng chứng packet đã rời máy; chỉ `status=SENT` được tính là request.

**Xử lý lỗi / trường hợp biên:** Fresh run trả toàn bộ count bằng zero; file request chưa tồn tại trả zero; dòng gateway/event JSONL hỏng bị bỏ riêng; findings sai JSON/sai shape trả zero; approval `detail=null` không gây `AttributeError` và được tính rejected; bước hoàn thành với elapsed zero vẫn có key trong breakdown.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `collect_metrics` | `collect_metrics(record: RunRecord) -> dict[str, Any]` | Thu năm nhóm metrics của đúng một run |
| Hằng | `LLM_STEPS` | `frozenset({"analyze"})` | Phân loại lỗi do LLM |
| Hằng | `APP_STEPS` | `frozenset({"scan", "normalize", "probe", "scrub"})` | Phân loại lỗi ứng dụng |
| Artifact | Metrics | `<run>/metrics.json` | Được `step_finalize` ghi qua redaction choke point |
| Trường | `requests_denied` | `metrics["requests_denied"]` | Số quyết định guardrail chặn, tách khỏi request đã gửi |
| Trường | `errors.other` | `metrics["errors"]["other"]` | Lỗi ở propose/approval/report/finalize hoặc bước chưa phân nhóm |

**Cách chạy:**

```bash
python -m pytest tests/unit/orchestrator tests/unit/guardrails -v
python -m pytest -m "not llm and not live_gateway" -q
```

**Output thật (đã che secret):**

```text
============================= 202 passed in 1.69s ==============================
400 passed, 15 deselected in 3.04s
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Tính metrics tại finalize từ record và các artifact bền trên đĩa, không giữ counter riêng trong bộ nhớ.

**Lý do:** Kiến trúc Plan 3 quy định thư mục run là nguồn sự thật dùng chung cho CLI và web. Đọc lại artifact làm metrics tái lập được sau khi tiến trình đổi, đồng thời tránh counter in-memory lệch khỏi log hoặc state thực.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Tăng counter trong từng step | Nhanh khi finalize | Mất khi process kết thúc và có thể lệch artifact trên đĩa |
| Lọc step bằng `if step.elapsed_ms` như snippet cũ | Ngắn | Làm mất bước hợp lệ có thời gian làm tròn thành `0.0ms` |
| Tạo fallback metrics trong `step_finalize` | Che được module thiếu | Làm xanh giả Task 6 và phân tán trách nhiệm thu số liệu |
| Đếm mọi dòng gateway audit là request | Code rất ngắn | DENIED chưa gửi packet; guardrail càng tốt thì metric càng bị thổi phồng |
| Đặt `total = llm + app` | Hai nhóm dễ đọc | Bỏ mất lỗi ở bốn step còn lại; tên `total` trở thành sai nghĩa |

**Đánh đổi đã chấp nhận:** Finalize đọc vài file nhỏ trong run thay vì dùng counter bộ nhớ; chi phí I/O nhỏ đổi lại tính bền và khả năng kiểm tra.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `python -m pytest tests/unit/orchestrator/test_metrics.py -v` trước production code | 2 | Collection error: thiếu `project_sentinel.orchestrator.metrics` |
| `python -m pytest tests/unit/orchestrator/test_metrics.py -v` | 0 | 8 passed in 0.03s |
| `python -m pytest tests/unit/orchestrator/test_metrics.py tests/unit/orchestrator/test_steps_scrub_report.py -v` | 0 | 19 passed in 0.11s |
| `python -m pytest tests/unit/orchestrator -v` | 0 | 86 passed in 1.55s |
| Hai test SENT/DENIED và error total trước fix | 1 | 2 failed: `requests_total` là 3 thay vì 1; `errors.total` là 2 thay vì 5 |
| Bốn regression sau fix | 0 | 4 passed in 0.04s |
| `python -m pytest tests/unit/orchestrator tests/unit/guardrails -v` lần đầu | 1 | 200 passed, 1 failed; test report cũ kỳ vọng corrupt events phải fail, trái contract tolerant events mới |
| `python -m pytest tests/unit/orchestrator tests/unit/guardrails -v` | 0 | 202 passed in 1.69s |
| `python -m pytest -m "not llm and not live_gateway" -q` | 0 | 400 passed, 15 deselected in 3.04s |
| `python -m compileall -q src/project_sentinel` | 0 | Không có output lỗi |
| `git diff --check` và `git diff --cached --check` | 0 | Không có whitespace error |

**Test mới thêm:**

- `test_all_five_metric_groups_are_present` — contract top-level có đủ năm nhóm.
- `test_step_and_total_elapsed_are_summed` — breakdown và tổng thời gian nhất quán.
- `test_requests_total_counts_sent_gateway_log_lines` / `...is_zero...` — SENT count có và không có log.
- `test_requests_total_counts_only_requests_that_were_sent` — DENIED không làm phồng request đã gửi; denial vẫn có metric riêng.
- `test_corrupt_gateway_log_line_is_ignored` — một audit line hỏng không làm mất SENT/DENIED hợp lệ.
- `test_findings_total_comes_from_findings_json` — số cảnh báo lấy từ artifact.
- `test_approve_and_reject_counts_come_from_events` — approval count lấy từ security events.
- `test_approval_with_null_detail_is_counted_as_rejected` — `detail=null` không làm sập metrics.
- `test_llm_and_app_errors_are_counted_separately` — hai loại lỗi không bị trộn.
- `test_errors_total_counts_every_error_line` — `total` gồm cả ba lỗi ở nhóm `other`.
- `test_metrics_on_a_fresh_run_are_all_zero` — fresh run không sinh số liệu giả.
- `test_one_corrupt_line_does_not_break_reading_events` — đọc được hai security events hợp lệ quanh dòng hỏng.

**Bất biến đã giữ:** Không mock/fake/stub; không skip; không secret; không network mới; không sửa Gateway/WebGoat/historical reports; metrics chỉ đọc artifact trong đúng run.

**Còn fail / chưa chạy được:** Không có trong các suite được yêu cầu; test LLM/live Gateway được loại theo marker của lệnh nghiệm thu.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/orchestrator/metrics.py` — phân nhóm `APP_STEPS` bám đúng plan hiện tại; error step mới sẽ tự vào `other` nên không mất khỏi total, nhưng reviewer vẫn cần quyết định có chuyển nó sang app hay không.
- **Giả định đã đặt:** Giả định cũ “mỗi dòng không rỗng trong `gateway-requests.jsonl` tương ứng một request đã gửi” là **sai**. Audit line chỉ chứng minh quyết định được ghi; implementation nay chỉ tính `status=SENT` vào `requests_total`, còn `DENIED` vào `requests_denied`.
- **Việc còn nợ:** Task 8 nối runner và chịu trách nhiệm chuyển mọi `StepFailure` sang trạng thái `FAILED` bền trên đĩa.
- **Câu hỏi cho người dùng:** Không có.
