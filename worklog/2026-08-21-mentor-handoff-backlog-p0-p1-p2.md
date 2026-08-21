# Worklog — Backlog bàn giao mentor (P0 + P1 + P2)

**Ngày:** 2026-08-21 · **Agent/Model:** Claude Code · Opus 5 ·
**Branch:** `feat/handoff-hardening` · **Plan:** review mentor local · **Task ID:** `P0+P1+P2`

---

## 1. Tóm tắt

Thực hiện toàn bộ backlog P0/P1/P2 trong bản review của mentor trước khi bắt tay làm UI.
Điểm khác biệt lớn nhất so với việc làm theo lời: **mỗi claim trong review được kiểm chứng
trước khi implement**. Một claim (Task C — raw response chạm đĩa) hoá ra **sai**, và chính
việc kiểm chứng nó phơi ra hai lỗi thật khác mà review không thấy. Suite offline 457 → 582
test; over-claim rate trên finding thật giảm từ **100 % xuống 25–33 %**.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** đưa project từ trạng thái "chạy được" sang trạng thái
  "bàn giao được": số liệu đúng, kết luận không vượt quá bằng chứng, và có tài liệu để
  người khác chạy lại.
- **Nằm ở đâu trong luồng:** cắt ngang — chạm analysis, orchestrator, probe, guardrails,
  CLI, CI và toàn bộ tài liệu.
- **Không có nó thì hỏng gì:** báo cáo nộp mentor công bố số liệu sai (`retry_count`,
  `0 false positive`), trình bày false positive như lỗ hổng `high`, và người clone repo
  không có bằng chứng nào vì `artifacts/runs/` bị Git ignore.
- **Ngoài phạm vi (cố ý không làm):** UI (P3) — theo đúng thứ tự review đề xuất.

---

## 3. Đã làm gì

Bảy commit, mỗi commit một chủ đề. Chi tiết trong message của từng commit.

| Commit | Nội dung |
|---|---|
| `f1cfef4` | Task C — bằng chứng redaction đúng số liệu, che trước khi cắt preview |
| `f9ad400` | Task E + F — `disposition`/hiệu chỉnh, và `supports`/`refutes`/`inconclusive` |
| `984dc44` | Task D — ground truth 23 finding WebGoat + nới cửa sổ bằng chứng |
| `c643774` | P2 — ruff, mypy, coverage, dep-audit, bandit làm gate chặn |
| `b1a772f` | P2 — tách `steps.py` (722 dòng) và `cli.py` (380 dòng) |
| `5964678` | Task A — sửa sai sót thực tế, evidence pack, sửa đường phê duyệt |
| `bfdd267` | Task B — bốn deliverable tài liệu + README |

**`git diff --stat` (toàn nhánh so với `main`):**

