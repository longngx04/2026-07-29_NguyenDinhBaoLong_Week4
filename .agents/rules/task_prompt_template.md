# Lời nhắc chuẩn cho Coding Agent (Task Prompt Template)

> Dành cho các agent model yếu (Gemini Flash, Haiku, GPT-mini, Cursor auto…).
> Model yếu hỏng ở ba chỗ: **code trước khi đọc**, **làm quá phạm vi**, **báo cáo mơ hồ**.
> File này chặn cả ba bằng 3 cổng bắt buộc (Gate) và một mẫu báo cáo cố định.

**Cách dùng:** copy nguyên khối `PROMPT` bên dưới, dán vào đầu mỗi task, thay `<TASK>` và
`<PLAN_FILE>`. Không rút gọn khối này — model càng yếu thì càng cần đủ chữ.

---

## 1. Khối prompt copy-paste

````text
=== LỜI NHẮC BẮT BUỘC — ĐỌC HẾT TRƯỚC KHI LÀM BẤT CỨ VIỆC GÌ ===

NHIỆM VỤ: <TASK>
KẾ HOẠCH: <PLAN_FILE>

Bạn phải đi qua 3 cổng theo đúng thứ tự. Không được nhảy cóc.
Không được viết/sửa một dòng code nào trước khi in xong BẰNG CHỨNG ĐỌC ở Gate 1.

---------- GATE 0 — XÁC NHẬN BRANCH TRƯỚC ĐÃ ----------

Tôi thường chạy hai task song song trên hai branch khác nhau. Một thư mục làm việc
chỉ đứng được trên MỘT branch, nên làm nhầm chỗ là file của task này nằm lại trên
branch của task kia.

Chạy và IN RA output thật:

  git branch --show-current
  git status --short
  git worktree list

Rồi đối chiếu:
  - Branch hiện tại KHÔNG đúng branch ghi trong task  ⇒ DỪNG, hỏi tôi.
    Không tự `git switch`, không tự tạo branch, không commit.
  - `git status` có file KHÔNG thuộc task của bạn     ⇒ đó là việc của task khác.
    Kệ nó. Không sửa, không xoá, không di chuyển, không commit kèm.

Cần một thư mục riêng thì dùng worktree (`.worktrees/` đã được gitignore):

  git worktree add .worktrees/<ten-task> -b feat/<ten-branch>     # branch mới
  git worktree add .worktrees/<ten-task> <branch-co-san>          # branch đã có

Chạy test bên trong worktree PHẢI thêm PYTHONPATH, vì venv cài editable trỏ cứng
về `src/` của thư mục gốc — thiếu nó là import nhầm bản copy khác:

  PYTHONPATH="$PWD/src" <duong-dan-repo-goc>/.venv/bin/python -m pytest tests/... -q

---------- GATE 1 — ĐỌC TRƯỚC, CODE SAU ----------

Đọc đầy đủ (đọc thật, không đoán, không đọc lướt):
  1. AGENTS.md
  2. .agents/README.md
  3. .agents/context.md
  4. .agents/workflow.md
  5. .agents/security.md
  6. .agents/rules/coding_agent_rules.md
  8. .agents/rules/git_commit_workflow.md
  9. <PLAN_FILE>  — đọc phần Global Constraints + đúng task được giao
 10. Mọi file mà task sẽ sửa (đọc trước khi sửa, không sửa file chưa đọc)

Sau khi đọc, IN RA khối này (bắt buộc, không được bỏ qua, không được bịa):

  ### READ-PROOF
  | File | Số dòng | Một ràng buộc tôi phải tuân theo từ file này |
  |---|---|---|
  | AGENTS.md | ... | ... |
  | ... | ... | ... |

  ### KẾ HOẠCH LÀM
  - Mục tiêu task (1 câu):
  - File sẽ tạo/sửa/xoá (liệt kê hết, kèm lý do từng file):
  - Test sẽ viết/chạy:
  - Rủi ro + cách quay lui:

Ràng buộc nào tôi chép sai hoặc bịa ra ⇒ coi như chưa đọc, phải đọc lại.

---------- GATE 2 — CODE TỪNG BƯỚC NHỎ ----------

- Làm ĐÚNG một task/một bước trong plan. Xong mới sang bước kế.
- Diff nhỏ nhất có thể. KHÔNG refactor tiện tay, KHÔNG format lại file không liên quan,
  KHÔNG đổi tên biến ngoài phạm vi.
- Bám theo quy ước của file đang sửa (typing, naming, pathlib, kiểu báo lỗi).
- Test viết theo TDD nếu plan yêu cầu: test đỏ trước, code sau, test xanh.

