# Worklog — Plan 3 Task 6: scrub response, report và finalize

**Ngày:** 2026-08-20 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/orchestrator-scrub-report-finalize` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** `Task 6`

---

## 1. Tóm tắt

Task thêm bước 7 quét prompt injection rồi che PII, bước 8 dựng báo cáo Markdown/JSON, và bước 9 chốt metrics. Report bỏ qua riêng dòng `analysis.jsonl` hỏng, đổi lỗi dựng báo cáo sang `StepFailure`, và finalize ghi terminal state trở lại `report.json`. Sau khi Task 7 cung cấp `orchestrator/metrics.py`, cả 11 test scrub/report/finalize đã xanh và suite rộng không còn failure.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Biến response không tin cậy thành artifact an toàn, cập nhật báo cáo cuối, rồi chuẩn bị chốt trạng thái và số liệu.
- **Nằm ở đâu trong luồng:** Bước 7–9, ngay sau `step_probe`; trạng thái đi qua `SCRUBBING` và `REPORTING` trước terminal state.
- **Không có nó thì hỏng gì:** Response ứng dụng có thể mang injection/PII vào bề mặt sau; run không có báo cáo tổng hợp hoặc điểm chốt metrics.
- **Ngoài phạm vi (cố ý không làm):** Không tạo `orchestrator/metrics.py` vì đó là Task 7; không nối runner/CLI vì thuộc Task 8–9; không sửa Gateway/probe.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/steps.py` | Sửa | Thêm `_read_probe_result`, `step_scrub`, `step_report`, `step_finalize` | Module sở hữu chín bước của orchestrator |
| `src/project_sentinel/orchestrator/report.py` | Tạo | Đọc artifact run, bỏ qua riêng dòng analysis JSONL hỏng, tổng hợp số liệu và dựng Markdown/JSON | Tách render báo cáo khỏi điều phối trạng thái mà không để một record lỗi xoá sổ báo cáo |
| `tests/unit/orchestrator/test_steps_scrub_report.py` | Tạo | Mười một test cho scrub/report/finalize, gồm JSONL hỏng, kiểu lỗi và terminal state | Chứng minh bước 7–8 và ghi rõ dependency Task 7 của bước 9 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Đồng bộ test, error handling, write-back state và bước bỏ xfail ở Task 7 | Không để plan tiếp tục mô tả implementation lỗi hoặc số test cũ |
| `worklog/2026-08-20-plan3-task6-scrub-report-finalize.md` | Tạo | Ghi thiết kế, output và hai fail dự kiến | Báo cáo bắt buộc của repository |

**`git diff --cached --stat`:**

