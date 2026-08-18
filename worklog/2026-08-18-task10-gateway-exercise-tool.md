# Worklog — Task 10: Bài tập W4 — Python tool và tài liệu bài tập

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/gateway-exercise-tool` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 10

---

## 1. Tóm tắt

- Xây dựng Python client tool `exercises/week4-gateway/tool.py` cho bài tập Week 4 gửi request an toàn qua Gateway với header `X-API-Key`, hỗ trợ phương thức GET/POST, giới hạn kích thước response preview tối đa 512 ký tự, và xử lý an toàn các lỗi kết nối/timeout mà không làm sập chương trình.
- Viết 7 bài kiểm thử unit/integration trong `exercises/week4-gateway/tests/test_tool.py` kèm fixture session khởi động target app và gateway thật trên nền `uvicorn.Server` đa luồng, đảm bảo kiểm thử end-to-end không dùng mock/stub.
- Biên soạn tài liệu `exercises/week4-gateway/README.md` mô tả kiến trúc cô lập, bảng allowlist, hướng dẫn chạy Docker Compose và 8 ca kiểm chứng. Toàn bộ 25/25 bài kiểm thử của bài tập Week 4 đạt trạng thái xanh (100% passed).

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp công cụ client Python chuẩn mực (`tool.py`) và tài liệu hướng dẫn (`README.md`) đóng gói hoàn chỉnh bài tập thực hành Week 4 về cơ chế kiểm soát truy cập qua API Gateway.
- **Nằm ở đâu trong luồng:** 
  - Đóng vai trò là client tương tác trực tiếp với Gateway (:9000).
  - Minh hoạ cách một agent/operator gửi request kiểm thử bảo mật có kiểm soát (bounded execution, auto API key injection, response truncation).
- **Không có nó thì hỏng gì:** Người dùng/học viên không có công cụ client mẫu và tài liệu chuẩn để thực hiện bài tập Week 4.
- **Ngoài phạm vi (cố ý không làm):** `tool.py` là công cụ độc lập cho bài tập Week 4, cố ý không import bất kỳ module nào từ `src/project_sentinel/` hay can thiệp vào pipeline chính.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `exercises/week4-gateway/tool.py` | Tạo mới | Triển khai client tool với `send(...)`, dataclass `Result`, `SAFE_PAYLOADS`, xử lý timeout/URLError/HTTPError | Deliverable chính của Task 10 |
| `exercises/week4-gateway/tests/test_tool.py` | Tạo mới | 7 test cases kiểm thử status 200, chặn 403, gửi POST body, xử lý connection error, timeout và giới hạn preview | Bộ kiểm thử tự động cho Python tool |
| `exercises/week4-gateway/README.md` | Tạo mới | Tài liệu bài tập: sơ đồ kiến trúc, bảng allowlist, cách chạy demo và bảng ca chứng minh | Hướng dẫn sử dụng bài tập Week 4 |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành Task 10 Step 1 → 7 | Cập nhật tiến độ kế hoạch tổng thể |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md |  14 +--
 exercises/week4-gateway/README.md                         |  68 ++++++++++++
 exercises/week4-gateway/tests/test_tool.py                | 104 +++++++++++++++++++
 exercises/week4-gateway/tool.py                           |  93 +++++++++++++++++
 4 files changed, 272 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Khởi tạo `exercises/week4-gateway/tests/test_tool.py` với 7 test cases kiểm thử các khía cạnh an toàn và kết quả trả về của tool.
2. Viết fixture `gateway_process` bên trong `test_tool.py` sử dụng `uvicorn.Server` trong background daemon threads để khởi động cả `target-app` (:8000) và `gateway` (:9000) khi kiểm thử chạy.
3. Chạy `pytest` xác nhận thất bại `ModuleNotFoundError: No module named 'tool'` (TDD Red).
4. Viết `exercises/week4-gateway/tool.py`:
   - `Result`: frozen dataclass chứa `status_code: int | None`, `body_preview: str`, `elapsed_ms: float`, `error: str | None`.
   - `SAFE_PAYLOADS`: định nghĩa các giá trị thử an toàn (`long_string`, `special_chars`, `empty_value`, `wrong_type`).
   - `send(method, path, *, body=None, headers=None, timeout=5.0) -> Result`: tự động tiêm `X-API-Key` từ biến môi trường `EXERCISE_API_KEY`, serialize JSON body, đọc tối đa 512 ký tự response preview, bắt trọn vẹn `HTTPError`, `URLError`, `TimeoutError` và đo thời gian thực thi `elapsed_ms`.
   - Khối `__main__` demo gửi request tới 5 endpoints (`/health`, `/items`, `/echo`, `/admin`, `/debug`).
5. Chạy kiểm thử qua Docker Compose live stack và chạy `make exercise-test` xác nhận toàn bộ 25/25 test cases thành công (TDD Green).
6. Viết `exercises/week4-gateway/README.md`.

---

## 5. Output là gì

**Thành phần mới:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Module | `tool.py` | `exercises/week4-gateway/tool.py` | Python client tool gửi request qua gateway |
| Dataclass | `Result` | `Result(status_code, body_preview, elapsed_ms, error)` | Cấu trúc dữ liệu kết quả thực thi |
| Hàm | `send` | `send(method: str, path: str, *, body=None, headers=None, timeout=5.0) -> Result` | Hàm gửi request kiểm thử có giới hạn |
| Test suite | `test_tool.py` | `exercises/week4-gateway/tests/test_tool.py` | 7 test cases cho Python tool |
| Tài liệu | `README.md` | `exercises/week4-gateway/README.md` | Hướng dẫn sử dụng bài tập Week 4 |

**Cách chạy:**

```bash
# 1. Chạy toàn bộ test bài tập
make exercise-test

