# Worklog — Task 3: Nâng cấp toàn diện công cụ tìm kiếm tri thức (Knowledge Search)

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/w1-w4-task3-knowledge-search` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 3

---

## 1. Tóm tắt

- Đã nâng cấp công cụ `keyword_search.py` thành hệ thống tìm kiếm tri thức bảo mật toàn diện, hỗ trợ trích xuất token kỹ thuật (CWE, OWASP, camelCase, rule IDs), taxonomy mở rộng hai chiều cho toàn bộ 17+ lớp lỗ hổng, chấm điểm BM25/TF-IDF đa trường (Title 6x, Tags 5x, Headings 3x, Path tokens 4x, Body TF), phrase boost (+8.0 tới +10.0) và trích xuất snippet thông minh quanh từ khoá.
- Khắc phục triệt để false positive khi so khớp đường dẫn bằng token-level match (`path_tokens`), bảo tồn stream token nguyên bản trong `tokenize()` để tính term frequency (`body_token_list.count(token)`), và chuẩn hoá chuỗi cụm từ gốc cho phrase boost.
- Kết quả: 45/45 retrieval unit tests pass 100% (gồm 34 tests acceptance mới và 11 unit tests mở rộng), 94/94 toàn bộ offline test suite xanh sạch.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Nâng cấp năng lực truy vấn và xếp hạng tài liệu tri thức bảo mật trong `data/knowledge-base/` theo từ khoá, mã lỗ hổng CWE, danh mục OWASP Top 10, hoặc rule ID từ OpenGrep.
- **Nằm ở đâu trong luồng:** Nằm ở module `src/project_sentinel/retrieval/`, được gọi bởi `analysis/packet_builder.py` để bổ sung tri thức ngữ cảnh trước khi gửi sang LLM phân tích, và phục vụ CLI `make search Q='...'`.
- **Không có nó thì hỏng gì:** Nếu chỉ hỗ trợ cứng SQLi/XSS hoặc ranking kém, khi hệ thống gặp các lỗ hổng khác (Path Traversal, Deserialization, SSRF, XXE, CSRF, IDOR, Broken Auth, JWT...) LLM sẽ không nhận được tài liệu hướng dẫn tương ứng, dẫn tới phân tích thiếu chính xác hoặc hallucination.
- **Ngoài phạm vi (cố ý không làm):** Không tích hợp vector database hay embedding ngoại lai nhằm giữ hệ thống chạy nhanh, nhẹ, hoàn toàn offline và độc lập không cần GPU/API phụ thuộc bên ngoài.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/retrieval/keyword_search.py` | Sửa | Nâng cấp tokenizer (trả về full stream không deduplicate sớm), bổ sung ma trận synonyms/taxonomy hai chiều, tính điểm đa trường (Title, Tags, Headings, Path tokens, Body TF), raw query phrase boost (+8.0 tới +10.0) và trích xuất snippet ngữ cảnh tốt nhất | Nâng cấp lõi tìm kiếm toàn diện theo yêu cầu |
| `tests/unit/retrieval/test_search_acceptance.py` | Tạo mới | Viết 34 test cases: tiêu chí đề bài (SQLi, XSS), 20 lỗ hổng trong KB, 9 mã CWE, rule ID, anti-hallucination và CLI ranking | Khoá tiêu chí nghiệm thu và bao phủ toàn diện KB |
| `tests/unit/retrieval/test_keyword_search.py` | Sửa | Thêm unit tests cho tokenizer kỹ thuật, taxonomy expansion, snippet centering, category filter, non-match path substring, repeated body terms TF boost, và two-word phrase boost | Kiểm chứng các hàm thành phần và scoring edge-cases |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành các checkbox Step 1 → Step 4 của Task 3 | Cập nhật tiến độ kế hoạch |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md |   8 +-
 src/project_sentinel/retrieval/keyword_search.py         | 344 ++++++++++++++++++++++---
 tests/unit/retrieval/test_keyword_search.py              |  61 ++++-
 tests/unit/retrieval/test_search_acceptance.py          | 104 ++++++++
 4 files changed, 440 insertions(+), 77 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Mở rộng từ điển ánh xạ ngữ nghĩa `SYNONYMS` hai chiều (bidirectional) giữa các thuật ngữ viết tắt (SSRF, XXE, IDOR, CSRF, JWT, LFI, RCE...), mã định danh chuẩn (`CWE-89`, `CWE-502`, `CWE-22`, `CWE-918`, `CWE-78`, `CWE-611`, `CWE-352`, `CWE-347`...) và các từ khóa tiếng Anh tương ứng.
2. Thiết kế hàm `tokenize()` nhận diện các cụm token kỹ thuật và trả về full stream để tính TF chính xác: chuẩn hoá `cwe-89` ↔ `cwe89`, tách camelCase (`findAccountById`), tách namespace Java (`java.lang.Runtime`).
3. Chấm điểm theo mô hình BM25/TF-IDF đa trường:
   - `Title`: trọng số 6.0
   - `Tags`: trọng số 5.0
   - `Headings`: trọng số 3.0
   - `Path`: trọng số 4.0 khớp theo `path_tokens` (loại bỏ false positive dạng substring)
   - `Body`: trọng số 1.0 kèm giảm bậc tần suất `1.0 + ln(1 + min(tf, 20))`
   - Cụm từ chính xác (Phrase match từ `raw_query`): boost thêm +8.0 (body/headings) đến +10.0 (title).
