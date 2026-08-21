# Worklog — Task C: redaction trước khi chạm đĩa & tính toàn vẹn bằng chứng

**Ngày:** 2026-08-21 · **Agent/Model:** Claude Code · Opus 5 ·
**Branch:** `feat/handoff-hardening` · **Plan:** review mentor local (Task C, P0) · **Task ID:** `Task C`

---

## 1. Tóm tắt

Review mentor báo `step_probe` ghi `body_preview` **thô** vào `probe-result.json` trước khi
`step_scrub` chạy. Kiểm chứng bằng canary cho thấy **lỗi đó không tồn tại**:
`_write_json_artifact` đã gọi `redact_structure` từ trước. Nhưng khi chạy đúng chuỗi
`step_probe → step_scrub` thật, lộ ra một lỗi khác chưa ai bắt: **bằng chứng redaction bị sai**
— `scrubbed.json` báo `password: 1` (khớp lại chính placeholder của nó) và bỏ sót email, token,
api_key thật. Đã sửa hai lỗi gốc, thêm 6 test, suite offline 457 → 463 passed.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** giữ cho số liệu guardrail trong `scrubbed.json`, `events.jsonl`
  và mục "Sự kiện bảo mật" của báo cáo cuối phản ánh đúng redaction đã thật sự xảy ra.
- **Nằm ở đâu trong luồng:** cửa ra `send_probe` (bước 6) và bước `step_scrub` (bước 7).
- **Không có nó thì hỏng gì:** báo cáo nộp mentor khẳng định "0 redaction" cho một response
  thật sự chứa email/token/API key. Bằng chứng guardrail phản lại chính nó — tệ hơn là không có
  bằng chứng, vì nó tạo niềm tin sai.