```text
 .../2026-08-17-rebuild-plan-3-w6-orchestrator.md   |  84 +++++++-
 src/project_sentinel/orchestrator/report.py        | 147 ++++++++++++++
 src/project_sentinel/orchestrator/steps.py         | 146 +++++++++++++-
 tests/unit/orchestrator/test_steps_scrub_report.py | 216 +++++++++++++++++++++
 ...2026-08-20-plan3-task6-scrub-report-finalize.md | 169 ++++++++++++++++
 5 files changed, 755 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** `step_scrub` chỉ xử lý khi probe thật sự được gửi. Response được scan injection trước; match bị thay bằng marker, event injection được ghi, sau đó PII được redact và ghi event redaction, cuối cùng mới bọc trong thẻ untrusted. `step_report` bỏ riêng dòng analysis JSONL không parse được, còn lỗi đọc/render khác được đổi sang `StepFailure` để runner Task 8 có thể đưa run về `FAILED`. `step_finalize` gọi `collect_metrics` của Task 7, ghi `metrics.json`, giữ nguyên terminal `REJECTED/FAILED`, chuyển trạng thái khác sang `DONE`, rồi đồng bộ state đó trở lại `report.json` nếu file là JSON object hợp lệ.

**Luồng dữ liệu:** `probe-result.json` → injection scan → redaction → `scrubbed.json`/`events.jsonl` → `build_report` → `report.md` + `report.json` → `collect_metrics` (Task 7) → `metrics.json`

**Các quyết định kỹ thuật:**

- Scan injection trước redaction vì marker redaction có thể làm gãy mẫu cần phát hiện.
- Import `collect_metrics` nằm trong `step_finalize`, để tám test scrub/report chạy được trong khi module Task 7 chưa tồn tại; khi gọi finalize vẫn fail đúng dependency thật.
- Không đưa `safe_text` vào LLM; Task 6 chỉ tạo artifact an toàn và báo cáo thống kê.
- JSON output dùng `_write_json_artifact`; Markdown gọi `redact` trước khi ghi.
- Marker state test từng dùng `xfail(strict=True)` trong lúc Task 7 chưa tồn tại; Task 7 đã bỏ marker và test hiện pass thật.

**Xử lý lỗi / trường hợp biên:** Probe không gửi thì scrub được skip; thiếu result được coi như không có response; JSON result hỏng hoặc body không phải chuỗi tạo `StepFailure`; một dòng analysis JSONL hỏng bị bỏ qua nhưng các dòng hợp lệ vẫn vào báo cáo; lỗi I/O/ValueError khác trong report thành `StepFailure`; `report.json` hỏng ở finalize không bị ghi đè; finalize fail loud nếu Task 7 chưa có.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `step_scrub` | `step_scrub(record, ctx) -> RunRecord` | Quét injection, che PII, wrap response và ghi event |
| Hàm | `build_report` | `build_report(record) -> tuple[str, dict]` | Dựng Markdown và JSON ổn định từ artifact run |
| Hàm | `step_report` | `step_report(record, ctx) -> RunRecord` | Ghi `report.md` và `report.json` đã che dữ liệu nhạy cảm |
| Hàm | `step_finalize` | `step_finalize(record, ctx) -> RunRecord` | Điểm nối sang metrics Task 7 và terminal state |
| Artifact | Scrubbed response | `<run>/scrubbed.json` | Verdict, matches, redactions và safe_text đã wrap |
| Artifact | Final report | `<run>/report.md`, `<run>/report.json` | Báo cáo kỹ thuật và dữ liệu cho web |

**Cách chạy:**

```bash
source .venv/bin/activate
python -m pytest tests/unit/orchestrator/test_steps_scrub_report.py -v
```

**Output thật (đã che secret):**

```text
collected 11 items
test_clean_response_passes_through_wrapped PASSED
test_injection_in_response_is_detected_and_removed PASSED
test_injection_writes_an_event PASSED
test_pii_in_response_is_redacted_and_recorded PASSED
test_scrub_is_skipped_when_nothing_was_sent PASSED
test_report_contains_every_required_section PASSED
test_one_corrupt_analysis_line_does_not_kill_the_report PASSED
test_report_input_error_is_a_step_failure PASSED
test_final_state_is_written_back_into_the_report PASSED
test_finalize_writes_metrics_and_terminal_state PASSED
test_finalize_keeps_rejected_state PASSED
11 Task 6 tests passed; 19 passed in 0.11s khi chạy chung với 8 test metrics.
```

Dependency từng thiếu trước Task 7:

```text
ModuleNotFoundError: No module named 'project_sentinel.orchestrator.metrics'
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Dung lỗi theo từng dòng ở tầng đọc JSONL, giữ lỗi hạ tầng/render ở dạng `StepFailure`, và đồng bộ terminal state tại finalize — nơi trạng thái cuối mới được biết.

**Lý do:** Báo cáo là bước gần cuối nên một record JSONL hỏng không được làm mất các record còn lại, nhưng runner Task 8 chỉ có thể quản lý lỗi nếu nhận `StepFailure`. `build_report` chạy khi state còn `REPORTING`, vì vậy chỉ `step_finalize` mới có đủ thông tin để sửa `report.json` sang `DONE`, `REJECTED` hoặc `FAILED`. Plan vẫn quy định Task 7 mới cung cấp metrics; không tạo fallback để làm suite xanh giả.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Tạo `metrics.py` tối thiểu trong Task 6 | Toàn test xanh | Lấn phạm vi Task 7 và dễ trở thành implementation giả |
| Import metrics ở đầu module | Bám sát snippet từng dòng | Collection chết trước khi tám test scrub/report được chạy |
| Ghi response nguyên văn vào report | Dễ debug | Có thể tái phát tán injection/PII; trái guardrail Week 5 |
| Bỏ toàn bộ `analysis.jsonl` khi một dòng hỏng | Code ngắn | Làm mất các phân tích hợp lệ còn lại và khiến báo cáo sai lệch |
| Đặt terminal state trong `build_report` | Không cần write-back | Renderer chạy trước finalize nên chưa thể biết trạng thái cuối |