4. Trích xuất `snippet_for()`: quét các đoạn văn, tính mật độ khớp từ khoá truy vấn và căn giữa cửa sổ snippet xung quanh từ khoá đầu tiên tìm thấy.

**Luồng dữ liệu:** `Query` → `tokenize()` → `expand_query_tokens()` → `load_docs()` → `score_doc()` → `snippet_for()` → `sort(score desc)` → Top-K `RetrievalHit`.

**Xử lý lỗi / trường hợp biên:**
- Truy vấn rỗng: trả về danh sách rỗng `[]` ngay lập tức.
- Thư mục không tồn tại: bắt lỗi an toàn và trả về `[]`.
- Truy vấn từ vô nghĩa (`zzzz khong ton tai`): không bịa tài liệu, trả về danh sách tài liệu hợp lệ trong KB nếu có điểm hoặc `[]`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| File | `test_search_acceptance.py` | `tests/unit/retrieval/test_search_acceptance.py` | 34 test cases bao phủ toàn bộ KB |
| Function | `tokenize` | `tokenize(text: str) -> list[str]` | Tách token kỹ thuật an ninh mạng, giữ full stream |
| Function | `expand_query_tokens` | `expand_query_tokens(tokens: list[str]) -> list[str]` | Mở rộng từ đồng nghĩa bảo mật hai chiều (deduplicated) |
| Function | `score_doc` | `score_doc(query_tokens, original_tokens, doc, raw_query) -> float` | Chấm điểm đa trường BM25 + phrase boost |
| Function | `snippet_for` | `snippet_for(query_tokens, body, width) -> str` | Trích xuất trích đoạn ngữ cảnh thông minh |
| Function | `search` | `search(query, knowledge_dir, limit, category) -> list` | API tìm kiếm chính |

**Cách chạy:**

```bash
pytest tests/unit/retrieval/ -v
make search Q='Path Traversal'
make search Q='CWE-502'
make search Q='SSRF'
```

**Output thật:**

```text
$ pytest tests/unit/retrieval/ -v
============================== 45 passed in 0.34s ==============================

$ make search Q='Path Traversal'
Query: 'Path Traversal' — 5 hit(s)

1. [64.7] Path Traversal
   path: data/knowledge-base/vulnerabilities/path-traversal.md
   tags: example, path-traversal, lfi, cwe-22
   snippet: Mitigation: resolve path rồi kiểm tra nằm trong base directory; reject ..; dùng ID thay vì tên file thô.

$ make search Q='CWE-502'
Query: 'CWE-502' — 5 hit(s)

1. [34.6] Insecure Deserialization
   path: data/knowledge-base/vulnerabilities/insecure-deserialization.md
   tags: example, deserialization, cwe-502, a08, java
   snippet: ObjectInputStream.readObject() trên dữ liệu attacker-controlled có thể dẫn tới RCE (gadget chains). OpenGrep rule java-unsafe-deserialization gắn CWE-502 / OWASP A08.
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Pure Python BM25/TF-IDF đa trường với taxonomy mở rộng có sẵn, regex tokenization, precomputed path tokens và raw query phrase matching.

**Lý do:** Đảm bảo tốc độ thực thi cực nhanh (0.34s cho 45 tests), zero-dependency mới, hoạt động độc lập 100% offline, và đáp ứng chính xác mọi loại lỗ hổng trong knowledge base.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Dùng thư viện Vector DB / Embedding ngoài (như Chroma, sentence-transformers) | Hiểu ngữ nghĩa tốt hơn | Thêm dependency nặng, đòi hỏi tài nguyên tính toán cao và mạng để tải weights, vi phạm nguyên tắc tối giản và độc lập của pipeline |
| Chỉ giữ lại danh sách từ khoá cứng cho SQLi và XSS | Rất đơn giản | Không đáp ứng yêu cầu tìm kiếm toàn diện và hỗ trợ các lỗ hổng khác của dự án |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest tests/unit/retrieval/ -v` | 0 | 45 passed (100%) |
| `pytest tests/unit/retrieval tests/unit/infra tests/unit/ingestion tests/unit/analysis tests/test_no_doubles.py -v` | 0 | 94 passed (100%) |
| `python3 -m compileall -q src/project_sentinel` | 0 | PASSED |
| `make search Q='SQL Injection'` | 0 | Trả về tài liệu `sql-injection-concat.md` và `sql-injection-login.md` |
| `make search Q='Path Traversal'` | 0 | Trả về tài liệu `path-traversal.md` |
| `make search Q='SSRF'` | 0 | Trả về tài liệu `ssrf.md` |

**Bất biến đã giữ:** Không mock/stub, test không skip, không lộ secret, giữ nguyên historical reports `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Trọng số các trường (Title: 6, Tags: 5, Headings: 3, Path: 4, Body: 1) — hiện tại cho kết quả ranking rất tốt trên toàn bộ 20 tài liệu trong KB.
- **Giả định đã đặt:** Các tài liệu Markdown trong `data/knowledge-base/` duy trì định dạng Frontmatter chuẩn (`title:`, `tags:`).
- **Việc còn nợ:** Không có.
- **Câu hỏi cho người dùng:** Bạn có muốn commit Task 3 lên nhánh `feat/w1-w4-task3-knowledge-search` ngay bây giờ không?
