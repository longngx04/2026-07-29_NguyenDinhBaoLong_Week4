# Worklog — Task 2: Tài liệu target WebGoat (deliverable W1)

**Ngày:** 2026-08-17 · **Agent/Model:** opencode · deepseek-v4-flash-free ·
**Branch:** `feat/w1-w4-task1-compose-invariants` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 2

---

## 1. Tóm tắt

- Đã viết `docs/target-webgoat.md` — deliverable W1 đang thiếu: kiến trúc ứng dụng, endpoint chính trong allowlist, và bảng cảnh báo OpenGrep với số liệu thật.
- Phục vụ người đọc/giám khảo hiểu topology và phạm vi target an toàn trước khi chạy pipeline.
- Kết quả: 3 test mới `test_target_doc.py` pass (đỏ→xanh), tổng `tests/unit/infra` 11/11 xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Ghi lại contract của target WebGoat — kiến trúc mạng, endpoint được allowlist, và bức tranh cảnh báo SAST hiện tại.
- **Nằm ở đâu trong luồng:** Tài liệu tham chiếu cho tuần 1 (deliverable W1); test nằm cạnh các test infra khác, khoá tài liệu không lệch khỏi allowlist thật.
- **Không có nó thì hỏng gì:** Deliverable W1 thiếu theo plan; tài liệu có thể mô tả endpoint không tồn tại trong `configs/gateway/endpoint-allowlist.json` (hallucination).
- **Ngoài phạm vi (cố ý không làm):** Không viết chi tiết từng bài học WebGoat; không mô tả cách khai thác; không thay đổi allowlist.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `docs/target-webgoat.md` | Tạo | 5 mục: cảnh báo bảo mật, Kiến trúc, Endpoint chính (2 endpoint allowlist), Cảnh báo đã phát hiện (3 rule, 23 finding), Cách chạy lại | Deliverable W1 theo plan Task 2 |
| `tests/unit/infra/test_target_doc.py` | Tạo | 3 test: doc tồn tại, đủ 3 heading bắt buộc, mọi path trong allowlist có mặt trong doc | Khoá tài liệu không lệch allowlist |
| `README.md` | Sửa | Thêm dòng "Tài liệu target: docs/target-webgoat.md" ngay dưới `## Pipeline Overview` | Plan Step 6 yêu cầu link |

**`git diff --stat`:**

```text
 README.md                        |   1 +
 docs/target-webgoat.md           |  Untracked (mới, 52 dòng)
 tests/unit/infra/test_target_doc.py | Untracked (mới, 26 dòng)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** TDD — viết test đỏ trước (doc chưa tồn tại), thu số liệu thật từ `artifacts/raw/opengrep.json`, rồi viết doc theo đúng khung plan, cuối cùng xanh.

**Luồng dữ liệu:** `configs/gateway/endpoint-allowlist.json` (2 endpoint: `ep_health`/`ep_attack`) → test đọc file này, đối chiếu từng `path` xuất hiện trong doc. Số liệu cảnh báo lấy từ `artifacts/raw/opengrep.json` (23 findings) do `make scan` sinh.

**Các quyết định kỹ thuật:**

- Số liệu trong bảng "Cảnh báo đã phát hiện" lấy ĐÚNG từ lệnh `jq` (Step 3) — không bịa, không làm tròn.
- Doc khai báo "không bao giờ mở ra host/Internet" khớp security.md và compose invariant (WebGoat không có `ports`).
- Giới hạn 65.536 byte và header `Accept`/`User-Agent` chép thẳng từ allowlist (max_response_bytes, allowed_request_headers).

**Xử lý lỗi / trường hợp biên:** Test `test_doc_lists_every_allowlisted_path` sẽ đỏ nếu ai đó thêm endpoint vào allowlist mà quên cập nhật doc — bắt hallucination ngược chiều (allowlist → doc).

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Doc | `docs/target-webgoat.md` | — | Deliverable W1: kiến trúc, endpoint, cảnh báo |
| Test | `test_target_doc.py` | `test_doc_exists` / `test_doc_covers_required_sections` / `test_doc_lists_every_allowlisted_path` | Khoá doc không lệch allowlist |
| README | `README.md` | link `docs/target-webgoat.md` | Điều hướng |

**Cách chạy:**

```bash
python3 -m pytest tests/unit/infra/test_target_doc.py -v
```

**Output thật:**

```text
$ python3 -m pytest tests/unit/infra -v
tests/unit/infra/test_target_doc.py::test_doc_exists PASSED
tests/unit/infra/test_target_doc.py::test_doc_covers_required_sections PASSED
tests/unit/infra/test_target_doc.py::test_doc_lists_every_allowlisted_path PASSED
============================== 11 passed in 0.05s ===============================
```

Số liệu Step 3 (đầu vào cho doc):

```text
$ jq '.results | length' artifacts/raw/opengrep.json
23
$ jq -r '.results[].check_id' artifacts/raw/opengrep.json | sort | uniq -c | sort -rn
20 configs.opengrep.java-sql-statement-execution
 2 configs.opengrep.java-unsafe-deserialization
 1 configs.opengrep.java-command-execution
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Doc theo khung plan Task 2 nguyên văn (cảnh báo bảo mật, Kiến trúc, Endpoint chính, Cảnh báo đã phát hiện, Cách chạy lại), số liệu thật từ quét.

