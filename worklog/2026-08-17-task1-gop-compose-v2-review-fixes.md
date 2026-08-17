# Worklog — Task 1 (v2): Sửa review — regression scan-profile, .dockerignore, test bất biến

**Ngày:** 2026-08-17 · **Agent/Model:** opencode · deepseek-v4-flash-free ·
**Branch:** `week4-cont` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 1 (review round 1)

> Vòng này KHÔNG tạo task mới — sửa 3 finding của Reviewer (Codex) trên diff Task 1. Worklog gốc:
> [`2026-08-17-task1-gop-compose.md`](2026-08-17-task1-gop-compose.md).

---

## 1. Tóm tắt

- Đã sửa 3 finding của Reviewer trên Task 1: (1) `make scan` không còn phụ thuộc
  `SENTINEL_GATEWAY_API_KEY` vì bỏ interpolation bắt buộc `:?`; (2) thêm `.dockerignore` ngăn
  `.env`/`.git`/runtime vào build context; (3) khoá test đúng bất biến "mọi host port bind loopback".
- Phục vụ người review và CI/người mới clone: `make scan` phải chạy được trên checkout sạch không có `.env`.
- Kết quả: 7/7 test pass, `--profile scan` parse OK khi không có key, build image `web` thành công
  với context giảm từ ~114MB+.git xuống ~21MB.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Giữ bất biến "scan là tác vụ không cần Gateway" và "secret không
  bao giờ vào build context" của infra.
- **Nằm ở đâu trong luồng:** Toàn bộ lệnh `make scan` + bất kỳ build `docker compose --profile app build web` nào.
- **Không có nó thì hỏng gì:** Trên CI/checkout sạch, `make scan` chết vì `required variable
  SENTINEL_GATEWAY_API_KEY is missing`; build web nướng `.env` (key thật) vào layer image và gửi
  `.git` 114MB làm context.
- **Ngoài phạm vi (cố ý không làm):** Không thay đổi cấu trúc Task 1 đã được duyệt; chỉ vá đúng
  các finding. Không đổi gì ở tests/unit/verification (fail loud do thiếu Gateway, ngoài phạm vi).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `docker-compose.yml` | Sửa | `environment: SENTINEL_GATEWAY_API_KEY=${SENTINEL_GATEWAY_API_KEY:?...}` → `${SENTINEL_GATEWAY_API_KEY}` (bỏ `:?`) | Compose interpolate toàn bộ file trước khi lọc profile; `:?` làm chết `make scan` khi thiếu key. Makefile `target-up`/`gateway-live-test` đã có `test -n "$$KEY" || exit 2` |
| `tests/unit/infra/test_compose_invariants.py` | Sửa | Đổi `test_no_service_binds_all_interfaces` → `test_every_host_port_binds_loopback_only` (assert prefix `127.0.0.1:`); thêm `test_no_required_env_var_breaks_scan_profile` | Test cũ chỉ chặn chuỗi `0.0.0.0`, không chặn `8000:8000` (bind mọi interface mặc định). Test mới khoá đúng điều tuyên bố + khoá bất biến scan-profile |
| `.dockerignore` | Tạo | Loại `.env`, `.git`, `.gitignore`, `.gitmodules`, `.venv`, `__pycache__`, `*.py[cod]`, `*.egg-info`, `.pytest_cache`, `build`, `dist`, `artifacts/`, `flow/`, `cards/`, `docs/ground-truth.md`, `DESIGN.md`, `RETRO.md`, `infra/docker/scanner/opengrep`, `reports/`, `*.pem`, `*.key` | Build context service `web` là toàn repo; không có `.dockerignore` thì `.env` key thật và `.git` 114MB vào image |
| `infra/docker/web/Dockerfile` | Sửa | `COPY pyproject.toml requirements.txt ./` + `COPY src ./src` TRƯỚC `RUN pip install` | Phát hiện thêm khi build thật: `requirements.txt` có dòng `-e .` nên `pip install` cần `pyproject.toml`/`src` tại `/app`; bản plan cũ `COPY . .` sau `RUN pip` nên build fail |
| `docs/superpowers/plans/...rebuild-plan-1-w1-w4.md` | Sửa | Đồng bộ 3 snippet: compose bỏ `:?`, test đổi tên + thêm test scan-profile, Dockerfile web thêm `COPY pyproject.toml/src`, thêm khối `.dockerignore` vào Step 5 | Plan là canonical; reviewer chỉ định "sửa cả hai chỗ" (test + plan); để plan khớp thực tế tránh task sau lặp lỗi |

