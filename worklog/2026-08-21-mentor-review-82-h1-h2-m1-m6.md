# Worklog — Đóng blocker H-1/H-2 và các finding M của vòng review 82,0/100

**Ngày:** 2026-08-21 · **Agent/Model:** Claude Code · Opus 5 ·
**Branch:** `feat/mentor-handoff-hardening` · **Plan:** [`worklog/2026-08-21-mentor-handoff-review-local.md`](2026-08-21-mentor-handoff-review-local.md) · **Task ID:** `Review vòng 3`

---

## 1. Tóm tắt

Đóng hai blocker mentor đặt trước UI có thao tác (H-1 Gateway tin header template
do caller khai; H-2 `resume_run` không nguyên tử nên probe chạy hai lần), cộng
sáu finding M và L-1. Phục vụ đúng một mục tiêu: mở được UI Phase B (approve /
resume / probe) mà không nối nút bấm vào một backend còn lỗ. Kết quả: cả hai
bypass đã đo lại trên Nginx thật và tiến trình thật là đã đóng; 750 test offline
xanh, snapshot sạch 0 failed.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** biến `X-Sentinel-Template` từ một *lời khai của
  caller* thành một *ràng buộc thi hành được tại hạ tầng*, và biến `resume_run`
  từ ba bước rời nhau thành một giao dịch có khoá.
- **Nằm ở đâu trong luồng:** H-1 ở biên giới mạng (Nginx, lớp enforce thứ hai,
  sau `probe/tool.py`); H-2 ở `orchestrator/runner.py`, ngay trước phase hai.
- **Không có nó thì hỏng gì:** bất kỳ ai có Gateway key đều gửi được body tùy ý
  tới WebGoat dù safe-payload registry nói không; và một cú double-click trên UI
  gửi hai request kiểm chứng cho một phiếu duyệt.
- **Ngoài phạm vi (cố ý không làm):**
  - **H-3** (Agent chưa sinh được objective dùng được) — đã sửa phần *code*
    (feedback retry nêu đúng endpoint hợp lệ; thêm `valid_objective_count` và
    `objective_validity_rate`), nhưng **chưa chạy lại LLM thật** để đo cải thiện.
    Đó là gate bàn giao cuối, không phải gate UI.
  - **M-7** (quyền tái phân phối dataset mentor) và **M-8** (push/PR/CI) —
    quyết định của người dùng, không phải việc code.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `infra/docker/gateway/templates/default.conf.template` | Sửa | Thêm `$sentinel_tmpl_method_ok`, `$sentinel_body_len_ok`, `$sentinel_canonical_body`; `proxy_set_body`; `proxy_pass_request_headers off`; chặn `Transfer-Encoding`; Accept/User-Agent đặt cứng | Đây là lớp enforce thứ hai — chỗ duy nhất chặn được khi tầng Python bị bỏ qua |
| `tests/unit/gateway/test_gateway_config_matches_registry.py` | Tạo | Đối chiếu ba map Nginx với `endpoint-allowlist.json` + `payloads.py` | Ba map là bản chép tay; chép tay thì sẽ lệch, trừ khi có test |
| `tests/integration/test_gateway_policy_enforcement.py` | Sửa | +5 ca live (body tùy ý, body cùng độ dài, template POST dùng cho GET, template không payload kèm body, chunked); `_status` không đi theo redirect | 10 ca cũ không có ca "tên template hợp lệ + body không khớp" |
| `Makefile` | Sửa | `agent-test` và `gateway-live-test` chạy `test_gateway_policy_enforcement.py` | File này trước đây chỉ xanh khi gọi trực tiếp |
| `src/project_sentinel/orchestrator/run_lock.py` | Tạo | `run_lock()` (flock, không chờ), `idempotency_key()`, `read_claim()`, `write_claim()` | CLI và web là hai tiến trình — `threading.Lock` không đủ |
| `src/project_sentinel/orchestrator/runner.py` | Sửa | Toàn bộ nạp→kiểm→chiếm nằm trong một khoá; tách `_resume_refusal()` | Race đã được ép chạy hai lần |
| `src/project_sentinel/orchestrator/state.py` | Sửa | `_confined_run_root` → `confined_run_root` (public) | `resume_run` cần nó cho bước kiểm tồn tại, thay vì ghép đường dẫn thô |
| `src/project_sentinel/analysis/validators.py` | Sửa | `validate_provenance` so khớp ID và location **hai chiều** | Prompt viết "Preserve supplied identifiers and locations exactly" |
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Tách `_ResponseErrors`/`_validate_response`/`_settle`; `unresolved_groups` vs `invalid_responses_observed`; token cộng mọi lần gọi; `_load_allowlist` trả lý do suy giảm; `_allowed_endpoints_hint` | M-2 + M-3 + phần code của H-3 |
| `src/project_sentinel/orchestrator/report.py` | Sửa | Phân biệt "Agent đề xuất" với "Người vận hành chỉ định"; tách `analysis_groups` khỏi `analysis_records`; in tỷ lệ objective và `degraded_reasons` | M-5 |
| `scripts/scan-opengrep.sh` | Sửa | Nhận đường dẫn output từ `$1` | Script bỏ qua argument nên mọi lần chạy đều báo `used_fallback: true` |
| `tests/test_evidence_pack_has_no_secrets.py` + `tests/fixtures/secrets/canary-values.env` | Sửa / Tạo | Bỏ `pytest.skip`, luôn chạy; có `.env` thì đối chiếu giá trị thật, không có thì đối chiếu canary committed | M-6 — cổng chỉ chạy ở máy tác giả thì không phải cổng |
| `.github/workflows/security-scan.yml` | Sửa | `quality-gates` checkout `submodules: recursive` | Hai test skip vì thiếu submodule; dependency phải có, chứ không phải test phải chấp nhận vắng mặt |
| `reports/week-06/artifacts/eval/score-run-approved.txt` | Sửa | Xoá trailing whitespace | L-1 |