# 2. Chạy tool demo với Docker Compose
cd exercises/week4-gateway
export EXERCISE_API_KEY="$(openssl rand -hex 16)"
docker compose -f compose.yml up --build --detach
sleep 5
python tool.py
docker compose -f compose.yml down
```

**Output thật (`make exercise-test`):**

```text
$ make exercise-test
exercises/week4-gateway/tests/test_app.py::test_health_returns_ok PASSED [  4%]
exercises/week4-gateway/tests/test_app.py::test_items_returns_list PASSED [  8%]
exercises/week4-gateway/tests/test_app.py::test_item_by_id_returns_one_item PASSED [ 12%]
exercises/week4-gateway/tests/test_app.py::test_unknown_item_returns_404 PASSED [ 16%]
exercises/week4-gateway/tests/test_app.py::test_echo_returns_body_back PASSED [ 20%]
exercises/week4-gateway/tests/test_app.py::test_admin_exists_but_is_not_protected_by_the_app_itself PASSED [ 24%]
exercises/week4-gateway/tests/test_app.py::test_debug_exists_but_is_not_protected_by_the_app_itself PASSED [ 28%]
exercises/week4-gateway/tests/test_app.py::test_echo_query_returns_query_params PASSED [ 32%]
exercises/week4-gateway/tests/test_gateway.py::test_allowlisted_endpoint_with_valid_key_reaches_upstream PASSED [ 36%]
exercises/week4-gateway/tests/test_gateway.py::test_missing_api_key_returns_401 PASSED [ 40%]
exercises/week4-gateway/tests/test_gateway.py::test_wrong_api_key_returns_401 PASSED [ 44%]
exercises/week4-gateway/tests/test_gateway.py::test_endpoint_outside_allowlist_returns_403 PASSED [ 48%]
exercises/week4-gateway/tests/test_gateway.py::test_debug_endpoint_outside_allowlist_returns_403 PASSED [ 52%]
exercises/week4-gateway/tests/test_gateway.py::test_method_not_in_allowlist_returns_403 PASSED [ 56%]
exercises/week4-gateway/tests/test_gateway.py::test_allowlisted_post_reaches_upstream PASSED [ 60%]
exercises/week4-gateway/tests/test_gateway.py::test_exceeding_rate_limit_returns_429 PASSED [ 64%]
exercises/week4-gateway/tests/test_gateway.py::test_api_key_never_appears_in_the_request_log PASSED [ 68%]
exercises/week4-gateway/tests/test_gateway.py::test_query_string_is_forwarded_to_upstream PASSED [ 72%]
exercises/week4-gateway/tests/test_tool.py::test_result_carries_status_and_bounded_preview PASSED [ 76%]
exercises/week4-gateway/tests/test_tool.py::test_send_sets_the_api_key_header_and_returns_status PASSED [ 80%]
exercises/week4-gateway/tests/test_tool.py::test_send_reports_403_for_endpoint_outside_allowlist PASSED [ 84%]
exercises/week4-gateway/tests/test_tool.py::test_send_can_post_a_body PASSED [ 88%]
exercises/week4-gateway/tests/test_tool.py::test_send_handles_connection_error_without_raising PASSED [ 92%]
exercises/week4-gateway/tests/test_tool.py::test_send_handles_timeout_without_raising PASSED [ 96%]
exercises/week4-gateway/tests/test_tool.py::test_body_preview_is_bounded PASSED [100%]

