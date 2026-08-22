# Worklog — Cổng method và body hằng số trong Nginx Gateway cho lane DAST (Task 3)

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · Gemini Pro ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-post-reachability.md`](../docs/superpowers/plans/2026-08-22-dast-post-reachability.md) · **Task ID:** `Task 3`

> Điền đủ 8 mục. Mục nào không có nội dung thì ghi `Không có` — không được xoá mục.
> Mọi số liệu phải là kết quả chạy thật. Che secret bằng `***`.

---

## 1. Tóm tắt

Task 3 đã bổ sung cơ chế kiểm soát phương thức POST và ép body chính tắc (canonical body) trong cấu hình Nginx Gateway (`default.conf.template`) cho lane DAST theo nguyên tắc deny-by-default. Cơ chế này phục vụ việc cho phép ZAP gửi request POST tới 11 endpoint WebGoat đã được thẩm tra độc lập mà không trao quyền cho ZAP tùy biến nội dung payload hoặc header. Kết quả kiểm thử toàn diện (unit tests, offline suite 939 tests, lint/typecheck và live container test) đều đạt 100%, xác nhận request POST hợp lệ trả về HTTP 200, POST ngoài allowlist bị chặn với HTTP 405, và GET vẫn hoạt động bình thường.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Thiết lập lớp bảo vệ hạ tầng (Gateway level enforcement) cho lane DAST, ánh xạ 11 URI đã duyệt sang body chính tắc cố định thông qua directive Nginx `map` và `proxy_set_body`, đồng thời chặn mọi method hoặc URI chưa được duyệt bằng mã phản hồi HTTP 405 Method Not Allowed.
- **Nằm ở đâu trong luồng:** Tại Nginx reverse proxy (cổng 8081 nội bộ), đứng trước WebGoat và tiếp nhận traffic từ ZAP (`scan-zap.sh` / Automation Framework `requestor` job).
- **Không có nó thì hỏng gì:** Nếu không có lớp gateway này, hoặc là DAST lane bị khóa cứng ở GET/HEAD (khiến 19 finding SAST POST không thể chứng minh reachability), hoặc nếu mở POST tự do thì ZAP có thể gửi payload tùy ý/độc hại trực tiếp vào WebGoat, phá vỡ tính an toàn và khả năng kiểm soát của lane DAST.
- **Ngoài phạm vi (cố ý không làm):** Không tự động sinh cấu hình Nginx từ JSON (giữ nguyên nguyên tắc 2 lớp độc lập đối chiếu bằng test), không thay đổi cấu hình ZAP scan script hay YAML plan (thuộc Task 4), không thay đổi logic tính toán tương quan SAST-DAST (thuộc Task 5).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/unit/gateway/test_dast_post_policy.py` | Tạo | Tạo mới 7 unit tests kiểm tra toàn diện chính sách DAST POST: đối chiếu 11 path và canonical body giữa Nginx template và `dast-allowlist.json`, kiểm tra deny-by-default (`default 0`), kiểm tra `proxy_set_body`, `proxy_pass_request_body off`, `proxy_pass_request_headers off`, và giới hạn `client_max_body_size 8k` | Khoá chính sách DAST POST mới theo TDD |
| `infra/docker/gateway/templates/default.conf.template` | Sửa | Thêm 2 block `map $uri $sentinel_dast_post_body` (11 entries) và `map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok`; sửa server block DAST 8081: nâng `client_max_body_size` lên `8k`, kiểm tra `$sentinel_dast_method_ok = 0 { return 405; }`, bỏ `content_length 413`, thêm `proxy_set_body` và `Content-Type` | Triển khai chính sách DAST POST và ép body chính tắc tại Gateway |
| `tests/unit/gateway/test_dast_gateway_config.py` | Sửa | Viết lại hàm `test_dast_listener_only_forwards_read_only_methods` thành `test_dast_listener_forwards_only_reviewed_methods_and_bodies` để phù hợp với chính sách mới | Cập nhật assertion kiểm tra Nginx config cho chính sách mới |

**`git diff --stat`:**

