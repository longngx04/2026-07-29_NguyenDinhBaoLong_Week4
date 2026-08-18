# Worklog — Task 8: Bài tập W4 — Ứng dụng FastAPI phía sau Gateway

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/gateway-exercise-app` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 8

---

## 1. Tóm tắt

- Tạo ứng dụng FastAPI độc lập tại `exercises/week4-gateway/app/` đại diện cho dịch vụ backend đích (target application).
- Ứng dụng phục vụ 6 route: `GET /health`, `GET /items`, `GET /items/{item_id}`, `POST /echo`, `GET /admin`, `GET /debug`.
- Route `/echo` giữ nguyên toàn bộ body nhận được (dùng `Body(...)`) mà không lọc field, phục vụ kiểm chứng việc Gateway có strip body hay không trong Task 9.
- App được thiết kế cố ý **không tự bảo vệ** (không kiểm tra auth/allowlist nội tại, route `/admin` và `/debug` vẫn trả về 200 khi gọi trực tiếp) nhằm làm nổi bật vai trò chốt chặn và phân quyền của API Gateway ở phía trước.
- Dockerfile được thiết lập chạy non-root user (`appuser`, uid 10001), có `HEALTHCHECK` tích hợp và `.dockerignore`.
- Thêm target `exercise-test` vào `Makefile` để chạy chính thức bộ test bài tập.
- Bộ test độc lập `exercises/week4-gateway/tests/test_app.py` với 7 unit test cases, toàn bộ 7/7 passed.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Là thành phần ứng dụng mục tiêu (target backend) phục vụ kịch bản bài tập thực hành Week 4, minh hoạ kiến trúc Gateway bảo vệ ứng dụng nội bộ theo mô hình Zero-Trust / Deny-by-default.
- **Nằm ở đâu trong luồng:** 
  - Nằm trong thư mục `exercises/week4-gateway/app/`.
  - Được đóng gói trong container và sẽ được gọi thông qua API Gateway trong Task 9.
- **Không có nó thì hỏng gì:** Không có ứng dụng đích để API Gateway chuyển tiếp (proxy) các request kiểm chứng an toàn trong bài tập Week 4.
- **Ngoài phạm vi (cố ý không làm):** Ứng dụng này không tự cài đặt logic xác thực JWT hay Allowlist, nhiệm vụ bảo vệ ranh giới mạng thuộc về API Gateway.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `exercises/week4-gateway/app/__init__.py` | Tạo mới | Package init rỗng | Đóng gói ứng dụng Python |
| `exercises/week4-gateway/app/requirements.txt` | Tạo mới | Khai báo `fastapi`, `uvicorn`, `httpx` | Khai báo dependencies của target app |
| `exercises/week4-gateway/app/main.py` | Tạo mới | Khởi tạo app FastAPI với 6 endpoints (echo giữ nguyên body) | Cung cấp ứng dụng backend đích |
| `exercises/week4-gateway/app/.dockerignore` | Tạo mới | Loại trừ Dockerfile, pycache, pyc | Tối ưu context build Docker |
| `exercises/week4-gateway/app/Dockerfile` | Tạo mới | Dockerfile non-root + HEALTHCHECK trên nền `python:3.12-slim` | Build container an toàn cho target app |
| `exercises/week4-gateway/tests/__init__.py` | Tạo mới | Package init rỗng cho test | Đóng gói test suite bài tập |
| `exercises/week4-gateway/tests/test_app.py` | Tạo mới | 7 unit test cases sử dụng `TestClient` | Kiểm thử tính đúng đắn của target app |
| `Makefile` | Sửa | Thêm target `exercise-test` và vào `.PHONY` | Lối chạy test bài tập chính thức |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành Task 8 Step 1 → 7 | Cập nhật tiến độ kế hoạch |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md | 14 +++++------
 exercises/week4-gateway/app/Dockerfile                    |  6 +++++
 exercises/week4-gateway/app/__init__.py                   |  0
 exercises/week4-gateway/app/main.py                       | 54 +++++++++++++++++++++++++++++++++++++++++++
 exercises/week4-gateway/app/requirements.txt              |  3 +++
 exercises/week4-gateway/tests/__init__.py                 |  0
 exercises/week4-gateway/tests/test_app.py                 | 49 +++++++++++++++++++++++++++++++++++++++
 7 files changed, 119 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Tạo test trước (`test_app.py`), chạy xác nhận `ModuleNotFoundError` (TDD Red).
2. Viết `requirements.txt` và cài đặt `fastapi`, `uvicorn`, `httpx`.
3. Viết `main.py` triển khai đầy đủ 6 routes:
   - `GET /health` -> `{"status": "ok"}`
   - `GET /items` -> danh sách items
   - `GET /items/{item_id}` -> item theo ID hoặc 404 nếu không tìm thấy
   - `POST /echo` -> echo lại body nhận được
   - `GET /admin` -> trả về secret (cố ý không auth)
   - `GET /debug` -> trả về thông tin debug (cố ý không auth)
4. Xử lý đường dẫn `sys.path` trong `test_app.py` để test có thể chạy cả từ thư mục gốc lẫn từ `exercises/week4-gateway`.
5. Tạo `Dockerfile` đóng gói ứng dụng chạy cổng 8000.
6. Chạy kiểm thử xác nhận xanh toàn bộ.

---

## 5. Output là gì

**Thành phần mới:**

| Loại | Tên | Đường dẫn | Mô tả |
|---|---|---|---|
| Module | `main.py` | `exercises/week4-gateway/app/main.py` | Ứng dụng FastAPI 6 routes |
| Dockerfile | `Dockerfile` | `exercises/week4-gateway/app/Dockerfile` | Container target app |
| Test suite | `test_app.py` | `exercises/week4-gateway/tests/test_app.py` | 7 test cases với TestClient |

**Cách chạy:**

```bash
pytest exercises/week4-gateway/tests/test_app.py -v
```

**Output thật:**

```text
$ pytest exercises/week4-gateway/tests/test_app.py -v
============================== test session starts ==============================
collected 7 items

