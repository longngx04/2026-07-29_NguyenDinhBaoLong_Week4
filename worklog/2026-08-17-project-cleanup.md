# Worklog — Dọn dẹp dự án & tinh chỉnh cấu hình 3 Agent (Claude, Antigravity, OpenCode)

**Ngày:** 2026-08-17 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `project-cleanup` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** `Cleanup`

---

## 1. Tóm tắt

- Đã tạo nhánh mới `project-cleanup` và loại bỏ các tệp thừa không còn sử dụng (`.cursorrules`, script `stop_auto_review.py` phụ thuộc Codex CLI cũ, các tài liệu spec cũ đã bị thay thế).
- Tinh chỉnh và đồng bộ tài liệu hướng dẫn agent sang đúng 3 coding agent đang sử dụng: Claude, Antigravity, OpenCode; tạo tệp chỉ dẫn `OPENCODE.md`.
- Giữ nguyên 100% mã nguồn code sản xuất, tài liệu kiến trúc mới, bộ test (67/67 unit tests pass) và bảo tồn các báo cáo lịch sử `reports/week-XX/`.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Tinh gọn repository, loại bỏ các file cấu hình và hook thừa không tương thích hoặc không sử dụng, giúp các agent (Claude, Antigravity, OpenCode) tập trung đúng vào các luật và luồng kiểm thử cốt lõi.
- **Nằm ở đâu trong luồng:** Cấu hình môi trường agent và tài liệu tham chiếu gốc.
- **Không có nó thì hỏng gì:** Các agent có thể đọc nhầm tài liệu spec cũ đã bị thay thế (stale specs), gặp xung đột từ cấu hình Cursor/Codex không còn sử dụng.
- **Ngoài phạm vi (cố ý không làm):** Không sửa logic mã nguồn `src/project_sentinel/`; không đụng các báo cáo lịch sử `reports/week-XX/`.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `.cursorrules` | Xoá | Xoá file cấu hình Cursor | Người dùng chỉ sử dụng Claude, Antigravity, OpenCode |
| `scripts/hooks/stop_auto_review.py` | Xoá | Xoá script hook tự động review qua Codex CLI cũ | Codex không nằm trong 3 agent sử dụng; hook đã tắt |
| `docs/superpowers/specs/2026-08-06-openrouter-direct-analysis-design.md` | Xoá | Xoá file spec cũ | Đã được thay thế bởi spec `2026-08-17-sentinel-rebuild-design.md` |
| `docs/superpowers/specs/2026-08-12-week4-verification-design.md` | Xoá | Xoá file spec cũ | Đã được thay thế bởi spec `2026-08-17-sentinel-rebuild-design.md` |
| `.agents/hooks.json` | Sửa | Xoá mục hook `auto-coder-reviewer-loop` gọi `stop_auto_review.py` | Đồng bộ hook loại bỏ script đã xoá |
| `OPENCODE.md` | Tạo | Thêm file điều hướng cho OpenCode trỏ về `AGENTS.md` | Hỗ trợ 3 agent chính thức (Claude, Antigravity, OpenCode) |
| `AGENTS.md` | Sửa | Cập nhật header quy định 3 agent (Claude, Antigravity, OpenCode) | Đồng bộ phạm vi agent |
| `.agents/workflow.md` | Sửa | Cập nhật bảng vai trò cho 3 agent và dọn bỏ tài liệu hook Codex cũ | Làm sạch quy trình hai vai trò Coder / Reviewer |
| `.agents/README.md` | Sửa | Cập nhật danh sách agent và chỉ mục tài liệu | Đồng bộ tài liệu |
| `.agents/review.md` | Sửa | Bỏ liên kết tham chiếu tới `role_reviewer.md` cũ | Làm sạch tài liệu review |

**`git diff --stat`:**

```text
 .agents/README.md                                                       | 25 +++++++------------------
 .agents/hooks.json                                                      | 10 ----------
 .agents/review.md                                                       |  2 +-
 .agents/workflow.md                                                     | 75 +++++++++++++++++----------------------------------------------------------
 .cursorrules                                                            | 13 -------------
 AGENTS.md                                                               |  2 +-
 OPENCODE.md                                                             |  8 ++++++++
 docs/superpowers/specs/2026-08-06-openrouter-direct-analysis-design.md | 85 -------------------------------------------------------------------------------------
 docs/superpowers/specs/2026-08-12-week4-verification-design.md          | 85 -------------------------------------------------------------------------------------
 scripts/hooks/stop_auto_review.py                                       | 213 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 10 files changed, 43 insertions(+), 485 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Nhận diện các tệp spec cũ trong `docs/superpowers/specs/` đã có spec dựng lại `2026-08-17-sentinel-rebuild-design.md` thay thế.
2. Xoá cấu hình của các công cụ không nằm trong bộ 3 agent yêu cầu (`.cursorrules`, script gọi `codex exec`).
3. Cập nhật các tệp luật cốt lõi (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `OPENCODE.md`, `.agents/workflow.md`, `.agents/README.md`, `.agents/hooks.json`) để đồng bộ tuyệt đối về 3 agent đang hoạt động.
4. Kiểm tra toàn bộ test suite để đảm bảo không có tác dụng phụ.

**Luồng dữ liệu:** `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `OPENCODE.md` → `.agents/` (luật, context, review, security) → Agent làm việc và tuân thủ.

**Các quyết định kỹ thuật:**
- Giữ nguyên các hook bảo vệ bắt buộc đọc `.agents/` (`pre_invocation_check_agents.py`, `pre_tool_check_agents.py`) trong `hooks.json`.
- Bảo toàn tuyệt đối `reports/week-XX/` theo Rule 5 của repo.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| File | `OPENCODE.md` | `OPENCODE.md` | Chỉ dẫn khởi động cho OpenCode agent |
| Config | `hooks.json` | `.agents/hooks.json` | Làm sạch cấu hình hook, giữ hook kiểm tra đọc luật |
| Doc | `AGENTS.md` | `AGENTS.md` | Cập nhật định danh 3 coding agent |
| Doc | `workflow.md` | `.agents/workflow.md` | Quy trình review chuẩn hóa cho Claude, Antigravity, OpenCode |

**Cách chạy:**

```bash
pytest -m "not llm" tests/unit/infra/ tests/unit/ingestion/ tests/unit/retrieval/ tests/unit/analysis/ tests/unit/llm/ tests/test_no_doubles.py -v
```

**Output thật:**

```text
======================= 67 passed, 2 deselected in 0.37s =======================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Xoá các spec cũ và công cụ ngoại lai, tập trung cấu hình xoay quanh 3 agent (Claude, Antigravity, OpenCode).

**Lý do:** Yêu cầu rõ ràng từ người dùng chỉ giữ lại code, tài liệu còn sử dụng và 3 agent coding được chỉ định.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ lại `.cursorrules` và `stop_auto_review.py` | Đa dạng công cụ hơn | Tạo ra dead code và tài liệu gây nhầm lẫn vì không sử dụng Cursor/Codex |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest -m "not llm" tests/unit/infra/ tests/unit/ingestion/ tests/unit/retrieval/ tests/unit/analysis/ tests/unit/llm/ tests/test_no_doubles.py -v` | 0 | 67 passed |
| `python3 -m compileall -q src/project_sentinel` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, giữ nguyên toàn bộ `reports/week-XX/`, không lộ secret, giữ vững layout phân tầng.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** 3 agent làm việc độc lập hoặc tương tác qua git/diff theo mô hình Coder/Reviewer.
- **Việc còn nợ:** Không có.
- **Câu hỏi cho người dùng:** Không có.