DỪNG LẠI VÀ HỎI NGƯỜI DÙNG (không tự quyết) khi:
  - Plan mâu thuẫn với code thực tế.
  - Task đòi sửa > 5 file mà plan không nói.
  - Phải thêm dependency mới.
  - Phải sửa file ngoài danh sách đã khai ở Gate 1.
  - Test fail mà nguyên nhân nằm ngoài phạm vi task.

TUYỆT ĐỐI CẤM:
  - Mock / Fake / Stub / Dummy / provider="fake" ở bất kỳ đâu.
  - Test `skip` khi thiếu Docker hoặc LLM key — phải FAIL kèm thông báo rõ nguyên nhân.
  - Commit hoặc push khi người dùng chưa duyệt.
  - `git add -A`, `git add .`, `git commit -a` — luôn liệt kê rõ từng đường dẫn,
    rồi đọc lại `git diff --cached --name-status` trước khi commit.
  - Đụng vào file của task khác đang nằm chung thư mục (sửa, xoá, di chuyển, commit kèm).
  - Sửa/xoá reports/week-01 … reports/week-04.
  - In secret, API key, .env ra log/stdout/báo cáo.
  - Nói "đã xong" khi chưa chạy lệnh kiểm chứng và dán output thật.

Chạy kiểm chứng trước khi sang Gate 3 (dán exit code thật, không phỏng đoán):
  git branch --show-current          # vẫn phải đúng branch của task
  git diff --cached --name-status    # mọi dòng phải là file bạn đã khai ở Gate 1
  python3 -m compileall -q src/project_sentinel
  pytest -m "not llm" -q tests
  <các lệnh make mà plan yêu cầu cho task này>

---------- GATE 3 — VIẾT BÁO CÁO WORKLOG ----------

Code xong KHÔNG được kết thúc lượt. Phải tạo đúng MỘT file báo cáo:

  worklog/<YYYY-MM-DD>-<task-slug>.md

Ví dụ: worklog/2026-08-17-task1-gop-compose.md

Nội dung copy đúng khung trong worklog/_TEMPLATE.md, điền đủ 8 mục:
  1. Tóm tắt        — 3 câu: làm gì, cho ai, kết quả.
  2. Chức năng      — task này phục vụ chức năng gì của hệ thống, thiếu nó thì hỏng cái gì.
  3. ĐÃ LÀM GÌ      — bảng file × loại thay đổi × mô tả, đủ mọi file trong diff.
  4. LÀM NHƯ THẾ NÀO— luồng dữ liệu/thuật toán, đầu vào → xử lý → đầu ra, ai gọi ai.
  5. OUTPUT         — output cụ thể: file sinh ra, API/hàm mới (kèm chữ ký), lệnh chạy,
                      và output THẬT dán từ terminal (đã che secret).
  6. VÌ SAO CHỌN CÁCH NÀY — nêu ≥1 phương án đã cân nhắc và loại bỏ, kèm lý do loại bỏ.
                      Nếu plan đã chỉ định cách làm thì trích dòng đó và nói vì sao nó hợp lý.
  7. KIỂM CHỨNG     — bảng lệnh | exit code | kết quả. Fail thì ghi fail, cấm giấu.
  8. CẦN NGƯỜI REVIEW KỸ — chỗ mình ít chắc chắn nhất, giả định đã đặt, việc còn nợ.

Quy tắc báo cáo:
  - Viết cho người CHƯA đọc code hiểu được. Không viết "đã cập nhật logic" chung chung.
  - Mọi con số, exit code, output đều là số thật đã chạy. Bịa số = hỏng cả báo cáo.
  - Không có gì để ghi ở một mục thì ghi "Không có" — không được xoá mục.

Kết thúc lượt bằng: đường dẫn file worklog + `git diff --stat` + trạng thái từng
tiêu chí nghiệm thu (pass / partial / fail).
=== HẾT LỜI NHẮC ===
````

---

## 2. Vì sao đặt ba cổng như vậy

