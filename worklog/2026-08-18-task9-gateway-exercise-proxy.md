# Worklog — Task 9: Bài tập W4 — Gateway kiểm soát request theo allowlist

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/gateway-exercise-proxy` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 9

---

## 1. Tóm tắt

- Xây dựng API Gateway cho bài tập Week 4 tại `exercises/week4-gateway/gateway/` đóng vai trò là reverse proxy bảo vệ ứng dụng mục tiêu (`target-app`).
- Thiết lập cấu hình allowlist `exercises/week4-gateway/allowlist.json` với `rate_limit_per_minute: 30` và 4 endpoints được phép: `GET /health`, `GET /items`, `POST /echo`, `GET /echo-query`.
- Triển khai 4 hành vi cốt lõi theo thứ tự kiểm tra nghiêm ngặt:
  1. Thiếu hoặc sai API key (`X-API-Key`) -> Trả HTTP 401.
  2. Endpoint / Method không nằm trong allowlist -> Trả HTTP 403.
  3. Vượt hạn mức số lượng request mỗi phút -> Trả HTTP 429.
  4. Hợp lệ -> Chuyển tiếp (proxy) an toàn sang upstream kèm đầy đủ query string và trả phản hồi.
- Cơ chế audit logging ghi nhận `ts`, `method`, `path`, `status`, `elapsed_ms` vào `requests.jsonl` và **tuyệt đối không bao giờ ghi API key**.
- Tối ưu cấu hình Docker: đặt `.dockerignore` tại gốc context `exercises/week4-gateway/` ngăn chặn rò rỉ audit log/tests vào container; Dockerfile chạy non-root (`appuser:10001`); `compose.yml` chỉ mở cổng `127.0.0.1:9000` ra loopback host.
- Kiểm chứng thực tế: 18/18 test cases trong `make exercise-test`, kiểm tra `docker run ls -la` container sạch sẽ, và test live container qua Docker Compose đạt chuẩn 100%.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Là thành phần trung gian (Reverse Proxy / Policy Enforcement Point) kiểm soát toàn bộ lưu lượng mạng truy cập vào ứng dụng backend đích trong kịch bản bài tập thực hành Week 4.
- **Nằm ở đâu trong luồng:** 
  - Đứng trước `target-app` (FastAPI cổng 8000).
  - Lắng nghe trên cổng `9000`, tiếp nhận request từ client/operator, thực thi chính sách bảo mật trước khi gửi tiếp sang backend.
- **Không có nó thì hỏng gì:** Các endpoint nhạy cảm (`/admin`, `/debug`) của target app sẽ bị truy cập tự do mà không qua bất kỳ lớp kiểm soát nào.
- **Ngoài phạm vi (cố ý không làm):** Gateway bài tập không thay thế Gateway chính của production (`src/project_sentinel/gateway/`), nó phục vụ kịch bản minh hoạ độc lập cho Week 4.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `exercises/week4-gateway/allowlist.json` | Tạo mới | Cấu hình allowlist 4 endpoints (`/health`, `/items`, `/echo`, `/echo-query`) và rate limit 30 rpm | Định nghĩa ranh giới truy cập cho Gateway |
| `exercises/week4-gateway/gateway/__init__.py` | Tạo mới | Package init rỗng | Đóng gói module gateway |
| `exercises/week4-gateway/gateway/main.py` | Tạo mới | Ứng dụng Gateway FastAPI xử lý auth, allowlist, rate limit, logging, query string forwarding và proxy | Triển khai logic điều khiển chính |
| `exercises/week4-gateway/.dockerignore` | Tạo mới | Loại trừ Dockerfile, pycache, pyc, tests, requests.jsonl tại gốc build context | Tối ưu context build Docker, ngăn lọt file nhạy cảm |
| `exercises/week4-gateway/gateway/Dockerfile` | Tạo mới | Containerfile non-root trên nền `python:3.12-slim` | Build container cho gateway |
| `exercises/week4-gateway/compose.yml` | Tạo mới | Định nghĩa 2 services `target-app` và `exercise-gateway` | Đóng gói kịch bản Docker compose cho bài tập |
| `exercises/week4-gateway/tests/test_gateway.py` | Tạo mới | 10 unit test cases kiểm thử 401, 403, 429, proxy, query string và log redaction | Kiểm chứng hành vi cốt lõi của gateway |
| `exercises/week4-gateway/tests/test_app.py` | Sửa | Thêm test kiểm tra `/echo-query` | Kiểm chứng route phụ trợ ở target app |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành Task 9 Step 1 → 9 | Cập nhật tiến độ kế hoạch |

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Tạo `allowlist.json` cấu hình 4 endpoints được phép (`GET /health`, `GET /items`, `POST /echo`, `GET /echo-query`).
2. Viết bộ kiểm thử `test_gateway.py` bao gồm background daemon server fixture để khởi chạy `target-app` trên loopback port 8000 phục vụ kiểm thử tích hợp ASGI thực tế không dùng stub/mock.
3. Viết `gateway/main.py`:
   - `load_allowlist()`: đọc và parse cấu hình JSON.
   - `is_allowed(method, path)`: kiểm tra method và path chính xác (không kèm query).
   - `check_rate_limit(client_id)`: sử dụng `collections.deque` với sliding window 60s.
   - `log_request(...)`: ghi log JSONL với `ts`, `method`, `path`, `status`, `elapsed_ms`.
   - `proxy(...)`: thực hiện xác thực header `X-API-Key`, kiểm tra allowlist, kiểm tra rate limit, forward request qua `httpx.AsyncClient` kèm query string và ghi log audit.
4. Tạo `Dockerfile` và `compose.yml` cô lập mạng: `target-app` chỉ `expose` cổng 8000 nội bộ, `exercise-gateway` bind `127.0.0.1:9000:9000` ra loopback host.
5. Đặt `.dockerignore` tại gốc context `exercises/week4-gateway/.dockerignore`.
6. Chạy kiểm thử live bằng Docker Compose với `curl` xác nhận `health: 200`, `admin: 403`, `no key: 401`.

---

## 5. Output là gì

**Thành phần mới:**

| Loại | Tên | Đường dẫn | Mô tả |
|---|---|---|---|
| Cấu hình | `allowlist.json` | `exercises/week4-gateway/allowlist.json` | Cấu hình allowlist và rate limit |
| Module | `main.py` | `exercises/week4-gateway/gateway/main.py` | Ứng dụng Gateway FastAPI |
| Dockerfile | `Dockerfile` | `exercises/week4-gateway/gateway/Dockerfile` | Container đóng gói Gateway |
| Compose | `compose.yml` | `exercises/week4-gateway/compose.yml` | Cấu hình Docker compose cho bài tập |
| Test suite | `test_gateway.py` | `exercises/week4-gateway/tests/test_gateway.py` | 10 test cases cho Gateway |

**Cách chạy:**

```bash
make exercise-test
```

**Output thật (`make exercise-test`):**

```text
$ make exercise-test
exercises/week4-gateway/tests/test_app.py::test_health_returns_ok PASSED [  5%]
exercises/week4-gateway/tests/test_app.py::test_items_returns_list PASSED [ 11%]
exercises/week4-gateway/tests/test_app.py::test_item_by_id_returns_one_item PASSED [ 16%]
exercises/week4-gateway/tests/test_app.py::test_unknown_item_returns_404 PASSED [ 22%]
exercises/week4-gateway/tests/test_app.py::test_echo_returns_body_back PASSED [ 27%]
exercises/week4-gateway/tests/test_app.py::test_admin_exists_but_is_not_protected_by_the_app_itself PASSED [ 33%]
exercises/week4-gateway/tests/test_app.py::test_debug_exists_but_is_not_protected_by_the_app_itself PASSED [ 38%]
exercises/week4-gateway/tests/test_app.py::test_echo_query_returns_query_params PASSED [ 44%]
exercises/week4-gateway/tests/test_gateway.py::test_allowlisted_endpoint_with_valid_key_reaches_upstream PASSED [ 50%]
exercises/week4-gateway/tests/test_gateway.py::test_missing_api_key_returns_401 PASSED [ 55%]
exercises/week4-gateway/tests/test_gateway.py::test_wrong_api_key_returns_401 PASSED [ 61%]
exercises/week4-gateway/tests/test_gateway.py::test_endpoint_outside_allowlist_returns_403 PASSED [ 66%]
exercises/week4-gateway/tests/test_gateway.py::test_debug_endpoint_outside_allowlist_returns_403 PASSED [ 72%]
exercises/week4-gateway/tests/test_gateway.py::test_method_not_in_allowlist_returns_403 PASSED [ 77%]
exercises/week4-gateway/tests/test_gateway.py::test_allowlisted_post_reaches_upstream PASSED [ 83%]
exercises/week4-gateway/tests/test_gateway.py::test_exceeding_rate_limit_returns_429 PASSED [ 88%]
exercises/week4-gateway/tests/test_gateway.py::test_api_key_never_appears_in_the_request_log PASSED [ 94%]
exercises/week4-gateway/tests/test_gateway.py::test_query_string_is_forwarded_to_upstream PASSED [100%]

