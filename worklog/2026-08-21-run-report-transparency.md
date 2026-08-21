# Worklog — Minh bạch báo cáo lần chạy

**Ngày:** 2026-08-21 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/run-report-transparency` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md) · **Task ID:** Post-Task 10 transparency

---

## 1. Tóm tắt

Đã làm cho report và metrics nói rõ quyết định phê duyệt đến từ `cli-auto` hay người vận hành, đồng thời công bố số lời gọi LLM và phản hồi không hợp lệ. Đã thêm lệnh dọn run cũ chỉ chạy thủ công, đồng bộ checkbox của hai plan với lịch sử merge thật và tạo báo cáo Tuần 6 nêu thẳng bốn giới hạn đã quan sát. Lượt pipeline thật `20260821T042005Z` kết thúc `DONE`; artifact mới ghi `cli-auto`, 21 lời gọi LLM và 4 phản hồi không hợp lệ.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Bảo toàn nguồn gốc phê duyệt và chất lượng output LLM trong các artifact mà người chấm/người vận hành đọc.
- **Nằm ở đâu trong luồng:** `events.jsonl` + `analysis-summary.json` → `build_report()` / `collect_metrics()` → `report.md`, `report.json`, `metrics.json`.
- **Không có nó thì hỏng gì:** `--yes` trông giống phê duyệt của con người; retry do output LLM hỏng biến mất khỏi báo cáo; thư mục run tăng không giới hạn; plan và báo cáo tuần tạo ấn tượng sai về tiến độ/phạm vi bằng chứng.
- **Ngoài phạm vi (cố ý không làm):** Không đổi approval gate, không tự động xoá run trong runner, không tăng số probe mỗi lần chạy, không triển khai web Plan 4, không sửa kết quả LLM hoặc retry pipeline thật.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/metrics.py` | Sửa | Thêm `approvals.decided_by` và nhóm `llm.calls`/`llm.invalid_outputs`; input thiếu/hỏng trả 0 | Metrics phải nói ai duyệt và output LLM có lỗi hay không |
| `src/project_sentinel/orchestrator/report.py` | Sửa | Đưa approver và LLM counts vào JSON/Markdown; cảnh báo rõ `cli-auto` không phải người | `report.md` là artifact người đọc đầu tiên |
| `tests/unit/orchestrator/test_metrics.py` | Sửa | Test approver, summary đúng, summary thiếu/hỏng và schema zero-state | Khoá contract metrics mới |
| `tests/unit/orchestrator/test_steps_scrub_report.py` | Sửa | Test auto/human approver và số LLM qua `step_report` thật | Chứng minh artifact trên đĩa, không chỉ helper |
| `tests/unit/orchestrator/test_clean_runs_make_target.py` | Tạo | Chạy Make thật trong `tmp_path`, chứng minh giữ N run mới nhất và không có thư mục vẫn thành công | Không thử xoá trên artifact thật |
| `Makefile` | Sửa | Thêm target thủ công `clean-runs`, mặc định `KEEP=5` | Cho người vận hành kiểm soát tăng dung lượng |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Tick Task 1, 2, 10 theo commit/path/worklog thật | Plan phản ánh đúng phần đã hoàn tất |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-3-w6-orchestrator.md` | Sửa | Tick Task 3–9 theo PR #37–#42; giữ Task 10 trống vì chưa merge `main` | Không tick theo branch chưa tích hợp |
| `reports/week-06/report.md` | Tạo | Ghi bốn giới hạn: probe coverage ~4%, endpoint chưa chứng minh finding, eval bất định, web chưa làm | Báo cáo tuần phải nói đúng giới hạn bằng chứng |
| `worklog/2026-08-21-run-report-transparency.md` | Tạo | Ghi quyết định và output thật | Deliverable bắt buộc của repo |

**`git diff --stat`:**

```text
 Makefile                                           |   8 +-
 .../plans/2026-08-17-rebuild-plan-1-w1-w4.md       |  44 +++---
 .../2026-08-17-rebuild-plan-3-w6-orchestrator.md   |  64 ++++----
 reports/week-06/report.md                          |  27 ++++
 src/project_sentinel/orchestrator/metrics.py       |  33 +++-
 src/project_sentinel/orchestrator/report.py        |  40 +++++
 .../orchestrator/test_clean_runs_make_target.py    |  50 ++++++
 tests/unit/orchestrator/test_metrics.py            |  47 +++++-
 tests/unit/orchestrator/test_steps_scrub_report.py |  46 ++++++
 worklog/2026-08-21-run-report-transparency.md      | 170 +++++++++++++++++++++
 10 files changed, 470 insertions(+), 59 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Tái sử dụng đúng hai artifact đã có: sổ `events.jsonl` cho nguồn quyết định và `analysis-summary.json` cho số lần gọi/invalid output. Cả report và metrics chỉ nhận số đếm nguyên không âm; file summary thiếu, JSON hỏng hoặc sai kiểu trở về 0. `clean-runs` chỉ hoạt động khi người dùng gọi Make target và chỉ sau khi `cd artifacts/runs` thành công.

