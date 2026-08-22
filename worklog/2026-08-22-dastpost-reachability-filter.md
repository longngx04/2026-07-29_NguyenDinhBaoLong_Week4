# Worklog — Siết điều kiện reachability chỉ nhận HTTP status 2xx

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-post-reachability.md`](../docs/superpowers/plans/2026-08-22-dast-post-reachability.md) · **Task ID:** `Task 5`

> Điền đủ 8 mục. Mục nào không có nội dung thì ghi `Không có` — không được xoá mục.
> Mọi số liệu phải là kết quả chạy thật. Che secret bằng `***`.

---

## 1. Tóm tắt

Task này siết chặt điều kiện trích xuất endpoint từ access log của API Gateway trong `parse_gateway_access_log` để chỉ các request có mã phản hồi HTTP 2xx mới được ghi nhận là reachable. Thay đổi này phục vụ module phân tích tĩnh-động (`correlation`), bảo đảm các request bị redirect (302) hoặc từ chối không bị tính nhầm là đã chạm tới endpoint ứng dụng. Kết quả là 18 unit tests trong `tests/unit/analysis/test_correlation.py` và toàn bộ 945 tests non-LLM/non-live của bộ test suite đều pass với 0 lỗi linter/typecheck.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Chuẩn hóa logic kiểm tra reachability ở tầng phân tích tương quan (`analysis/correlation.py`), chuyển tiêu chí từ "không phải lỗi `>= 400`" sang "thành công thực sự `200 <= status < 300`".
- **Nằm ở đâu trong luồng:** Nằm ở hàm `parse_gateway_access_log`, phân tích log của Nginx DAST Gateway (`artifacts/dast/gateway-access.log`) trước khi hàm `correlate` ghép nối với các finding SAST (OpenGrep).
- **Không có nó thì hỏng gì:** Các request nhận status 302 (chẳng hạn bị redirect về `/WebGoat/login` khi chưa authenticated hoặc sai session) sẽ bị tính sai là đã chạm tới endpoint đích (`reachable`), dẫn đến phóng đại độ phủ reachability sai lệch so với thực tế.
- **Ngoài phạm vi (cố ý không làm):** Không can thiệp vào parser SAST, không thay đổi schema của `runtime_evidence`, không sửa các rule correlation khác (`_route_matches`, `extract_route`).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/unit/analysis/test_correlation.py` | Sửa | Thêm 3 unit test: `test_a_redirect_is_not_reachable` (302 không được tính), `test_a_2xx_post_is_reachable` (POST 200 được tính), `test_a_204_is_reachable` (204 được tính) | Thực hiện TDD và khoá hành vi lọc status |
| `src/project_sentinel/analysis/correlation.py` | Sửa | Thay `if status >= 400: continue` thành `if not 200 <= status < 300: continue` trong `parse_gateway_access_log` | Siết điều kiện reachability chỉ chấp nhận dải HTTP 2xx |

**`git diff --stat`:**

```text
 src/project_sentinel/analysis/correlation.py |  6 ++++-
 tests/unit/analysis/test_correlation.py      | 40 ++++++++++++++++++++++++++++
 2 files changed, 45 insertions(+), 1 deletion(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Áp dụng phương pháp TDD (Test-Driven Development). Đầu tiên viết 3 test kiểm tra các trường hợp status 302, 200 và 204. Chạy test để thấy test 302 thất bại (RED). Sau đó sửa một dòng điều kiện lọc trong `parse_gateway_access_log` để loại bỏ tất cả status nằm ngoài `[200, 300)` và đưa test về trạng thái thành công (GREEN).

**Luồng dữ liệu:** `gateway-access.log` → đọc từng dòng qua regex `_LOG_LINE` → trích xuất `status = int(match.group("status"))` → kiểm tra `not 200 <= status < 300` để bỏ qua nếu không thuộc 2xx → gom nhóm `(method, path)` và query parameters → trả về dict `{"endpoints": [...]}`.

**Các quyết định kỹ thuật:**

- Dùng khoảng `200 <= status < 300` thay vì chỉ so sánh `status == 200` để hỗ trợ đầy đủ các mã thành công chuẩn HTTP như 201 Created, 204 No Content.
- Không coi 3xx là reachable vì trong môi trường Gateway + WebGoat, 302 thường là redirect về trang đăng nhập hoặc trang lỗi, chưa thực sự thực thi logic của lesson.

**Xử lý lỗi / trường hợp biên:** Các dòng log không đúng format regex hoặc file không tồn tại được xử lý graceful như cũ (trả về `{"endpoints": []}`). Dòng có status 3xx, 4xx, 5xx, 1xx đều bị bỏ qua một cách an toàn.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `parse_gateway_access_log` | `(path: str \| Path) -> dict[str, Any]` | Siết chặt bộ lọc: chỉ trích xuất các endpoint có mã HTTP 2xx |
| Test | `test_a_redirect_is_not_reachable` | `(tmp_path)` | Xác minh status 302 trả về `endpoints == []` |
| Test | `test_a_2xx_post_is_reachable` | `(tmp_path)` | Xác minh status 200 trả về đúng endpoint và method POST |
| Test | `test_a_204_is_reachable` | `(tmp_path)` | Xác minh toàn bộ dải 2xx (status 204) được tính là reachable |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v
```