**`git diff --stat` (phần thay đổi vòng review):**

```text
 docker-compose.yml                                   |  2 +-
 tests/unit/infra/test_compose_invariants.py          | 22 ++++---
 infra/docker/web/Dockerfile                          |  3 +-
 .dockerignore                                        |  Untracked (mới)
 docs/.../2026-08-17-rebuild-plan-1-w1-w4.md          | 60 +++++-----
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Sửa từng finding theo thứ tự mức độ — trước hết sửa nguyên nhân gốc (compose
interpolation), rồi phòng vệ bằng test, rồi mới vá khâu build context.

**Luồng dữ liệu:**

1. Finding 1: compose giữ `:?` → `make scan` (không `.env`) fail. Sau sửa: compose parse OK khi
   thiếu key; `target-up`/`gateway-live-test` vẫn bắt buộc key ở tầng Makefile.
2. Finding 2: `.dockerignore` chặn `.env`/`.git`/runtime → build context giảm 114MB → image không
   chứa secret.
3. Finding 3: test đảo chiều khẳng định — mọi port mapping phải bắt đầu `127.0.0.1:`; thêm test
   quét mọi `environment` chặn dạng `:?`.

**Các quyết định kỹ thuật:**

- Giữ việc bắt buộc key ở Makefile (`test -n "$$KEY"`) thay vì ở compose — key chỉ cần cho profile
  `target`, không cần cho `scan`. Đây chính là đề xuất của reviewer.
- Test `test_no_required_env_var_breaks_scan_profile` quét tĩnh YAML (không chạy Docker) — vừa đủ
  để bắt regression, không tốn container.
- `.dockerignore` loại cả `reports/` vì web không cần lịch sử sprint trong image.

**Xử lý lỗi / trường hợp biên:** Build web lần đầu fail (`-e .` không tìm thấy project) — đã phát
hiện nhờ chạy build thật, sửa Dockerfile để copy `pyproject.toml` + `src` trước `pip install`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| File config | `.dockerignore` | repo root | Chặn secret/VCS/runtime khỏi build context |
| Test | `test_every_host_port_binds_loopback_only` | `tests/unit/infra/test_compose_invariants.py` | Mọi port mapping phải có prefix `127.0.0.1:` |
| Test | `test_no_required_env_var_breaks_scan_profile` | `tests/unit/infra/test_compose_invariants.py` | Không service nào dùng interpolation `:?` |
| Dockerfile | `infra/docker/web/Dockerfile` | — | Copy `pyproject.toml`+`src` trước `pip install` |

**Cách chạy:**

```bash
python3 -m pytest tests/unit/infra -v
env -u SENTINEL_GATEWAY_API_KEY docker compose --profile scan --env-file /dev/null config --quiet
docker build --file infra/docker/web/Dockerfile --tag sentinel-sec/web:test .   # rồi xoá image
make scan
```

**Output thật (đã che secret):**

```text
$ python3 -m pytest tests/unit/infra -q
.......                                                                    [100%]
7 passed in 0.03s

$ env -u SENTINEL_GATEWAY_API_KEY docker compose --profile scan --env-file /dev/null config --quiet && echo OK
time="..." level=warning msg="The \"SENTINEL_GATEWAY_API_KEY\" variable is not set. Defaulting to a blank string."
OK