**`git diff --stat`:**

```text
 .github/workflows/security-scan.yml                |   8 +-
 Makefile                                           |   6 +-
 .../docker/gateway/templates/default.conf.template | 104 ++++++--
 .../week-06/artifacts/eval/score-run-approved.txt  |   4 +-
 scripts/scan-opengrep.sh                           |   8 +-
 src/project_sentinel/analysis/pipeline.py          | 296 +++++++++++++++------
 src/project_sentinel/analysis/validators.py        |  30 ++-
 src/project_sentinel/orchestrator/report.py        |  61 ++++-
 src/project_sentinel/orchestrator/run_lock.py      |  98 +++++++
 src/project_sentinel/orchestrator/runner.py        | 116 +++++---
 src/project_sentinel/orchestrator/state.py         |   4 +-
 tests/fixtures/secrets/canary-values.env           |   9 +
 .../integration/test_gateway_policy_enforcement.py | 121 ++++++++-
 tests/test_evidence_pack_has_no_secrets.py         |  36 ++-
 .../analysis/test_pipeline_counts_what_happened.py | 171 ++++++++++++
 tests/unit/analysis/test_provenance_is_exact.py    |  65 +++++
 .../test_gateway_config_matches_registry.py        | 171 ++++++++++++
 tests/unit/orchestrator/test_report_disposition.py |  56 ++++
 tests/unit/orchestrator/test_resume_is_not_racy.py | 206 ++++++++++++++
 .../unit/orchestrator/test_steps_scan_normalize.py |  20 ++
 20 files changed, 1436 insertions(+), 154 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** với H-1, không cố "kiểm body cho đúng" mà **loại bỏ body của
caller khỏi đường đi**: Gateway tự dựng lại body chính tắc từ tên template. Với
H-2, đưa toàn bộ *nạp → kiểm → chiếm* vào một khoá liên tiến trình, và ghi dấu
vết chiếm xuống đĩa **trước** mọi network I/O.

**Luồng dữ liệu (H-1):** `client body` → *bỏ đi* → `$http_x_sentinel_template` →
`$sentinel_canonical_body` → `proxy_set_body` → `WebGoat`.

**Các quyết định kỹ thuật:**

- **Ba cơ chế thay vì một.** Kiểm `Content-Length` một mình *không đủ*:
  `{"evil": "x"}` dài đúng 13 byte như `{"value": ""}`. `proxy_set_body` mới là
  cái đóng biến thể đó. Kiểm độ dài vẫn giữ lại vì nó cho caller một **403 rõ
  ràng** thay vì im lặng viết lại body.
- **Chunked bị chặn riêng.** Không có `Content-Length` thì map độ dài không có
  gì để so — đó là một đường vòng, nên `Transfer-Encoding` bị từ chối thẳng.
- **`proxy_pass_request_headers off` là allowlist thật.** Xoá vài header cụ thể
  (Cookie, Authorization, X-Forwarded-\*) là **blocklist**: header lạ vẫn đi qua.
  Comment cũ nói "chỉ hai header được forward" là sai với mặc định Nginx.
- **`flock` chứ không phải `threading.Lock`.** CLI và tiến trình nền của web là
  hai *tiến trình*. `flock` gắn với open file description nên đúng cả giữa hai
  tiến trình lẫn hai luồng, và OS tự nhả khi tiến trình chết.
- **Không chờ khoá (`LOCK_NB`).** Chờ là sai cho UI: một cú double-click sẽ giữ
  một request treo tới khi probe xong. Người gọi thứ hai cần biết ngay.
- **Khoá + khoá chiếm bền, không chỉ khoá.** `flock` nhả khi tiến trình kết
  thúc, nên lần resume *sau đó* vẫn phải bị chặn — đó là việc của
  `probe-claim.json` và của chuyển trạng thái sang `PROBING` ghi dưới khoá.
- **Idempotency key buộc vào `decision.json`, không chỉ `run_id`.** Một quyết
  định khác là một lượt kiểm chứng khác và phải được nhìn thấy là khác.

**Xử lý lỗi / trường hợp biên:** không đọc được allowlist → lần chạy vẫn tiếp
tục (propose và Gateway còn chặn) nhưng tự khai `PARTIAL` kèm `degraded_reasons`;
objective sai → đặt `null` và đếm, không vứt cả record; `probe-claim.json` hỏng
→ coi như chưa có khoá chiếm.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Module | `run_lock` | `src/project_sentinel/orchestrator/run_lock.py` | Khoá liên tiến trình + khoá chiếm bền trên đĩa |
| Hàm | `run_lock` | `run_lock(root: Path) -> Iterator[bool]` | Context manager, không chờ; `False` nghĩa là bận |
| Hàm | `idempotency_key` | `idempotency_key(run_id, root) -> str` | `run_id` + sha256 nội dung `decision.json` |
| Hàm | `_allowed_endpoints_hint` | `pipeline._allowed_endpoints_hint(allowlist)` | Liệt kê đúng các tổ hợp đã duyệt cho feedback retry |
| Config | 3 `map` Nginx | `default.conf.template` | method↔template, độ dài body, body chính tắc |
| Số liệu | `unresolved_groups`, `invalid_responses_observed`, `unsafe_responses_observed`, `valid_objective_count`, `objective_validity_rate`, `allowlist_loaded`, `degraded_reasons` | `analysis-summary.json` | Tách "còn hỏng" khỏi "đã từng hỏng" |
| Artifact | `probe-claim.json` | `<run>/probe-claim.json` | Khoá chiếm một lượt phase hai |

**Cách chạy:**

```bash
make gateway-live-test        # 8 live + 15 policy, qua Nginx thật
python3 -m pytest tests/unit/orchestrator/test_resume_is_not_racy.py -q
make quality
```

**Output thật (đã che secret):**

```text
$ make gateway-live-test
============================== 23 passed in 0.54s ==============================