**Output thật (đã che secret):**

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/longngx04/VinSOC/project_sentinel_main/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
plugins: respx-0.23.1, xdist-3.8.0, anyio-4.14.2, cov-7.1.0
collecting ... collected 18 items

tests/unit/analysis/test_correlation.py::test_parses_method_path_and_query_from_a_real_log PASSED [  5%]
tests/unit/analysis/test_correlation.py::test_non_dast_lines_are_ignored PASSED [ 11%]
tests/unit/analysis/test_correlation.py::test_blocked_requests_are_not_counted_as_reachable PASSED [ 16%]
tests/unit/analysis/test_correlation.py::test_a_missing_log_is_an_empty_map_not_a_crash PASSED [ 22%]
tests/unit/analysis/test_correlation.py::test_the_real_fixture_log_parses PASSED [ 27%]
tests/unit/analysis/test_correlation.py::test_a_redirect_is_not_reachable PASSED [ 33%]
tests/unit/analysis/test_correlation.py::test_a_2xx_post_is_reachable PASSED [ 38%]
tests/unit/analysis/test_correlation.py::test_a_204_is_reachable PASSED  [ 44%]
tests/unit/analysis/test_correlation.py::test_class_mapping_is_prefixed_to_method_mapping PASSED [ 50%]
tests/unit/analysis/test_correlation.py::test_a_file_without_mapping_returns_none PASSED [ 55%]
tests/unit/analysis/test_correlation.py::test_a_missing_file_returns_none_rather_than_raising PASSED [ 61%]
tests/unit/analysis/test_correlation.py::test_route_reached_by_zap_is_reachable PASSED [ 66%]
tests/unit/analysis/test_correlation.py::test_route_zap_never_reached PASSED [ 72%]
tests/unit/analysis/test_correlation.py::test_no_route_when_the_file_declares_none PASSED [ 77%]
tests/unit/analysis/test_correlation.py::test_a_zap_alert_on_the_same_route_upgrades_to_alerted PASSED [ 83%]
tests/unit/analysis/test_correlation.py::test_zap_findings_get_no_runtime_evidence_block PASSED [ 88%]
tests/unit/analysis/test_correlation.py::test_the_input_list_is_not_mutated PASSED [ 94%]
tests/unit/analysis/test_correlation.py::test_strengths_are_ordered_weakest_first PASSED [100%]

============================== 18 passed in 0.14s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Kiểm tra điều kiện `if not 200 <= status < 300: continue`.

**Lý do:** Kế hoạch `docs/superpowers/plans/2026-08-22-dast-post-reachability.md` (Task 5) chỉ định rõ ràng:
> *"CHI 2xx moi la cham toi duoc. Truoc day dieu kien la `>= 400`, nen mot 302 ve /login — tuc la KHONG cham toi duoc — van duoc tinh la reachable. Do la dem sai theo huong lac quan, kieu sai te nhat cho mot cong cu do do phu."*

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Chỉ chấp nhận `status == 200` | Rất chặt chẽ | Loại bỏ các status 201, 204 hợp lệ vốn cũng là kết quả thực thi thành công của endpoint |
| Giữ nguyên `status < 400` nhưng loại trừ riêng `status == 302` | Ít thay đổi code | Không bao quát hết các redirect khác (301, 303, 307, 308) hoặc các status 1xx |

**Đánh đổi đã chấp nhận:** Các endpoint có thể cố ý trả về 3xx như một response hợp lệ sẽ không được coi là reachable trừ khi ZAP đi theo redirect và nhận được 2xx tại đích. Đây là đánh đổi cần thiết để đảm bảo tính xác thực của evidence.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v` | 0 | 18 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 945 passed, 38 deselected, 1 warning |
| `make lint && make typecheck` | 0 | Ruff: All checks passed; Mypy: Success (78 source files) |
| `python3 -m compileall -q src/project_sentinel` | 0 | Compile thành công, không có lỗi cú pháp |

**Test mới thêm:**

- `tests/unit/analysis/test_correlation.py::test_a_redirect_is_not_reachable` — Xác nhận log chứa status 302 không được thêm vào danh sách endpoint reachable.
- `tests/unit/analysis/test_correlation.py::test_a_2xx_post_is_reachable` — Xác nhận log chứa status 200 với method POST được trích xuất chính xác.
- `tests/unit/analysis/test_correlation.py::test_a_204_is_reachable` — Xác nhận log chứa status 204 được tính là reachable.

**Bất biến đã giữ:** Không sử dụng mock/stub; không sửa các weekly report lịch sử; không thay đổi contract của `correlate`; tuân thủ phân lớp và type checking.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có (thay đổi rất tinh gọn và đã được bao phủ chặt chẽ bởi 3 unit test mới).
- **Giả định đã đặt:** Giả định các log của gateway luôn ghi status code dạng số nguyên ở trường `status=`.
- **Việc còn nợ:** Tiếp tục Task 6 của plan (sửa test live và cập nhật tài liệu).
- **Câu hỏi cho người dùng:** Không có.
