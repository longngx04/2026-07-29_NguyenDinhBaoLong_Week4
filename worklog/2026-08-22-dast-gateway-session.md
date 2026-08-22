# Worklog — Gateway giữ session DAST, chặn logout và log thêm query

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 2`

---

## 1. Tóm tắt

Đã thiết lập cơ chế để Nginx Gateway tự động khởi tạo session WebGoat lúc khởi động (`16-acquire-dast-session.envsh`) và gắn header `Cookie: JSESSIONID=...` cho mọi request chuyển tiếp từ ZAP Baseline. Đồng thời cấu hình Gateway chặn gọi `/WebGoat/logout` bằng mã 403 để bảo vệ tính toàn vẹn của session, và bổ sung `query=$args` vào định dạng log `sentinel_dast_access`. Kết quả: 10 test case mới trong `test_dast_session.py` pass 100%, bảo toàn 862 tests offline.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cho phép quét DAST có phiên đăng nhập mà ZAP vẫn là scanner ẩn danh không body, không credential; ranh giới bảo mật Gateway là nơi duy nhất quản lý session.
- **Nằm ở đâu trong luồng:** Tại cấu hình và entrypoint của container `gateway` (listener DAST cổng 8081).
- **Không có nó thì hỏng gì:** ZAP chỉ quét được 19 URL công khai, không chạm tới được các bài học và lỗ hổng thực sự của WebGoat (đòi hỏi session).
- **Ngoài phạm vi (cố ý không làm):** Chưa chạy scan ZAP và chưa cập nhật fixture (nội dung của Task 3).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh` | Tạo | Script `.envsh` lấy `JSESSIONID` qua wget và export `SENTINEL_DAST_SESSION` | Khởi tạo session tự động khi gateway-dast khởi động |
| `infra/docker/gateway/Dockerfile` | Sửa | `chmod 0755` cho `16-acquire-dast-session.envsh` | Đảm bảo script có quyền thực thi để entrypoint source được |
| `infra/docker/gateway/templates/default.conf.template` | Sửa | Thêm `proxy_set_header Cookie`, chặn `/WebGoat/logout` trả về 403 | Gắn session tự động và bảo vệ session không bị huỷ giữa chừng |
| `infra/docker/gateway/nginx.conf` | Sửa | Thêm `query=$args` vào `log_format sentinel_dast_access` sau `path=$uri ` | Phục vụ trích xuất bản đồ endpoint kèm tham số query |
| `tests/unit/gateway/test_dast_session.py` | Tạo | 10 unit test khoá chính sách session, entrypoint, cookie injection, logout block, log format | Kiểm chứng tự động chính sách Gateway DAST |

**`git diff --stat`:**

```text
 infra/docker/gateway/Dockerfile                      |  2 +-
 infra/docker/gateway/nginx.conf                      |  3 ++-
 infra/docker/gateway/templates/default.conf.template |  8 ++++++++
 tests/unit/gateway/test_dast_session.py              | 88 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 99 insertions(+), 2 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Tận dụng cơ chế xử lý file `.envsh` của image `nginx:1.27-alpine` (được `source` bởi `/docker-entrypoint.sh` trước khi `20-envsubst-on-templates.sh` thực thi).
Script `16-acquire-dast-session.envsh` chỉ kích hoạt khi `SENTINEL_GATEWAY_MODE="dast"`, đăng ký một tài khoản ngẫu nhiên với WebGoat, lấy `JSESSIONID`, kiểm tra hợp lệ với `/WebGoat/start.mvc`, và export biến môi trường `SENTINEL_DAST_SESSION`.

**Luồng dữ liệu:**
Docker startup $\rightarrow$ `16-acquire-dast-session.envsh` $\rightarrow$ `export SENTINEL_DAST_SESSION` $\rightarrow$ `20-envsubst-on-templates.sh` $\rightarrow$ Nginx config có `proxy_set_header Cookie "JSESSIONID=..."` $\rightarrow$ Mọi GET/HEAD từ ZAP được chuyển tiếp với Cookie hợp lệ.

**Các quyết định kỹ thuật:**
- Script mang đuôi `.envsh` và prefix `16-` (chạy sau `00-require-key.sh` và trước `20-envsubst-on-templates.sh`).
- Chặn tuyệt đối `/WebGoat/logout` bằng `location ^~ /WebGoat/logout { return 403; }` để ZAP spider không vô tình đăng xuất làm mất session.
- Trường `query=$args` được đặt ngay sau `path=$uri ` trong log format để giữ khoảng trắng phía sau `path=`, không làm vỡ các biểu thức chính quy parser access log hiện có.

**Xử lý lỗi / trường hợp biên:**
- Nếu không lấy được session hoặc WebGoat từ chối session: script `exit 1` làm Gateway fail loud ngay từ lúc khởi động, ngăn chặn tình trạng "chạy ngầm ẩn danh mà tưởng có session".
- Nếu mode không phải `dast` (ví dụ lane `probe`): script thoát ngay lập tức mà không tác động.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Script | `16-acquire-dast-session.envsh` | `infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh` | Script bootstrap session DAST |
| Config | DAST Cookie & Logout | `infra/docker/gateway/templates/default.conf.template` | Cấu hình proxy session & chặn logout |
| Config | DAST Log Format | `infra/docker/gateway/nginx.conf` | Định dạng log access có query string |
| Test | `test_dast_session.py` | `tests/unit/gateway/test_dast_session.py` | 10 unit test khoá chính sách |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/gateway/test_dast_session.py -v
```