$ curl -X POST .../WebGoat/attack -H 'X-Sentinel-Template: tmpl_attack_post_empty' \
       --data-raw '{"unreviewed":"benign-canary"}'
403                       # trước khi sửa: 302 (tới được WebGoat)

$ bash scripts/demo-week4.sh
Tổng kết — 14 pass / 0 fail
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Gateway **dựng lại** body chính tắc, thay vì cố kiểm body của
caller có khớp template không.

**Lý do:** mentor nêu ba phương án — "exact empty body, exact/hashed canonical
body, hoặc endpoint nội bộ nhận template ID rồi tự materialize body". Phương án
materialize là phương án duy nhất mà Nginx thi hành được **không cần Lua**, và
là phương án duy nhất đúng với body cùng độ dài nhưng khác nội dung.
`.agents/security.md` đặt Gateway làm lớp enforce độc lập với Python; một lớp
chỉ *kiểm* thì còn phụ thuộc vào việc kiểm có đầy đủ không, còn một lớp *tự
dựng* thì không có gì để bỏ sót.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Chỉ kiểm `Content-Length` khớp body chính tắc | Đơn giản, trả 403 rõ ràng | `{"evil": "x"}` dài đúng 13 byte như `{"value": ""}` — không đóng được biến thể cùng độ dài |
| So sánh hash body bằng `njs`/Lua trong Nginx | Kiểm đúng từng byte, vẫn trả 403 | Thêm một runtime script vào biên giới an ninh để làm việc mà `proxy_set_body` làm được bằng một dòng config |
| Ký template ID bằng HMAC ở tầng Python | Header không còn giả được | Vẫn không nói gì về **body**; đó mới là thứ tới được WebGoat |
| Sinh config Nginx từ Python lúc build | Không bao giờ lệch | Thêm một bước build; test đối chiếu đạt cùng mục tiêu với ít cơ chế hơn |
| Khoá chờ (`flock` blocking) cho H-2 | Không mất request nào | Double-click sẽ giữ một request HTTP treo tới khi probe xong |

**Đánh đổi đã chấp nhận:**

