# Worklog — Sửa backlog re-review của mentor (P0 + P1 bảo mật)

**Ngày:** 2026-08-21 · **Agent/Model:** Claude Code · Opus 5 ·
**Branch:** `feat/mentor-handoff-hardening` · **Task ID:** `re-review P0`

---

## 1. Tóm tắt

Mentor chấm lại ở `3d3508e` được **74,5/100 — REQUEST CHANGES** với 12 finding P0.
**Cả 12 đều kiểm chứng được là có thật** — khác lượt trước, không có claim nào sai.
Đã sửa 10 finding thuộc phạm vi code, cộng 4 mục P1 bảo mật. Hai finding còn lại
(P0-10 bản quyền dataset, P0-12 push/merge) là quyết định của người, không phải code.

Suite offline 597 → 720. **Fresh clone từ `git archive HEAD`: 9 fail → 0 fail.**

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** đóng các bypass an toàn còn lại và làm cho bản clone
  sạch tái lập được trạng thái xanh — hai điều kiện mentor đặt ra để gọi là bàn giao được.
- **Không có nó thì hỏng gì:** cổng phê duyệt bị qua mặt bằng một chuỗi `"false"`;
  ai có Gateway key đều bỏ qua được safe-payload registry; báo cáo nộp mentor chứa
  hướng dẫn `DROP TABLE`; và người clone repo không chạy nổi bước đầu của Quick Start.
- **Ngoài phạm vi (cố ý không làm):** UI; push/merge (chờ xác nhận bản quyền dataset).

---

## 3. Đã làm gì

| Finding | Nội dung | Trạng thái |
|---|---|---|
| P0-1 | `bool("false")` là `True` ở cổng HITL | Sửa + audit DENIED |
| P0-2 | Gateway không enforce query/header/body/template | Sửa ở cả Python và Nginx |
| P0-3 | Agent sinh exploit/destructive guidance | Sửa: schema closed-set + bộ quét |
| P0-4 | 6/18 objective ngoài allowlist | Sửa: kiểm ngay sau LLM, đếm lại |
| P0-5 | Proximity grouping gộp TP với FP | Sửa: tắt mặc định |
| P0-6 | Mất record nhưng vẫn báo thành công | Sửa: `completeness` + `missing_group_keys` |
| P0-7 | Provenance chưa chặn evidence bịa | Sửa: khớp nguyên văn content/dòng/score |
| P0-8 | Fresh clone đỏ 9 test | Sửa: evidence pack + bản đã lọc được commit |
| P0-9 | Quick Start `validate-analysis` fail | Sửa: tái sinh baseline |
| P0-11 | Demo Tuần 4 đã chết | Viết lại + test canh |
| P0-10 | Dataset recall chưa có quyền phân phối | **Chờ người dùng** |
| P0-12 | Branch chưa push/merge/CI | **Chờ người dùng** |
| P1 | Audit log mất 84/100 bản ghi khi ghi đồng thời | Sửa: append có khoá |
| P1 | `read_log` nhận scalar làm finalize sập | Sửa: chặn tại biên đọc |
| P1 | Symlink trong `runs/` đọc được file bất kỳ | Sửa: `_confined_run_root` |
| P1 | `triage_precision` là tên gọi sai | Sửa: đổi thành `label_accuracy` |

---

## 4. Làm như thế nào

**Cách tiếp cận:** kiểm chứng từng finding bằng cách chạy thật trước khi sửa; sau khi
sửa, đo lại đúng bài kiểm mà mentor đã dùng.

**Ba lỗi CỦA CHÍNH TÔI ở lượt sửa trước, lộ ra lần này:**

1. **Test đọc thư mục bị Git ignore.** `test_ground_truth_scoring.py` đọc
   `artifacts/runs/20260821T045519Z/`. Suite chỉ xanh trên máy còn giữ artifact cũ.
   Đây đúng là loại lỗi "kiểm thử nội dung một file không thay thế được việc kiểm thử
   rằng file đó thật sự có" mà chính báo cáo Tuần 6 đã ghi.