```text
110 files changed, 7229 insertions(+), 1098 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** với mỗi mục trong backlog — kiểm chứng claim → viết test bắt lỗi →
sửa → chạy lại. Không implement theo mô tả mà chưa thấy lỗi bằng mắt.

**Ba lỗi tìm ra nhờ cách làm đó, review không nêu:**

1. **Bằng chứng redaction bị sai.** Task C nói raw response chạm đĩa. Test canary chứng
   minh **không**: `_write_json_artifact` đã redact từ trước. Nhưng chạy đúng chuỗi
   `step_probe → step_scrub` thật thì `scrubbed.json` báo `password: 1` (khớp lại chính
   placeholder `[REDACTED_PASSWORD]`) và **bỏ sót** email, token, api_key thật. Test scrub
   cũ tự tay ghi `probe-result.json` nên không bao giờ đi qua `step_probe`.

2. **`source_radius = 4` là nguyên nhân gốc của việc Agent thiếu tự tin.** Với bán kính 4
   dòng, cửa sổ bằng chứng không với tới annotation `@PostMapping`/`@RequestParam` của
   **bất kỳ** true positive nào (0/13). Agent viết "không có bằng chứng trực tiếp cho thấy
   tham số query đến từ người dùng" cho chính ca mà **toàn bộ** câu truy vấn là tham số
   request — vì đường vào nằm cách sink 7 dòng, vừa lọt ra ngoài. Đo lại: r=20 → 10/13,
   r=28 → 12/13 rồi bão hoà.

3. **Đường phê duyệt của người vận hành bị hỏng.** Thử chạy đầu-cuối với người thật gõ
   `approve`: câu trả lời **luôn** bị mất, lần chạy kết thúc `REJECTED`. Bước scan chạy
   `subprocess.run` không chuyển hướng `stdin`, tiến trình con kế thừa và đọc hết. Mặc
   định fail-safe che mất lỗi — hệ thống vẫn an toàn nhưng đường phê duyệt không dùng
   được. Đây là lý do thật sự của dòng "chưa lần chạy nào có người thật bấm Approve".

**Quyết định kỹ thuật đáng nói:**

- **Hiệu chỉnh chỉ hạ, không bao giờ nâng.** Một luật sai chỉ làm mất độ nhạy, không bao
  giờ tự tạo ra một `confirmed` giả.
- **Chấm theo cách trình bày, không theo sự tồn tại của field.** Bản chạy cũ không có
  `disposition` mà vẫn gán `high` cho mọi thứ phải bị tính là over-claim, chứ không được
  báo "0 %" vì thiếu dữ liệu.
- **Bỏ nhánh dự phòng prompt trong `OpenRouterClient`.** Nó trả về chuỗi 68 ký tự khi
  thiếu file luật — chính sự cố ghi trong báo cáo Tuần 6.
- **Bộ luật ruff chọn theo "bắt lỗi thật", không theo "định dạng lại code".** `E501`
  (296 vi phạm) cố ý không bật để tránh một diff định dạng khổng lồ che mất lịch sử.

---

## 5. Output là gì

| Loại | Tên | Mô tả |
|---|---|---|
| Module | `analysis/calibration.py` | Hiệu chỉnh kết luận Agent theo bằng chứng, xác định phía Python |
| Module | `orchestrator/verdict.py` | `supports` / `refutes` / `inconclusive` |
| Package | `orchestrator/steps/` | 722 dòng → 5 module, lớn nhất 247 |
| Package | `commands/` | 7 lệnh con, `cli.py` còn 125 dòng |
| Dữ liệu | `eval/ground-truth/webgoat-findings.json` | 23 nhãn đặt theo đường đi dữ liệu |
| Công cụ | `eval/score_ground_truth.py` | Tách scanner precision khỏi Agent triage precision |
| Tài liệu | `docs/{architecture,product-brief,limitations,demo-script}.md` | Bốn deliverable bắt buộc |
| Bằng chứng | `reports/week-06/artifacts/` | Hai lần chạy đã lọc + kết quả chấm |

**Số liệu thật, đo trên cùng 23 cảnh báo WebGoat:**

| Lần chạy | Thay đổi | Triage precision | Over-claim | attacker_control |
|---|---|---:|---:|---:|
| `20260821T045519Z` | mốc nền | 0 % | **100 %** | — |
| A | + disposition + hiệu chỉnh | 36,4 % | 16,7 % | 45,5 % |
| B | + cửa sổ 4 → 28 dòng | 66,7 % | 33,3 % | 81,0 % |
| C | + luật chấm đúng dòng | 75,0 % | 25,0 % | 90,0 % |
| `20260821T083837Z` | đầu-cuối cuối cùng | 56,5 % | 33,3 % | 82,6 % |

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** kiểm chứng từng claim của review trước khi sửa; ưu tiên sửa **nguyên
nhân gốc** thay vì triệu chứng.

**Lý do:** review là output của một LLM judge, không phải chân lý. Một claim của nó sai
(Task C), và ba lỗi thật lại không nằm trong danh sách. Nếu implement theo lời, kết quả
sẽ là một bản vá cho lỗi không tồn tại, còn ba lỗi thật vẫn nguyên.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Implement thẳng Task C theo mô tả | Nhanh, "xong việc" | Sửa một lỗi không tồn tại; hai lỗi thật vẫn còn |
| Ép Agent trả lời tốt hơn bằng prompt | Không đụng code | Nguyên nhân gốc là bằng chứng bị cắt cụt, không phải prompt |
| Loại record mâu thuẫn thay vì hạ mức | Đơn giản | Mất record; hiện đã mất 1–2/21 mỗi lần chạy |
| Bật toàn bộ bộ luật ruff | Sạch hơn | 637 vi phạm → diff định dạng khổng lồ che mất thay đổi thật |

**Đánh đổi đã chấp nhận:**

- Cửa sổ bằng chứng rộng hơn tốn thêm ~8 k token mỗi lần chạy, và tạo một failure mode
  mới: hai sink cạnh nhau bị gộp kết luận (`opengrep-014`, `016`). Đã thêm luật prompt
  giảm bớt nhưng chưa hết.
- Regex redaction nay chạy trên toàn bộ body (tối đa 64 KiB) thay vì 512 byte. Chậm hơn
  không đáng kể, đổi lại không mảnh bí mật nào lọt qua mốc cắt.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả thật |
|---|---:|---|
| `pytest -m "not llm and not live_gateway" -q` | 0 | `582 passed, 18 deselected` (trước: 457) |
| `make gateway-live-test` | 0 | `8 passed` — Gateway + WebGoat thật |
| `make guardrails-test` | 0 | `120 passed` |
| `make exercise-test` | 0 | `25 passed` |
| `make lint` (ruff) | 0 | `All checks passed!` |
| `make typecheck` (mypy) | 0 | `no issues found in 70 source files` |
| `make coverage` | 0 | `80.72 %` (ngưỡng 78 %) |
| `make dep-audit` | 0 | `No known vulnerabilities found` |
| `bandit -r src eval -ll` | 0 | 0 High, 0 Medium |
| CLI đầu-cuối, người duyệt | 0 | `decided_by: ["cli-operator"]`, `DONE` |
| CLI đầu-cuối, người từ chối | 0 | `requests_total: 0`, `REJECTED` |

**[CHỨNG MINH] revert → FAIL → restore → PASS** đã chạy thật cho Task C — chi tiết trong
[`2026-08-21-task-c-redaction-evidence-integrity.md`](2026-08-21-task-c-redaction-evidence-integrity.md).

**Bất biến đã giữ:** không mock/stub · không test nào skip · không lộ secret (có test
quét evidence pack mỗi lần chạy) · Gateway vẫn loopback, WebGoat vẫn không mở cổng host ·
không đụng `reports/week-01..05/` · không push, không đụng `main`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `analysis/calibration.py:_DENIAL_PATTERNS`. Đây là dò cụm từ
  trên văn xuôi tiếng Việt và tiếng Anh. Danh sách được giữ hẹp và chỉ hạ kết luận, nên
  khớp nhầm chỉ mất độ nhạy — nhưng nó vẫn là heuristic, không phải phân tích.
- **Điểm cần mentor quyết định:** bộ ground truth 23 nhãn do **một người** đặt, không có
  người thứ hai đối chiếu. Bốn ca `needs_review` (`opengrep-002`, `003`, `005`, `020`)
  tranh luận được nhất.
- **Giả định đã đặt:** UI không phải acceptance requirement (PDF không yêu cầu), nên để
  sau P0/P1/P2 theo đúng thứ tự review đề xuất.
- **Việc còn nợ:** over-claim rate chưa về 0 và **sẽ không về 0** nếu không có phân tích
  taint thật — đã ghi trong `docs/limitations.md` §1.3.
- **Câu hỏi cho người dùng:** một claim trong bản review của mentor (Task C — raw response
  chạm đĩa) đã được **bác bỏ bằng test**. Nên nói lại điều này với mentor kèm bằng chứng,
  thay vì im lặng bỏ qua.