```text
 infra/docker/gateway/templates/default.conf.template | 38 ++++++++++++++++++++--
 tests/unit/gateway/test_dast_gateway_config.py     | 16 ++++++---
 tests/unit/gateway/test_dast_post_policy.py        | 97 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 144 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Áp dụng phương pháp Test-Driven Development (TDD). Viết test tĩnh đối chiếu chính sách `test_dast_post_policy.py` trước và chạy để ghi nhận trạng thái RED (6/7 tests fail). Sau đó cập nhật Nginx template với hai cấu trúc `map`: một map URI sang canonical body và một map ghép `$request_method:$sentinel_dast_post_body` để kiểm tra điều kiện cho phép. Cập nhật khối listener DAST 8081 để thực thi chính sách, cập nhật test cấu hình cũ, và chạy kiểm chứng trên container Docker thật.

**Luồng dữ liệu:**
1. ZAP gửi request tới `http://gateway-dast:8081/WebGoat/...` kèm `X-Sentinel-DAST-Key`.
2. Nginx kiểm tra `$sentinel_dast_key_valid` (nếu sai trả 401).
3. Nginx tra cứu `$uri` trong `map $uri $sentinel_dast_post_body` để lấy body chính tắc tương ứng (hoặc chuỗi rỗng nếu URI không có trong allowlist).
4. Nginx đánh giá `$request_method:$sentinel_dast_post_body` qua `map ... $sentinel_dast_method_ok`:
   - `GET` hoặc `HEAD` -> `1` (hợp lệ).
   - `POST` kèm body khác rỗng -> `1` (hợp lệ).
   - Mọi trường hợp khác (POST URI chưa duyệt, PUT, DELETE,...) -> `0` (trả về HTTP 405).
5. Khi hợp lệ, request đi vào `location ^~ /WebGoat/`:
   - `proxy_pass_request_body off;` loại bỏ body của caller.
   - `proxy_set_body $sentinel_dast_post_body;` thay thế bằng body chính tắc.
   - `proxy_set_header Content-Type "application/x-www-form-urlencoded";`
   - `proxy_set_header Content-Length "";` (giữ nguyên theo Task 1).
   - `proxy_pass http://webgoat:8080;` chuyển tiếp lên WebGoat.

**Các quyết định kỹ thuật:**
- Sử dụng cấu trúc `map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok` với `default 0;` để đảm bảo deny-by-default nằm ngay trong cấu trúc map thay vì dựa vào danh sách phủ định.
- Đồng bộ thủ công 11 path từ `configs/gateway/dast-allowlist.json` vào Nginx template và dùng test `test_dast_post_policy.py` để kiểm tra 2 chiều (Nginx không thiếu path từ JSON, và Nginx không có path thừa ngoài JSON). Không dùng script sinh mã để duy trì 2 lớp kiểm tra độc lập.
- Giữ nguyên `proxy_set_header Content-Length "";` theo đúng kết luận đo đạc thực nghiệm từ Task 1 Step 3.

**Xử lý lỗi / trường hợp biên:**
- Request POST tới path không có trong allowlist (ví dụ `/WebGoat/login`) -> `$sentinel_dast_post_body` là `""` -> `$request_method:$sentinel_dast_post_body` là `POST:` -> `$sentinel_dast_method_ok` là `0` -> trả về HTTP 405.
- Request chứa `Transfer-Encoding: chunked` -> bị chặn ngay bởi `if ($http_transfer_encoding) { return 400; }`.
- Caller gửi body vượt quá 8k -> bị chặn bởi `client_max_body_size 8k`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Test | `tests/unit/gateway/test_dast_post_policy.py` | `tests/unit/gateway/test_dast_post_policy.py` | Bộ 7 test khoá chính sách DAST POST, map Nginx và các bất biến bảo vệ |
| Test | `test_dast_listener_forwards_only_reviewed_methods_and_bodies` | `tests/unit/gateway/test_dast_gateway_config.py` | Test cấu hình listener DAST theo chính sách mới |
| Config | `infra/docker/gateway/templates/default.conf.template` | `infra/docker/gateway/templates/default.conf.template` | Template Nginx Gateway chứa 2 map và cấu hình DAST boundary mới |