2. **Provenance so nguyên văn với bản chưa bọc.** Agent nhìn thấy evidence **đã bọc**
   trong thẻ `<untrusted_app_response>` nên nó echo lại bản bọc. Luật mới của tôi làm
   **0/23 record** qua được — một luật provenance bắn nhầm là một luật làm mất toàn bộ
   kết quả. Phát hiện được vì `completeness: PARTIAL` (P0-6) báo động đúng lúc.

3. **Objective sai làm mất cả record.** `verification_objective` là trường tuỳ chọn;
   vứt cả phần phân tích vì một đề xuất kiểm chứng sai là đổi một lỗi nhỏ lấy một mất
   mát lớn. Đổi sang: đặt `null` + đếm lại.

**Hai lần thu hẹp luật sau khi đo trên dữ liệu thật (P0-3):**

- Backtick trong văn xuôi kỹ thuật gần như luôn là code span Markdown (`` `kid` ``,
  `` `accountName` ``), không phải command substitution. Không thu hẹp thì 17/21 record
  hợp lệ bị đánh trượt.
- `"gửi ký tự đặc biệt như ';' hoặc '--'"` là văn xuôi mô tả **ký tự**, không phải
  payload.

Sau khi thu hẹp: 10/21 record vi phạm, tất cả đều thật.

**Quyết định thiết kế đáng nói:**

- **`evidence` cố ý không bị quét.** Nó chứa mã nguồn WebGoat nguyên văn, mà WebGoat
  có sẵn chuỗi tấn công trong comment.
- **GET không có body**, nên `payload_kind` của objective GET mô tả ý định quan sát,
  không mô tả dữ liệu được gửi. So khớp cùng một cách với POST sẽ từ chối mọi objective
  GET. GET kèm payload_kind **vẫn** cần người phê duyệt.
- **Quyết định không đọc được ≠ quyết định từ chối.** Nó là quyết định *hỏng*, và người
  vận hành cần biết. Nên `read_decision` ném lỗi thay vì trả `False`.

---

## 5. Output là gì

| Loại | Tên | Mô tả |
|---|---|---|
| Module | `analysis/output_safety.py` | Quét payload khai thác trong field do Agent viết |
| Module | `eval/refresh_recall_truth.py` | Sinh lại bản đã lọc của bộ nhãn recall |
| Script | `scripts/demo/agent_proposal_denied.py` | Ba dạng đề xuất sai đều bị chặn |
| Script | `scripts/demo/rate_limited_status.py` | Ánh xạ 429 qua `send_probe` thật |
| Config | `configs/gateway/endpoint-allowlist.json` | Thêm registry `templates` |
| Config | `infra/docker/gateway/.../default.conf.template` | Chặn query/header/body/template |
| Test | 9 file mới | Xem mục 7 |

**Đo lại đúng các bypass mentor tìm ra, trên Gateway thật:**

```text
                                   trước → sau
query string ngoài policy            302 → 400
không khai template                  200 → 403
template hợp lệ ở endpoint khác      200 → 403
POST body tự do                      302 → 403
body 4 KB                            302 → 413
đường hợp lệ                         200 → 200   (không hỏng)
```

**Artifact cuối cùng, sau khi sửa:**