**Luồng dữ liệu:** `cli-auto`/`cli-operator` → approval event → tập approver đã sort → report/metrics; `analysis-summary.json` → parse tolerant → counts → report/metrics.

**Các quyết định kỹ thuật:**

- Dùng tập hợp rồi sort approver để artifact ổn định và không lặp tên.
- Hiển thị cảnh báo chỉ khi tập approver chứa chính xác `cli-auto`; approver người thật không bị gắn cảnh báo sai.
- Tạo `reports/week-06/report.md` vì `main` chưa có thư mục Tuần 6; Task 10 đang ở PR riêng và chỉ tạo `eval-results.md`.
- Không tick Plan 3 Task 10 vì commit `e2b40d0` mới được push, chưa nằm trong `main` mà branch này lấy làm gốc.

**Xử lý lỗi / trường hợp biên:** `detail=null` vẫn được tính rejected và không crash; summary thiếu/hỏng cho `{calls: 0, invalid_outputs: 0}`; không có approval hiển thị “(không có bước phê duyệt)”; không có `artifacts/runs` thì `clean-runs` thoát 0.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Metrics | Approval provenance | `metrics.json -> approvals.decided_by` | Danh sách actor đã quyết định |
| Metrics | LLM quality | `metrics.json -> llm` | `calls` và `invalid_outputs` |
| Report JSON | Approval/LLM | `report.json` | `approval_decided_by` và `llm` |
| Report Markdown | Cảnh báo auto approve | `report.md` | Nói rõ `--yes` không có người vận hành xác nhận |
| Make target | `clean-runs` | `KEEP=5 make clean-runs` | Giữ N thư mục run mới nhất khi gọi thủ công |
| Báo cáo tuần | Known limitations | `reports/week-06/report.md` | Bốn giới hạn với số liệu thật |

**Cách chạy:**

```bash
KEEP=5 make clean-runs
```

**Output thật từ pipeline `20260821T042005Z` (không chứa secret):**