exercises/week4-gateway/tests/test_app.py::test_health_returns_ok PASSED [ 14%]
exercises/week4-gateway/tests/test_app.py::test_items_returns_list PASSED [ 28%]
exercises/week4-gateway/tests/test_app.py::test_item_by_id_returns_one_item PASSED [ 42%]
exercises/week4-gateway/tests/test_app.py::test_unknown_item_returns_404 PASSED [ 57%]
exercises/week4-gateway/tests/test_app.py::test_echo_returns_body_back PASSED [ 71%]
exercises/week4-gateway/tests/test_app.py::test_admin_exists_but_is_not_protected_by_the_app_itself PASSED [ 85%]
exercises/week4-gateway/tests/test_app.py::test_debug_exists_but_is_not_protected_by_the_app_itself PASSED [100%]

========================= 7 passed, 1 warning in 0.28s =========================
```

---

## 6. Vì sao chọn cách implement này

- **Thiết kế ứng dụng mở (Unprotected by default):** Tuân thủ triết lý phòng thủ nhiều lớp nơi Gateway chịu trách nhiệm kiểm soát truy cập biên. App không thêm logic chặn auth để thể hiện rõ nét chức năng của Gateway trong bài tập Task 9.
- **Sử dụng `TestClient` thật từ `fastapi`:** Không dùng mock hay monkeypatch, thực thi request HTTP in-process qua ASGI stack thực tế.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest exercises/week4-gateway/tests/test_app.py -v` | 0 | 7 passed (100%) |
| `pytest -m "not llm" ...` (toàn bộ offline suite) | 0 | 131 passed, 1 deselected (100%) |
| `python3 -m compileall -q exercises/week4-gateway` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, không vi phạm secret isolation, không ảnh hưởng tới production package `src/project_sentinel/`.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** `uvicorn` chạy trên cổng 8000 trong container.
- **Việc còn nợ:** Task 9 (Xây dựng Gateway kiểm soát request cho bài tập Week 4).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 8 lên nhánh `feat/gateway-exercise-app` ngay bây giờ không?