======================== 25 passed, 1 warning in 1.65s =========================
```

**Output thật chạy Live `python tool.py` qua Docker Compose:**

```text
GET   /health    -> 200  
GET   /items     -> 200  
POST  /echo      -> 200  
GET   /admin     -> 403  
GET   /debug     -> 403  
```

---

## 6. Vì sao chọn cách implement này

- **Giao diện phi ngoại lệ (Exception-safe result envelope):** `send()` không bao giờ raise exception làm ngắt quãng luồng thực thi của agent/operator; thay vào đó, các lỗi mạng hoặc timeout đều được đóng gói chuẩn hoá vào trường `error: str | None` và `status_code: None`.
- **Giới hạn bộ nhớ và token (Bounded execution):** Cắt `MAX_PREVIEW_CHARS = 512` bảo vệ hệ thống khỏi việc nhận dữ liệu response khổng lồ gây tràn bộ nhớ hoặc vượt quá context window khi tích hợp với LLM.
- **Thư viện chuẩn (Standard library only):** Sử dụng `urllib.request` thay vì phụ thuộc bên ngoài trong `tool.py`, giúp client nhẹ và dễ dàng tích hợp vào bất kỳ môi trường Python nào.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `make exercise-test` | 0 | 25 passed (100%) |
| `python tool.py` (live compose stack) | 0 | `/health` 200, `/items` 200, `/echo` 200, `/admin` 403, `/debug` 403 |
| `python3 -m compileall -q exercises/week4-gateway` | 0 | PASSED |

**Chứng minh test `test_body_preview_is_bounded` bắt được lỗi (Proof of failure detection):**

1. Khi tạm đổi `MAX_PREVIEW_CHARS = 100000` trong `tool.py`:
```text
$ pytest exercises/week4-gateway/tests/test_tool.py::test_body_preview_is_bounded -q
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_body_preview_is_bounded _________________________
...
>       assert len(result.body_preview) == 512
E       assert 1049 == 512
1 failed in 0.78s
```
*(Test bắt lỗi chính xác vì body 1049 ký tự không bị cắt về 512)*

2. Khi trả `MAX_PREVIEW_CHARS = 512`:
```text
$ pytest exercises/week4-gateway/tests/test_tool.py::test_body_preview_is_bounded -q
.                                                                        [100%]
1 passed in 0.85s
```

**Bất biến đã giữ:** Không mock/stub trong test kiểm thử bài tập, response preview giới hạn đúng 512 ký tự, an toàn trước ngoại lệ mạng.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Gateway chạy trên `http://127.0.0.1:9000` (hoặc cấu hình qua `EXERCISE_GATEWAY_URL`).
- **Việc còn nợ:** Không có (đã hoàn tất trọn vẹn cả 10 task trong rebuild plan W1-W4).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 10 lên nhánh `feat/gateway-exercise-tool` ngay bây giờ không?