| Gate | Lỗi của model yếu mà nó chặn |
|---|---|
| Gate 1 — READ-PROOF dạng bảng | Model hay "giả vờ đã đọc". Bắt trích một ràng buộc cụ thể/1 file khiến việc bịa khó hơn việc đọc thật. |
| Gate 1 — khai trước danh sách file | Chặn phình phạm vi. Sang Gate 2, mọi file ngoài danh sách là tín hiệu dừng. |
| Gate 2 — danh sách DỪNG LẠI VÀ HỎI | Model yếu tự ý "sửa cho chạy được" rồi phá bất biến. Liệt kê sẵn tình huống dừng thì nó không phải tự phán đoán. |
| Gate 2 — cấm dạng liệt kê tuyệt đối | Cấm chung chung ("hãy cẩn thận") vô tác dụng. Cấm nêu đích danh (`Fake*`, `skip`, `git commit`) thì kiểm tra được bằng grep. |
| Gate 3 — báo cáo theo khung cố định | Không có khung, model viết 5 dòng vô nghĩa. 8 mục cố định buộc nó phơi bày cả lý do thiết kế lẫn phần chưa chắc. |
| Gate 3 — mục 6 "phương án đã loại bỏ" | Đây là mục người review đọc đầu tiên: biết agent chọn có suy nghĩ hay chọn bừa. |
| Gate 3 — mục 8 "cần review kỹ" | Model yếu luôn tự tin quá mức. Bắt nêu chỗ yếu nhất giúp định hướng review đúng chỗ. |

---

## 3. Bảng chống nguỵ biện (dán kèm khi agent hay cãi)

Agent nghĩ điều bên trái ⇒ đó là dấu hiệu đang đi sai.

| Ý nghĩ | Thực tế |
|---|---|
| "Task nhỏ, khỏi đọc `.agents/`" | Task nhỏ vẫn phá được bất biến. Đọc trước. |
| "Tôi nhớ luật rồi" | Luật có thể vừa đổi. Đọc lại file. |
| "Sửa luôn cho gọn" | Ngoài phạm vi = diff khó review = bị trả về. |
| "Test này skip cho nhanh" | Repo cấm skip. Phải fail rõ nguyên nhân. |
| "Mock tạm để chạy được" | Repo không có test double. Dựng phụ thuộc thật. |
| "Commit luôn cho tiện" | Người dùng duyệt rồi mới commit. |
| "Chắc là chạy được" | Chưa chạy = chưa xong. Dán output thật. |
| "Báo cáo viết sau" | Không có worklog = task chưa hoàn thành. |
| "Plan sai nên tôi tự sửa" | Plan sai thì DỪNG và hỏi, không tự đổi thiết kế. |
| "`git add -A` cho nhanh" | Thư mục có thể đang chứa task khác. Liệt kê từng đường dẫn. |
| "Branch nào chẳng được, commit sau sửa" | Sai branch = file của bạn nằm lại trên nhánh người khác. Kiểm tra ở Gate 0. |
| "File lạ này chắc rác, xoá đi" | Đó là task song song đang làm dở. Không đụng vào. |

---

## 4. Bản rút gọn (task nhỏ, 1 file)

Dùng khi task thực sự nhỏ; vẫn giữ đủ ba cổng:

```text
Trước tiên: `git branch --show-current` + `git status --short`. Sai branch, hoặc thấy file
của task khác ⇒ DỪNG, hỏi tôi. Không tự switch, không đụng file không phải của mình.
Trước khi code: đọc AGENTS.md (nhất là mục 4 về làm song song nhiều branch) + toàn bộ
.agents/*.md + <PLAN_FILE> + file sẽ sửa.
In READ-PROOF (mỗi file 1 ràng buộc) và danh sách file sẽ sửa. Chưa in xong thì chưa được code.
Khi code: đúng một bước, diff nhỏ nhất, không mock/stub, test không được skip, không commit.
Khi stage: liệt kê từng đường dẫn, cấm `git add -A` / `git add .`.
Lệch plan hoặc phải đụng file ngoài danh sách ⇒ DỪNG, hỏi tôi.
Sau khi code: chạy `pytest -m "not llm" -q tests`, rồi tạo worklog/<ngày>-<task>.md theo
worklog/_TEMPLATE.md, đủ 8 mục (đã làm gì · làm thế nào · output thật · chức năng ·
vì sao chọn cách này · kiểm chứng · cần review kỹ). Trả lời kèm đường dẫn worklog + git diff --stat.
```

---

## 5. Người dùng nghiệm thu thế nào

Task chỉ được coi là xong khi đủ cả 5:

1. Có khối `READ-PROOF` ở đầu lượt, ràng buộc trích dẫn đúng file.
2. `git diff --stat` chỉ chứa các file đã khai ở Gate 1, và commit nằm đúng branch của task.
3. Có `worklog/<ngày>-<task-slug>.md` đủ 8 mục, không mục nào bỏ trống.
4. Output kiểm chứng trong worklog khớp với lệnh chạy lại được.
5. Không có file của task song song khác bị kéo vào diff hoặc bị xoá/di chuyển.

Thiếu bất kỳ mục nào ⇒ trả về agent kèm đúng một câu: *"Thiếu Gate N, làm lại phần đó."*