1. Ba `map` Nginx là bản chép tay của registry Python. Đổi lấy: một test đối
   chiếu (`test_gateway_config_matches_registry.py`) làm đỏ ngay khi lệch.
2. Body cùng độ dài nhưng khác nội dung **không** bị trả 403 — nó bị *viết lại*.
   WebGoat không có endpoint nào phản chiếu body nên không khẳng định được từ
   ngoài; bằng chứng byte-level nằm ở test đối chiếu config.
3. Provenance hai chiều **sẽ làm tăng** `invalid_responses_observed` trên các
   lần chạy thật, vì bỏ sót một location nay cũng là lỗi. Đó là contract mà
   system prompt đã tuyên bố.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest -m "not llm and not live_gateway" -q` | 0 | 750 passed, 33 deselected |
| `make quality` | 0 | ruff + mypy (72 files) + coverage 81,09% (ngưỡng 78%) + pip-audit sạch |
| `make gateway-live-test` | 0 | 23 passed (8 live + 15 policy) |
| `make guardrails-test` | 0 | 140 passed |
| `make exercise-test` | 0 | 25 passed |
| `bash scripts/demo-week4.sh` | 0 | 14 pass / 0 fail |
| `bandit -q -r src/project_sentinel eval -ll` | 0 | sạch |
| `git archive HEAD` → pytest | 0 | 748 passed, **0 failed**, 2 skipped |

**Test mới thêm:**

- `test_gateway_config_matches_registry.py` (8 test) — ba map Nginx khớp từng
  byte với registry Python; mọi location kiểm đủ ba policy map; Accept/User-Agent
  đặt cứng nằm trong `allowed_request_headers`.
- `test_gateway_policy_enforcement.py::test_a_reviewed_template_does_not_licence_an_unreviewed_body`
  — đúng request mentor dùng để chứng minh bypass.
- `test_resume_is_not_racy.py` (6 test) — hai luồng đồng thời probe đúng một lần;
  khoá chiếm ghi trước network I/O; resume lần hai sau khi lần một xong không
  probe lại.
- `test_pipeline_counts_what_happened.py` (10 test) — token cộng mọi lần gọi;
  `None` không thành `0`; objective sai không làm mất record; feedback nêu đúng
  endpoint hợp lệ; allowlist hỏng báo lý do.
- `test_provenance_is_exact.py` (+3) — đúng hai ca mentor đưa ra.

**[CHỨNG MINH] Test có bắt được lỗi thật:**

```text
resume_run bản CŨ  -> concurrent_resume_probe_calls = 2
resume_run bản MỚI -> concurrent_resume_probe_calls = 1
```

**Bất biến đã giữ:** không mock/stub trong mã production · không lộ secret (canary
check trong demo xanh) · chỉ Gateway bind cổng loopback · không đụng nội dung
`reports/week-XX/` (chỉ xoá trailing whitespace theo L-1) · không stage thay đổi
của người dùng tại `artifacts/normalized/findings.json`.

**Còn fail / chưa chạy được:**

- `make llm-test` **chưa chạy lại** sau các thay đổi này.
- **Chưa có lần chạy LLM thật mới**, nên H-3 (tỷ lệ objective dùng được) chưa có
  số liệu sau khi sửa feedback. Cơ chế đo đã có; con số thì chưa.
- Snapshot `git archive` còn **2 skip** vì `git archive` không thể chứa
  submodule. Trên `git clone --recurse-submodules` (cách mentor clone) và trên
  CI (nay `submodules: recursive`) hai test đó **có chạy**.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `infra/docker/gateway/templates/default.conf.template`
  — `proxy_pass_request_headers off` bỏ **toàn bộ** header của caller. Hôm nay
  WebGoat không cần header nào ngoài Host/Accept/User-Agent (đã xác nhận: demo
  14/14, health 200, login 200), nhưng thêm một endpoint cần header khác sẽ phải
  khai báo tường minh ở đây.
- **Giả định đã đặt:** `map` của Nginx nhận được complex value
  (`"$a:$b"`) làm nguồn. Đã xác nhận chạy thật trên nginx 1.27.5-alpine; nếu đổi
  bản Nginx thì phải chạy lại `make gateway-live-test` trước khi tin.
- **Việc còn nợ:** H-3 cần một lần chạy LLM thật không dùng operator override;
  `make llm-test`; và các mục P1 còn lại từ vòng trước (atomic artifact writes,
  per-class F1, provenance token/model theo từng attempt).
- **Câu hỏi cho người dùng:** M-7 (quyền tái phân phối `eval/ground-truth/recall/`)
  và M-8 (push/PR/CI/merge) vẫn chờ quyết định — không phải việc code.