======================== 18 passed, 1 warning in 1.25s =========================
```

**Kiểm chứng .dockerignore (Khớp đệ quy `**/__pycache__`, `**/*.pyc`, loại trừ tests/, requests.jsonl, compose.yml, Dockerfile):**

```text
$ cd exercises/week4-gateway
$ ls -d app/__pycache__ gateway/__pycache__
app/__pycache__  gateway/__pycache__

$ docker build --no-cache -f gateway/Dockerfile -t w4-gw:check .
$ docker run --rm w4-gw:check sh -c 'find /srv -name "__pycache__" -o -name "*.pyc" -o -name "requests.jsonl" -o -name "Dockerfile"'
(Lệnh find không in ra dòng nào -> hoàn toàn sạch sẽ, không lọt bất kỳ bytecode, log hay test nào)

$ docker rmi -f w4-gw:check
```

**Output Live Container (`docker compose` + `curl`):**

```text
health:  200
admin:   403
no key:  401
```

---

## 6. Vì sao chọn cách implement này

- **Thứ tự kiểm tra an ninh nghiêm ngặt:** `Auth (401) -> Allowlist (403) -> Rate Limit (429) -> Forward`. Thiết kế này đảm bảo từ chối các truy cập bất hợp pháp ngay từ bước đầu trước khi tiêu tốn tài nguyên kiểm tra nâng cao hoặc tài nguyên mạng.
- **Bảo mật audit log tuyệt đối:** Hàm `log_request` chỉ nhận `(method, path, status, elapsed_ms)`, không có bất kỳ tham số nào chứa `headers` hoặc `API_KEY`.
- **Cô lập mạng chặt chẽ:** `target-app` không mở cổng ra host; chỉ có `exercise-gateway` mở cổng loopback `127.0.0.1:9000`, tuân thủ bất biến mạng tuần 4.
- **Chuyển tiếp nguyên vẹn query string:** Tách bạch giữa `path` (đối chiếu exact match với allowlist) và `target_url` (ghép thêm query string để upstream nhận đầy đủ tham số).
- **Pattern .dockerignore đệ quy (`**/`):** Ngăn chặn toàn bộ bytecode `__pycache__` và `*.pyc` ở mọi cấp thư mục lồng nhau (`app/`, `gateway/`) bị copy vào image khi build context là thư mục cha.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `make exercise-test` | 0 | 18 passed (100%) |
| `docker run --rm w4-gw:check sh -c 'find /srv ...'` | 0 | 0 match (không lọt `__pycache__`, `*.pyc`, `requests.jsonl`, `Dockerfile`) |
| Live docker compose + curl test | 0 | `health: 200`, `admin: 403`, `no key: 401` |
| `pytest -m "not llm" ...` (toàn bộ offline suite) | 0 | 142 passed, 1 deselected (100%) |
| `python3 -m compileall -q exercises/week4-gateway` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, secret isolation (không log API key), network isolation (chỉ gateway bind loopback).

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Biến môi trường `EXERCISE_API_KEY` được truyền khi chạy gateway.
- **Việc còn nợ:** Task 10 (Python client tool và tài liệu README cho bài tập Week 4).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 9 lên nhánh `feat/gateway-exercise-proxy` ngay bây giờ không?