- **Ngoài phạm vi (cố ý không làm):** không đổi tập mẫu regex, không đổi ngưỡng 512 byte,
  không đụng schema `probe-result.json` ngoài việc thêm trường `redactions`.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/guardrails/redaction.py` | Sửa | Thêm `(?!\[REDACTED_)` vào hai mẫu `password`; đổi `_merge` thành `merge_events` công khai | Mẫu password khớp lại placeholder của chính nó nên đếm sai; bước scrub cần cộng số liệu hai chặng |
| `src/project_sentinel/probe/tool.py` | Sửa | `_preview` → `_safe_preview`: che **toàn bộ** body rồi mới cắt 512 byte, trả kèm sự kiện; `ProbeOutcome` thêm `redactions` | Cắt trước khi che có thể xé đôi email/token đúng mốc 512 byte làm mẫu không khớp; và bằng chứng phải rời khỏi nơi redaction thật sự xảy ra |
| `src/project_sentinel/orchestrator/steps.py` | Sửa | `step_probe` ghi `redactions` vào `probe-result.json`; thêm `_upstream_redactions()`; `step_scrub` gộp số liệu hai chặng | Không mang số liệu qua thì scrub chỉ thấy chuỗi đã sạch và báo 0 |
| `tests/unit/guardrails/test_redaction.py` | Sửa | +2 test idempotence về **cả nội dung lẫn số liệu** | Chốt lỗi đếm sai |
| `tests/unit/orchestrator/test_probe_scrub_redaction_chain.py` | Tạo | +4 test chạy đúng chuỗi `step_approval → step_probe → step_scrub` với transport trả canary | Test scrub cũ tự tay ghi `probe-result.json` nên không bao giờ đi qua `step_probe` — đúng loại lỗ hổng mà báo cáo Tuần 6 tự nhận |

**`git diff --stat`:**

```text
 src/project_sentinel/guardrails/redaction.py | 15 ++++++++---
 src/project_sentinel/orchestrator/steps.py   | 40 ++++++++++++++++++++++++++--
 src/project_sentinel/probe/tool.py           | 24 ++++++++++++++---
 tests/unit/guardrails/test_redaction.py      | 31 +++++++++++++++++++++
 4 files changed, 100 insertions(+), 10 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** kiểm chứng claim của review trước, không implement theo lời. Viết test chạy
chuỗi thật thay vì dựng artifact bằng tay. Test đó vừa bác bỏ lỗi được báo, vừa phơi ra lỗi thật.

**Luồng dữ liệu:** `response.body thô` → `redact()` (cửa ra `send_probe`) → `cắt 512B` →
`ProbeOutcome(body_preview sạch, redactions)` → `probe-result.json` → `step_scrub` gộp số liệu →
`scrubbed.json` + `events.jsonl`.

**Các quyết định kỹ thuật:**

- **Che trước, cắt sau.** Thứ tự cũ (cắt rồi che) để lọt mảnh secret bị xé đôi ở mốc 512 byte.
- **Redaction xảy ra một lần, tại cửa ra.** `send_probe` là đường duy nhất request rời hệ thống,
  nên cũng là nơi duy nhất response đi vào. Che ở đó thì không caller nào quên được.
- **Bằng chứng đi kèm dữ liệu.** Vì che ở cửa ra, bước scrub nhận chuỗi đã sạch và không thể tự
  đếm. Số liệu phải được mang theo trong `probe-result.json`.
- **Không bắt lại placeholder.** `(?!\[REDACTED_)` sửa tận gốc thay vì lọc sự kiện ở đầu ra —
  mọi đường che hai lần đều hưởng lợi, không riêng đường probe.

**Xử lý lỗi / trường hợp biên:** `_upstream_redactions()` bỏ qua mọi phần tử hỏng (không phải
dict, thiếu `kind`, `count` âm hoặc là bool) thay vì ném lỗi — `probe-result.json` là file trên
đĩa mà tiến trình khác có thể sửa; thà báo thiếu số liệu còn hơn giết cả lần chạy ở bước 7.

---

## 5. Output là gì

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `merge_events` | `guardrails/redaction.py:merge_events(list[RedactionEvent]) -> list[RedactionEvent]` | Gộp sự kiện cùng loại, nay công khai |
| Hàm | `_safe_preview` | `probe/tool.py:_safe_preview(str) -> tuple[str, tuple[RedactionEvent, ...]]` | Che toàn bộ body rồi cắt, trả kèm bằng chứng |
| Trường | `ProbeOutcome.redactions` | `probe/tool.py` | Sự kiện redaction đo tại cửa ra |
| Hàm | `_upstream_redactions` | `orchestrator/steps.py` | Đọc lại số liệu từ `probe-result.json`, chịu lỗi |
| Test | 6 test mới | `tests/unit/guardrails/test_redaction.py`, `tests/unit/orchestrator/test_probe_scrub_redaction_chain.py` | Xem mục 7 |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_probe_scrub_redaction_chain.py -q
```

**Output thật:**

```text
....                                                                     [100%]
4 passed in 0.08s
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** che một lần tại cửa ra `send_probe`, mang bằng chứng theo artifact sang bước scrub.

**Lý do:** `.agents/security.md` §7 yêu cầu audit "hữu ích mà không lộ nội dung nhạy cảm".
Một dòng `redactions: []` cho response có PII vẫn không lộ gì, nhưng đã hết hữu ích — nó nói sai.
README cũng tuyên bố ba chokepoint; đặt redaction ở cửa ra giữ đúng mô hình đó thay vì thêm
chokepoint thứ tư.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ raw trong `ProbeOutcome`, để scrub tự che | Không cần đổi schema artifact | Trả lại đúng rủi ro review lo: một caller ngoài orchestrator ghi thẳng preview thô xuống đĩa |
| Lọc sự kiện trùng ở đầu ra `redact()` | Sửa nhanh | Che triệu chứng; mọi đường che hai lần khác vẫn đếm sai |
| Emit event redaction ngay trong `send_probe` | Bằng chứng đúng nơi phát sinh | Sinh hai dòng event cho một redaction vì `step_scrub` cũng emit; và `send_probe` dùng được ngoài orchestrator |

**Đánh đổi đã chấp nhận:** chạy regex trên toàn body (tối đa 64 KiB) thay vì trên 512 byte.
Chậm hơn không đáng kể, đổi lại không có mảnh secret nào lọt qua mốc cắt.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q` | 0 | `463 passed, 18 deselected` (trước: 457) |
| `make gateway-live-test` | 0 | `8 passed` — Gateway + WebGoat thật |
| `.venv/bin/python -m pytest tests/unit/guardrails/ -q` | 0 | `114 passed` |

**Test mới thêm:**

- `test_redacting_twice_does_not_invent_a_second_redaction` — che lần hai không sinh sự kiện mới.
- `test_no_pattern_re_matches_its_own_placeholder` — mọi loại idempotent về cả nội dung lẫn số liệu.
- `test_no_canary_reaches_any_file_of_the_run` — quét **mọi** file trong thư mục lần chạy, không
  canary nào chạm đĩa. Đây là test bác bỏ claim của review.
- `test_scrubbed_keeps_placeholders` — `safe_text` giữ `[REDACTED_*]`, không im lặng xoá sạch.
- `test_scrubbed_reports_that_redaction_happened` — `scrubbed.json` phải liệt kê email và token.
- `test_redaction_event_is_recorded` — `events.jsonl` có dòng `redaction`.

**[CHỨNG MINH] revert → FAIL → restore → PASS (đã chạy thật):**

```text
############ REVERT FIX 1 (bo negative lookahead) ############
FAILED test_redacting_twice_does_not_invent_a_second_redaction
FAILED test_no_pattern_re_matches_its_own_placeholder
2 failed, 28 passed

############ REVERT FIX 2 (scrub tu redact lai) ############
E       assert 'email' in {'password'}
FAILED test_scrubbed_reports_that_redaction_happened
1 failed, 3 passed

############ RESTORE -> PASS ############
34 passed in 0.10s
```

**Bất biến đã giữ:** không mock/stub (`CanaryTransport` là transport thật cắm vào tham số
`transport` có sẵn của `step_probe`, không phải test double thay thế production code) · không test
nào skip · không lộ secret · Gateway vẫn loopback · không đụng `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `probe/tool.py:_safe_preview` — nay chạy regex trên toàn bộ body
  thay vì 512 byte đầu. Với response sát trần 64 KiB, chi phí regex tăng theo kích thước.
- **Giả định đã đặt:** redaction dựa trên mẫu là đủ cho môi trường WebGoat. Sai nếu response
  chứa định dạng secret mà tập mẫu chưa biết — đây là giới hạn còn tồn tại, sẽ ghi vào
  `docs/limitations.md`.
- **Việc còn nợ:** claim sai trong review (raw response chạm đĩa) cần được nói lại với mentor
  kèm test bác bỏ, thay vì im lặng bỏ qua.
- **Câu hỏi cho người dùng:** Không có.