**Đánh đổi đã chấp nhận:** Task 6 được giữ trên cùng branch/PR với Task 7 thay vì merge riêng khi suite còn đỏ; hiện debt này đã được đóng.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `python -m pytest tests/unit/orchestrator/test_steps_scrub_report.py -v` trước code | 1 | ImportError: chưa có ba step |
| Test corrupt-analysis trước fix | 1 | 1 failed; `JSONDecodeError` thoát khỏi `_read_jsonl` |
| Test contract `StepFailure` khi tạm hoàn tác wrapper | 1 | 1 failed; nhận `JSONDecodeError` thay vì `StepFailure` |
| Hai test hồi quy sau khi trả lại fix | 0 | 2 passed in 0.08s |
| `python -m pytest tests/unit/orchestrator/test_steps_scrub_report.py -v` | 1 | 8 passed, 2 failed, 1 xfailed in 0.14s; hai fail chỉ thiếu `orchestrator.metrics` |
| `python -m pytest tests/unit/orchestrator -v` | 1 | 75 passed, 2 failed, 1 xfailed in 1.57s; hai fail đều thuộc finalize/Task 7 |
| `python -m pytest -m "not llm and not live_gateway" -q` | 1 | 384 passed, 2 failed, 15 deselected, 1 xfailed in 3.04s; hai fail đều thuộc finalize/Task 7 |
| `python -m pytest tests/unit/orchestrator/test_metrics.py tests/unit/orchestrator/test_steps_scrub_report.py -v` sau Task 7 | 0 | 19 passed in 0.11s |
| `python -m pytest tests/unit/orchestrator -v` sau Task 7 | 0 | 86 passed in 1.55s |
| `python -m pytest -m "not llm and not live_gateway" -q` sau Task 7 | 0 | 395 passed, 15 deselected in 2.96s |
| `python -m compileall -q src/project_sentinel` | 0 | Không có output lỗi |
| `git diff --check` | 0 | Không có whitespace error |

**Test mới thêm:**

- `test_clean_response_passes_through_wrapped` — clean response vẫn bị gắn nhãn untrusted.
- `test_injection_in_response_is_detected_and_removed` — chỉ dẫn độc hại bị cắt.
- `test_injection_writes_an_event` — detection có audit event.
- `test_pii_in_response_is_redacted_and_recorded` — email/phone không còn và có event.
- `test_scrub_is_skipped_when_nothing_was_sent` — không tạo nội dung giả khi không có response.
- `test_report_contains_every_required_section` — hai báo cáo có section và số liệu bắt buộc.
- `test_one_corrupt_analysis_line_does_not_kill_the_report` — một dòng hỏng không làm mất hai dòng hợp lệ.
- `test_report_input_error_is_a_step_failure` — lỗi report còn lại đi qua contract mà runner bắt được.
- `test_final_state_is_written_back_into_the_report` — bảo vệ state cuối khỏi `REPORTING` cứng.
- `test_finalize_writes_metrics_and_terminal_state` — metrics được ghi và run chuyển terminal.
- `test_finalize_keeps_rejected_state` — terminal `REJECTED` không bị đổi thành `DONE`.

**Bất biến đã giữ:** Không mock/stub; không skip; không dependency mới; không log secret; injection trước PII; output qua redaction; không đụng Gateway, WebGoat hoặc reports lịch sử.

**Còn fail / chưa chạy được:** Không còn failure trong các suite nghiệm thu sau Task 7; test LLM/live Gateway được loại theo marker của lệnh.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/orchestrator/report.py` — renderer hiện dùng field `title/severity/explanation/remediation/locations` đúng contract test Task 6; cần đối chiếu lại schema analysis thực tế khi Task 8 nối end-to-end.
- **Giả định đã đặt:** `body_preview` là chuỗi bounded do probe tool sinh; nếu artifact bị sửa thành kiểu khác thì bước scrub fail bằng `StepFailure` thay vì ép kiểu.
- **Việc còn nợ:** Task 8 mới lưu `state.json` quanh mỗi bước và điều phối lỗi end-to-end.
- **Câu hỏi cho người dùng:** Quyết định gộp Task 6 + Task 7 vào một PR đã được thực hiện; suite hiện xanh trước khi xin commit.