**Output thật (đã che secret):**

```text
============================= test session starts ==============================
collected 10 items

tests/unit/gateway/test_dast_session.py::test_session_script_is_envsh_because_sh_cannot_export PASSED [ 10%]
tests/unit/gateway/test_dast_session.py::test_session_script_runs_after_local_resolvers_and_before_envsubst PASSED [ 20%]
tests/unit/gateway/test_dast_session.py::test_dockerfile_makes_the_session_script_executable PASSED [ 30%]
tests/unit/gateway/test_dast_session.py::test_session_script_only_runs_in_dast_mode PASSED [ 40%]
tests/unit/gateway/test_dast_session.py::test_session_script_fails_loudly_when_it_cannot_authenticate PASSED [ 50%]
tests/unit/gateway/test_dast_session.py::test_gateway_injects_the_cookie_itself PASSED [ 60%]
tests/unit/gateway/test_dast_session.py::test_caller_headers_are_still_stripped PASSED [ 70%]
tests/unit/gateway/test_dast_session.py::test_logout_is_blocked_at_the_gateway PASSED [ 80%]
tests/unit/gateway/test_dast_session.py::test_logout_block_is_declared_before_the_general_webgoat_location PASSED [ 90%]
tests/unit/gateway/test_dast_session.py::test_dast_log_format_records_the_query_string PASSED [100%]

============================== 10 passed in 0.02s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Gateway tự bootstrap session và inject Cookie qua Nginx template.

**Lý do:**
- Bảo toàn tuyệt đối 2 cơ chế bảo vệ cốt lõi của lane DAST: chỉ cho GET/HEAD và `proxy_pass_request_headers off`.
- ZAP không cần và không thể can thiệp vào credential hay session.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Cho ZAP tự đăng nhập | Cấu hình trong ZAP context | Vi phạm bất biến: phải nới POST và mở header cho ZAP, phá vỡ tính an toàn của lane DAST |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/gateway/test_dast_session.py -v` | 0 | 10 passed |
| `.venv/bin/python -m pytest tests/unit/gateway/test_dast_gateway_config.py -v` | 0 | 6 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 862 passed, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |

**Bất biến đã giữ:**
- Không sửa assertion nào trong `test_dast_gateway_config.py`.
- `query=$args` đặt sau `path=$uri `.
- Không rò rỉ secret / JSESSIONID.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Thứ tự prefix script `16-` đảm bảo luôn chạy sau `00-require-key.sh` và trước `20-envsubst-on-templates.sh`.
- **Giả định đã đặt:** Image `nginx:1.27-alpine` tiếp tục duy trì cơ chế source `.envsh` trong `/docker-entrypoint.sh`.
- **Việc còn nợ:** Chạy live scan ZAP trong Task 3 để kiểm chứng số lượng URL thực tế tăng vượt mốc 19.