**Cách chạy:**

```bash
# Chạy unit tests gateway
.venv/bin/python -m pytest tests/unit/gateway/ -v

# Chạy offline test suite
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests

# Linting và typechecking
make lint && make typecheck

# Khởi động container và đo đạc live
SENTINEL_DAST_API_KEY=$(openssl rand -hex 32) docker compose --profile dast up --detach --build gateway-dast
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="canary=999" http://127.0.0.1:8081/WebGoat/SqlInjection/attack2 2>&1 | head -30
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="x=1" http://127.0.0.1:8081/WebGoat/login 2>&1 | head -30
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    http://127.0.0.1:8081/WebGoat/login 2>&1 | head -30'
```

**Output thật (đã che secret):**

*Output 1: Unit tests gateway (`tests/unit/gateway/` - 62 passed):*
```text
============================== 62 passed in 0.51s ==============================
```

*Output 2: Offline test suite (`not llm and not live_gateway` - 939 passed):*
```text
939 passed, 38 deselected, 1 warning in 15.80s
```

*Output 3: Lint & Typecheck:*
```text
All checks passed!
Success: no issues found in 78 source files
```

*Output 4: Live container tests:*
```text
--- POST path DA allowlist ---
Connecting to 127.0.0.1:8081 (127.0.0.1:8081)
  HTTP/1.1 200 
  Server: nginx/1.27.5
  Date: Sat, 22 Aug 2026 14:30:50 GMT
  Content-Type: application/json
  Transfer-Encoding: chunked
  Connection: close
  X-Sentinel-Gateway: dast
  
writing to stdout
{
  "lessonCompleted" : false,
  "feedback" : "Something went wrong! You got no results, check your SQL Statement and the table above.",
  "feedbackArgs" : null,
  "output" : "unexpected end of statement",
  "outputArgs" : null,
  "assignment" : "SqlInjectionLesson2",
  "attemptWasMade" : true
}-                    100% |********************************|   296  0:00:00 ETA
written to stdout
--- POST path CHUA allowlist ---
Connecting to 127.0.0.1:8081 (127.0.0.1:8081)
  HTTP/1.1 405 Not Allowed
wget: server returned error: HTTP/1.1 405 Not Allowed
--- GET van chay ---
Connecting to 127.0.0.1:8081 (127.0.0.1:8081)
  HTTP/1.1 200 
  Server: nginx/1.27.5
  Date: Sat, 22 Aug 2026 14:30:50 GMT
  Content-Type: text/html;charset=UTF-8
  Transfer-Encoding: chunked
  Connection: close
  Content-Language: en-US
  X-Sentinel-Gateway: dast
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Sử dụng 2 directive `map` trong Nginx để liên kết URI với canonical body và kiểm tra điều kiện method một cách độc lập, kết hợp với `proxy_set_body` và `proxy_pass_request_body off`.

**Lý do:**
Theo đúng chỉ định trong plan `docs/superpowers/plans/2026-08-22-dast-post-reachability.md` (Task 3 Step 3 & 4) và Spec §6:
1. *"Không có body chính tắc" và "không được POST" phải là CÙNG một điều. Hai danh sách riêng thì sẽ có ngày quên đồng bộ một bên.*
2. *"Sinh nginx từ JSON sẽ biến hai lớp kiểm thành một lớp — đó là lý do việc đồng bộ được kiểm bằng test chứ không bằng script sinh mã."*
3. Việc sử dụng `map` giúp Nginx xử lý hiệu quả với O(1) hash lookup cho URI thay vì dùng chuỗi `if/else` lồng nhau.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Sinh Nginx config tự động từ `dast-allowlist.json` | Không cần gõ tay 11 path vào Nginx template | Vi phạm nguyên tắc 2 lớp kiểm tra độc lập (AGENTS.md §2, Plan Task 3) — nếu generator có lỗi sẽ làm cả 2 bên cùng sai. |
| Mở method POST cho toàn bộ `/WebGoat/` và chỉ filter ở ZAP | Đơn giản hóa cấu hình Nginx | Vi phạm nguyên tắc phòng thủ theo chiều sâu (Defense-in-depth, `.agents/security.md` §3 & §4) — Nginx phải là chốt chặn cuối cùng từ chối các POST chưa qua review. |
| Chuyển tiếp nguyên văn body của ZAP lên WebGoat | Linh hoạt hơn cho ZAP scanner | Nguy cơ bảo mật cao: ZAP có thể vô tình hoặc cố ý gửi payload khai thác làm thay đổi dữ liệu hoặc kích hoạt lỗ hổng thực sự thay vì chỉ kiểm tra reachability. |

**Đánh đổi đã chấp nhận:** Chấp nhận phải duy trì cả 2 file (JSON allowlist và Nginx template) song song, bù lại có test tĩnh `test_dast_post_policy.py` tự động phát hiện ngay lập tức nếu 2 bên bị lệch nhau.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/gateway/test_dast_post_policy.py -v` | 0 | 7 passed in 0.08s |
| `.venv/bin/python -m pytest tests/unit/gateway/ -v` | 0 | 62 passed in 0.51s |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 939 passed, 38 deselected, 1 warning |
| `make lint && make typecheck` | 0 | All checks passed, 78 source files clean |
| `docker compose --profile dast exec -T gateway-dast ... (POST allowlist)` | 0 | HTTP/1.1 200 OK |
| `docker compose --profile dast exec -T gateway-dast ... (POST unallowlist)` | 1 (wget 405 error) | HTTP/1.1 405 Not Allowed |
| `docker compose --profile dast exec -T gateway-dast ... (GET login)` | 0 | HTTP/1.1 200 OK |