```text
Lần chạy 20260821T042005Z: AWAITING_APPROVAL
Kết thúc: DONE
Báo cáo: /home/longngx04/VinSOC/project_sentinel_main/artifacts/runs/20260821T042005Z/report.md

- Người phê duyệt: cli-auto
> Lần chạy này dùng `--yes`: phê duyệt tự động, KHÔNG có người vận hành xác nhận.
- Lời gọi LLM: 21 (4 phản hồi không hợp lệ)
{'approved': 1, 'rejected': 0, 'decided_by': ['cli-auto']} {'calls': 21, 'invalid_outputs': 4}
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Tổng hợp provenance từ artifact gốc tại đúng hai nơi sinh output cuối, thay vì suy đoán từ số approve hoặc flag CLI.

**Lý do:** `approved=1` không cho biết con người hay automation đã quyết định. `events.jsonl` đã mang `decided_by`, còn `analysis-summary.json` đã mang số call/invalid; dùng hai nguồn này giữ báo cáo truy vết được và không thay đổi guardrail.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Suy ra auto-approve từ `approved=1` | Không thêm field | Sai: quyết định của người cũng có cùng count |
| Đọc argv/biến môi trường khi dựng report | Dễ biết có `--yes` | Không bền qua resume; artifact event mới là nguồn sự thật |
| Tự xoá run trong runner | Không cần thao tác | Xoá dữ liệu điều tra ngoài ý muốn; người dùng yêu cầu thủ công |
| Tick luôn Task 10 Plan 3 | Trông hoàn tất | Commit chưa merge vào `main`; sẽ biến plan thành tuyên bố sai |

**Đánh đổi đã chấp nhận:** Report và metrics cùng parse hai artifact nhỏ để độc lập; có ít logic lặp nhưng tránh coupling report vào metrics và giữ mỗi builder tự đủ dữ liệu.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| Ba file test targeted trước production code | 1 | 12 failed, 22 passed; bắt đúng thiếu approver/LLM/clean-runs |
| Ba file test targeted sau production code | 0 | 34 passed in 0.16s |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q` | 0 | 443 passed, 18 deselected in 7.18s |
| `make target-up` | 0 | Gateway sẵn sàng, endpoint health trả 401 khi không có key |
| Pipeline thật `run --yes --probe-method GET --probe-path /WebGoat/login` | 0 | Run `20260821T042005Z`, `DONE`, chạy đúng một lần |
| Trích `report.md` và `metrics.json` | 0 | `cli-auto`, cảnh báo không có người, 21 calls, 4 invalid |
| `make gateway-live-test` | 0 | 8 passed in 0.57s |
| `make guardrails-test` | 0 | 118 passed in 0.17s |
| `make target-down` | 0 | Đã xoá Gateway, WebGoat và network |

Suite offline thấp hơn kỳ vọng “≥452” vì branch này được tạo từ `main@3c8dc92`, chưa chứa 15 test của Task 10 vừa push trên `feat/orchestrator-eval`. Không có test nào fail; task này thêm 9 test và đưa main baseline lên 443.

**Test mới thêm:**

- `test_approval_metrics_name_the_automatic_approver` — metrics giữ actor `cli-auto`.
- `test_llm_metrics_come_from_analysis_summary` + hai ca missing/corrupt — counts đúng và tolerant.
- `test_report_says_when_approval_was_automatic` — report artifact cảnh báo auto approval.
- `test_report_names_a_human_approver_when_there_is_one` — không cảnh báo nhầm người thật.
- `test_report_discloses_llm_calls_and_invalid_outputs` — report nói rõ retry/invalid.
- Hai test `clean-runs` — giữ đúng N run mới và no-op khi chưa có thư mục.

**Bất biến đã giữ:** Không mock/fake/stub · không skip · không in/commit key · không đổi approval/probe guardrail · cleanup không tự chạy · không đụng report tuần 1–4 · không sửa/xoá runtime Task 10.

**Còn fail / chưa chạy được:** Không có test fail. Chênh lệch tổng test do Task 10 chưa merge đã giải thích phía trên.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `Makefile::clean-runs` dùng thứ tự tên thư mục; điều này đúng khi run ID giữ format UTC `%Y%m%dT%H%M%SZ` như invariant hiện tại.
- **Giả định đã đặt:** `decided_by` là actor provenance có chủ ý và giá trị `cli-auto` duy nhất biểu thị `--yes`.
- **Việc còn nợ:** Một lần chạy vẫn chỉ gửi một probe; endpoint hiện tại chưa tạo evidence gắn với finding; eval bất định; web Plan 4 chưa bắt đầu — đều đã ghi trong báo cáo tuần 6.
- **Câu hỏi cho người dùng:** Không có.

### Review hai lớp

| Layer | Severity | File:Line | Issue | Why it matters | Recommended fix |
|---|---|---|---|---|---|
| — | — | — | No actionable findings | — | — |

**VERDICT: APPROVE**