**Lý do:** Plan chỉ định khung và yêu cầu "không bịa số — dùng đúng đầu ra". Nguồn sự thật endpoint là allowlist thật, không phải trí nhớ hay CWE.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Liệt kê mọi endpoint "có thể có" của WebGoat | Chi tiết hơn | Vi phạm "no hallucinated evidence" — doc phải khớp allowlist, không liệt kê đường dẫn ngoài allowlist |
| Không thêm test, chỉ viết doc | Nhanh | Plan yêu cầu test khoá; thiếu test thì doc dễ lệch allowlist sau này |

**Đánh đổi đã chấp nhận:** Doc mô tả giới hạn (response 65.536 byte, header cố định) lấy từ allowlist — chính xác cho 2 endpoint hiện tại, nhưng sẽ lệch nếu allowlist đổi mà không cập nhật (test sẽ bắt điều đó qua path, chưa bắt qua các trường khác).

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `python3 -m pytest tests/unit/infra/test_target_doc.py -v` (trước sửa) | 1 | 3 failed — doc chưa tồn tại (TDD đỏ) |
| `python3 -m pytest tests/unit/infra/test_target_doc.py -v` (sau sửa) | 0 | 3 passed |
| `python3 -m pytest tests/unit/infra -v` | 0 | **11 passed** |
| `python3 -m compileall -q src/project_sentinel` | 0 | — |

**Test mới thêm:**

- `tests/unit/infra/test_target_doc.py::test_doc_exists` — file deliverable tồn tại.
- `tests/unit/infra/test_target_doc.py::test_doc_covers_required_sections` — đủ 3 heading bắt buộc.
- `tests/unit/infra/test_target_doc.py::test_doc_lists_every_allowlisted_path` — mọi `path` trong allowlist đều xuất hiện trong doc.

**Bất biến đã giữ:** no mock/stub · test không skip · không lộ secret · không đụng `reports/week-XX/` · không tự commit.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Số liệu 23 findings / 3 rule lấy từ `artifacts/raw/opengrep.json` hiện tại — nếu ai chạy `make scan` mới, con số có thể đổi; doc ghi "Tổng số finding: 23" theo thời điểm quét, không tự cập nhật.
- **Giả định đã đặt:** Submodule WebGoat đã được checkout (doc nhắc `benchmarks/targets/webgoat/`); README không có mục `## Pipeline Overview` trùng tên khác.
- **Việc còn nợ:** Chưa chạy `make target-up` + curl 401 để minh hoạ "Cách chạy lại" (cần `.env` có key) — nhưng đã kiểm chứng 401/200 ở Task 1 vòng review.
- **Câu hỏi cho người dùng:** Bạn có muốn commit Task 2 ngay, hay gộp thêm task sau rồi commit chung?