**Test mới thêm:**

- `tests/unit/gateway/test_dast_post_policy.py::test_post_is_gated_by_the_canonical_body_map` — Khẳng định POST bị ràng buộc trực tiếp bởi map canonical body.
- `tests/unit/gateway/test_dast_post_policy.py::test_the_method_map_denies_by_default` — Khẳng định `map ... $sentinel_dast_method_ok` có `default 0`.
- `tests/unit/gateway/test_dast_post_policy.py::test_every_allowlisted_path_appears_in_the_nginx_body_map` — Khẳng định 100% path trong `dast-allowlist.json` có mặt trong Nginx template với đúng canonical body.
- `tests/unit/gateway/test_dast_post_policy.py::test_the_nginx_body_map_advertises_nothing_beyond_the_allowlist` — Khẳng định Nginx không chứa bất kỳ path nào ngoài JSON allowlist.
- `tests/unit/gateway/test_dast_post_policy.py::test_the_lane_dictates_the_body_not_the_caller` — Khẳng định Nginx cấu hình `proxy_set_body` và `proxy_pass_request_body off`.
- `tests/unit/gateway/test_dast_post_policy.py::test_caller_headers_are_still_stripped` — Khẳng định Nginx cấu hình `proxy_pass_request_headers off`.
- `tests/unit/gateway/test_dast_post_policy.py::test_body_size_is_bounded` — Khẳng định `client_max_body_size 8k`.

**Bất biến đã giữ:**
- Không có bất kỳ mock/stub/fake implementation nào.
- 4 lớp bảo vệ của lane DAST được giữ nguyên và tăng cường: credential riêng, xóa header caller, xóa body caller, chỉ nội bộ không bind host port.
- Toàn bộ 939 offline tests pass (không giảm so với mốc baseline).
- Không sửa đổi các report lịch sử `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có — các map Nginx và server block đã được kiểm thử cả về mặt cấu hình tĩnh (pytest) lẫn đo lường trực tiếp trên container runtime.
- **Giả định đã đặt:** Giả định rằng toàn bộ 11 endpoints trong `dast-allowlist.json` đều nhận form URL-encoded (`application/x-www-form-urlencoded`), khớp với header `proxy_set_header Content-Type "application/x-www-form-urlencoded";` đã đặt ở Nginx.
- **Việc còn nợ:** Chuyển sang Task 4 để viết `infra/docker/zap/requestor-plan.yaml`, cập nhật `scripts/scan-zap.sh` để thêm lần gọi ZAP thứ hai chạy `requestor` job.
- **Câu hỏi cho người dùng:** Không có.