$ docker build --file infra/docker/web/Dockerfile --tag sentinel-sec/web:test .
#5 transferring context: 21.02MB 0.6s done      ← trước đây ~114MB+.git
#11 DONE 2.9s                                   ← build thành công
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Bỏ `:?` ở compose + giữ enforcement key ở Makefile; thêm `.dockerignore`; đảo
chiều khẳng định của test port binding; thêm test chống regression scan-profile.

**Lý do:** Reviewer chỉ ra Compose interpolate cả file trước khi lọc profile — fix ở tầng compose là
đúng gốc. Makefile đã enforce key (`target-up`, `gateway-live-test`), nên mất `:?` không làm mất
guardrail. `.dockerignore` là cơ chế chính thống của Docker cho context.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ nguyên `:?`, thêm `--env-file .env` mặc định khi scan | Không đổi compose | Checkout sạch không có `.env`; vẫn chết regression; thêm phụ thuộc ẩn |
| Test port binding chỉ thêm case `8000:8000` | Ít đổi | Vẫn liệt kê tay; assert ngược (`127.0.0.1:`) khoá chủ động hơn |
| Đưa `.env` vào `.dockerignore` qua `COPY . .` có `--exclude` | — | Docker không hỗ trợ `--exclude` trên COPY; chỉ `.dockerignore` mới đúng |

**Đánh đổi đã chấp nhận:** Mất fail-fast khi `docker compose` (tay, không qua Makefile) chạy target
mà thiếu key — gateway sẽ chạy với key blank và tự deny request (fail-closed), còn mọi đường `make`
vẫn báo lỗi rõ ràng.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `python3 -m pytest tests/unit/infra -v` | 0 | 7 passed |
| `env -u SENTINEL_GATEWAY_API_KEY docker compose --profile scan --env-file /dev/null config --quiet` | 0 | `OK` (trước sửa: exit 1 `required variable ... missing`) |
| `docker build --file infra/docker/web/Dockerfile --tag sentinel-sec/web:test .` | 0 | Build thành công; context 21.02MB |
| `make scan` | 0 | 23 findings, `OpenGrep report: .../artifacts/raw/opengrep.json` |
| `docker image rm sentinel-sec/web:test` | 0 | Image dọn sạch sau kiểm chứng |

**Test mới thêm / đổi:**

- `test_compose_invariants.py::test_every_host_port_binds_loopback_only` — mọi mapping phải match `127.0.0.1:`.
- `test_compose_invariants.py::test_no_required_env_var_breaks_scan_profile` — không `:?` trong `environment` (bảo vệ `make scan` trên checkout sạch).

**Bất biến đã giữ:** no mock/stub · test không skip · không lộ secret · chỉ Gateway bind loopback ·
không đụng `reports/week-XX/` · không tự commit · key bắt buộc ở Makefile `target-up`/`gateway-live-test` vẫn nguyên.

**Còn fail / chưa chạy được:** `tests/unit/verification` (22 errors) cần `SENTINEL_GATEWAY_API_KEY`
+ Gateway/WebGoat up — ngoài phạm vi; như mọi khi fail loud.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Việc bỏ `:?` khiến `docker compose` chạy tay (không qua Makefile) với
  profile `target` thiếu key chỉ cảnh báo blank, gateway deny hết — chấp nhận được nhưng cần xác
  nhận không ai phụ thuộc fail-fast đó.
- **Giả định đã đặt:** `.dockerignore` không loại nhầm file cần thiết cho build web; `reports/`
  không cần trong image web. `test_every_host_port_binds_loopback_only` coi web bind
  `127.0.0.1:8000:8000` là hợp lệ.
- **Việc còn nợ:** Chưa chạy `make gateway-up`/`make agent-test` (cần `.env` có key); chưa commit.
- **Câu hỏi cho người dùng:** Nếu Plan 3 thực sự build web trên context toàn repo, có cần tách
  `.dockerignore` chi tiết hơn theo nhu cầu web không? Hiện `.dockerignore` loại `reports/` và
  `artifacts/` — nếu web cần đọc `artifacts/` lúc build (không qua volume) thì phải xem lại.