```text
completeness  PARTIAL (21/23 record, 2 nhóm thiếu có tên)
unsafe_output 0        — 0 lần xuất hiện DROP TABLE / '; id / ' OR '1'='1
schema        21 record hợp lệ
approval      decided_by = cli-operator
verdict       inconclusive — unrelated_endpoint
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** đóng bypass ở **cả hai lớp** Python và Nginx; ưu tiên "không mất
record" khi thiết kế các luật mới.

**Lý do:** hai allowlist chỉ có nghĩa là hai lần kiểm khi chúng nói **cùng một chính
sách**. Trước đây Nginx chỉ biết method/path còn Python biết cả template, nên lớp thứ
hai thực chất mỏng hơn lớp thứ nhất. Có test đối chiếu hai tập template phải bằng nhau.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Vì sao loại |
|---|---|
| Cho `"false"` thành `False` | Đoán ý người viết ở đúng ranh giới không được đoán |
| Objective sai → loại cả record | Đổi một lỗi nhỏ lấy mất toàn bộ phân tích; đã đo: 0/23 record |
| Giữ proximity merge, thêm verdict theo từng finding | Đổi schema lớn hơn nhiều để cứu một heuristic vốn không đúng |
| Quét cả `evidence` tìm payload | WebGoat cố ý có chuỗi tấn công trong comment; mọi record sẽ trượt |

**Đánh đổi đã chấp nhận:** tắt proximity merge làm số nhóm 21 → 23, tức thêm 2 lời gọi
LLM mỗi lần chạy. Đúng đắn quan trọng hơn.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả thật |
|---|---:|---|
| `pytest -m "not llm and not live_gateway" -q` | 0 | `720 passed` (trước: 597) |
| **`git archive HEAD` → pytest** | 0 | `717 passed, 3 skipped, 0 fail` (trước: **9 fail**) |
| `make validate-analysis` (Quick Start) | 0 | `Validated 21 analysis records` (trước: **exit 4**) |
| `bash scripts/demo-week4.sh` | 0 | `14 pass / 0 fail` (trước: **9/5**) |
| `make gateway-live-test` | 0 | `8 passed` |
| `pytest tests/integration/test_gateway_policy_enforcement.py` | 0 | `10 passed` — qua Nginx thật |
| `make guardrails-test` | 0 | `140 passed` |
| `make lint` / `make typecheck` | 0 | sạch |
| `make coverage` | 0 | `80,5 %` |
| CLI đầu-cuối, người duyệt | 0 | `decided_by: ["cli-operator"]`, `DONE` |
| CLI đầu-cuối, người từ chối | 0 | `requests_total: 0`, `REJECTED` |

**Test mới (9 file):** `test_decision_parsing_is_strict.py` ·
`test_grouping_does_not_merge_distinct_sinks.py` · `test_output_safety.py` ·
`test_provenance_is_exact.py` · `test_template_binding.py` ·
`test_gateway_policy_enforcement.py` · `test_partial_analysis_is_disclosed.py` ·
`test_audit_log_concurrency.py` · `test_run_path_and_log_boundaries.py` ·
`test_demo_scripts_are_alive.py`

**Bất biến đã giữ:** không đụng `artifacts/normalized/findings.json` của người dùng
(đã kiểm bằng `git show --stat`) · không đụng `reports/week-01..05/` · không push.

**Còn fail / chưa chạy được:** `make llm-test` chưa chạy lại sau các thay đổi này.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `analysis/output_safety.py` — regex trên văn xuôi hai
  ngôn ngữ. Đã thu hẹp hai lần dựa trên dữ liệu thật, nhưng nó vẫn là heuristic. Nó
  chỉ làm record bị loại rồi sinh lại, không bao giờ làm lọt payload.
- **Điểm cần quyết định:** 17/23 objective bị từ chối vì Agent đề xuất `special_chars`
  cho POST trong khi registry chỉ duyệt `empty_value`/`long_string`. Hai hướng: review
  thêm payload đó vào registry, hoặc sửa prompt cho Agent đọc đúng `allowed_endpoints`.
- **Việc còn nợ:** over-claim **tăng** 33,3 % → 40,0 % ở lần chạy cuối. Sửa gộp nhóm
  bỏ được nguyên nhân máy móc, nhưng Agent vẫn tự xếp sai hai truy vấn hằng. Đây là
  giới hạn phán đoán, không phải lỗi cấu trúc.
- **Câu hỏi cho người dùng:** P0-10 (bản quyền dataset của mentor) và P0-12 (push/PR)
  đều cần quyết định của bạn. Mentor yêu cầu **không push trước khi có xác nhận tác giả**.
