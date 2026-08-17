# Worklog — Task 1 (v3): Giữ auth-bypass Gateway khi key rỗng qua entrypoint guard

**Ngày:** 2026-08-17 · **Agent/Model:** opencode · deepseek-v4-flash-free ·
**Branch:** `week4-cont` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 1 (review round 2 — auth bypass)

> Vòng này sửa finding của Reviewer trên lần chuyển guard key sang image gateway. Worklog trước:
> [`2026-08-17-task1-gop-compose.md`](2026-08-17-task1-gop-compose.md) (v1) và
> [`2026-08-17-task1-gop-compose-v2-review-fixes.md`](2026-08-17-task1-gop-compose-v2-review-fixes.md) (v2).

---

## 1. Tóm tắt

- Đã chuyển guard "key không rỗng" từ compose (bỏ `:?` để `make scan` không phụ thuộc key ở v2) sang
  **image gateway**: script entrypoint `00-require-key.sh` exit 1 khi `SENTINEL_GATEWAY_API_KEY` rỗng,
  tận dụng `set -e` của entrypoint nginx để container chết hẳn — không còn gateway chạy với key rỗng.
- Phục vụ mọi đường khởi động Gateway, kể cả `docker compose --profile target up` trực tiếp (không qua
  Makefile) mà plan Chốt giao cho các task sau.
- Kết quả (đã chạy thật): key rỗng ⇒ container `exited with code 1` + log câu từ chối; key `test-key` ⇒
  `/WebGoat/attack` không header = **401**, có header đúng = **200**; `--profile scan` không key vẫn parse
  exit 0; `tests/unit/infra` 8/8 xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Khoá bất biến bảo mật "Gateway KHÔNG BAO GIỜ chạy không auth". Trước
  v2, `docker compose --profile target up` không có key ⇒ nginx map `"" 1;` khớp request không header
  ⇒ mở toang WebGoat ra `127.0.0.1:9080` mà không cần key.
- **Nằm ở đâu trong luồng:** Điểm khởi động container gateway — chạy trước `20-envsubst-on-templates.sh`
  (render `default.conf.template`), nên nếu không có key thì nginx chưa bao giờ render template lỗi.
- **Không có nó thì hỏng gì:** Auth bypass — request không header tới `/WebGoat/attack` được proxy tới
  WebGoat (đã kiểm chứng nginx thật trả 200 thay vì 401); vi phạm security.md "missing/wrong key phải bị
  reject".
- **Ngoài phạm vi (cố ý không làm):** Không đổi `docker-compose.yml` (giữ `${SENTINEL_GATEWAY_API_KEY}`,
  không `:?`, không default value); không đổi template nginx; không đụng Makefile (guard của Makefile vẫn
  còn, đây là giữ nền).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `infra/docker/gateway/docker-entrypoint.d/00-require-key.sh` | Tạo | Script `test -n "$SENTINEL_GATEWAY_API_KEY" || { echo từ chối >&2; exit 1; }` | Điểm guard mới: fail loud lúc start thay vì nginx map chấp nhận key rỗng |
| `infra/docker/gateway/Dockerfile` | Sửa | `COPY docker-entrypoint.d/ /docker-entrypoint.d/` + `RUN chmod 0755 /docker-entrypoint.d/00-require-key.sh` (trước 2 COPY cũ) | Nạp script vào image; nginx entrypoint chỉ chạy `.sh` có executable bit; không đổi FROM/EXPOSE |
| `tests/unit/infra/test_compose_invariants.py` | Sửa | Thêm `test_gateway_image_refuses_empty_api_key` — đọc thật `Dockerfile` (phải chứa `docker-entrypoint.d`) + script (phải tồn tại, chứa `SENTINEL_GATEWAY_API_KEY`, `exit 1`) | Khoá guard bằng test tĩnh, chạy offline không cần Docker |
| `docs/superpowers/plans/...rebuild-plan-1-w1-w4.md` | Sửa | Thêm Step 4b "Guard key rỗng nằm ở IMAGE gateway" + giải thích vì sao không `:?`; thêm 2 file vào Files list Task 1 | Plan là canonical; các task sau gọi thẳng `docker compose --profile target up` phải biết guard nằm ở đâu |

**`git diff --stat` (phần vòng này):**

```text
 infra/docker/gateway/Dockerfile                    |  2 +
 tests/unit/infra/test_compose_invariants.py        | 21 ++++++
 docs/.../2026-08-17-rebuild-plan-1-w1-w4.md        | 37 ++++++----
 infra/docker/gateway/docker-entrypoint.d/          |  Untracked (1 script)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** TDD 4 bước (như lời nhắc): viết test ĐỎ đọc thật file → tạo script guard → sửa
Dockerfile → đồng bộ plan. Sau đó kiểm chứng bằng build + chạy container thật.

**Luồng dữ liệu:** `SENTINEL_GATEWAY_API_KEY` (env) → compose đưa vào container → entrypoint nginx
(`set -e`) chạy `/docker-entrypoint.d/00-require-key.sh` (sort -V: `00-` trước `20-envsubst`) →
key rỗng ⇒ exit 1 ⇒ container chết, chưa bao giờ render template → không có gateway mở.
Key có giá trị ⇒ tiếp tục `20-envsubst-on-templates.sh` → nginx map chỉ nhận đúng key.

**Các quyết định kỹ thuật:**

- Tiền tố `00-` để chạy trước `20-envsubst-on-templates.sh` (xác nhận bằng đọc source entrypoint nginx:
  `/docker-entrypoint.d/` rỗng hoặc không có script executable thì entrypoint bỏ qua; `set -e` làm exit 1
  của script lan ra, container chết hẳn).
- `chmod 0755` trong Dockerfile vì nginx entrypoint chỉ launch script có executable bit (source entrypoint
  có nhánh `Ignoring $f, not executable`).
- Test tĩnh đọc thật file (không chạy Docker) — không vi phạm "không skip", không tốn container, đủ bắt
  regression: ai đó xoá script hoặc COPY trong Dockerfile là test đỏ ngay.

**Xử lý lỗi / trường hợp biên:** Khi chạy `SENTINEL_GATEWAY_API_KEY= docker compose ... up gateway`,
compose trả `exit=0` ở bản chạy đầu (do `tail` trong pipe); lấy lại bằng `docker inspect` thấy
`State.ExitCode=1`, `State.Status=exited` — chuẩn nhất là trạng thái container, không phải exit của lệnh
`docker compose up` qua pipe.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Script | `00-require-key.sh` | `infra/docker/gateway/docker-entrypoint.d/00-require-key.sh` | Guard fail-loud khi key rỗng |
| Dockerfile | `infra/docker/gateway/Dockerfile` | `COPY docker-entrypoint.d/` + `RUN chmod 0755` | Nạp + set executable guard |
| Test | `test_gateway_image_refuses_empty_api_key` | `tests/unit/infra/test_compose_invariants.py` | Khoá guard tồn tại + exit 1 |
| Plan | Step 4b | `docs/.../rebuild-plan-1-w1-w4.md` | Hướng dẫn guard mới + lý do không `:?` |

**Cách chạy:**

```bash
SENTINEL_GATEWAY_API_KEY= docker compose --profile target up --no-deps gateway   # kỳ vọng chết code 1
docker inspect sentinel-sec-gateway-1 --format '{{.State.ExitCode}} {{.State.Status}}'
SENTINEL_GATEWAY_API_KEY=test-key docker compose --profile target up -d gateway webgoat
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9080/WebGoat/attack
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Sentinel-Api-Key: test-key' http://127.0.0.1:9080/WebGoat/actuator/health
docker compose --profile target down
```

**Output thật (đã che secret):**

```text
$ SENTINEL_GATEWAY_API_KEY= docker compose --profile target up --no-deps gateway
...
gateway-1  | /docker-entrypoint.sh: Launching /docker-entrypoint.d/00-require-key.sh
gateway-1  | SENTINEL_GATEWAY_API_KEY is empty — refusing to start an unauthenticated gateway
gateway-1 exited with code 1

$ docker inspect sentinel-sec-gateway-1 --format '{{.State.ExitCode}} {{.State.Status}}'
1 exited

$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9080/WebGoat/attack
401
$ curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Sentinel-Api-Key: test-key' http://127.0.0.1:9080/WebGoat/actuator/health
200
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Entrypoint hook `/docker-entrypoint.d/00-require-key.sh` trong image gateway, exit 1
khi key rỗng, tận dụng `set -e` của entrypoint nginx chính thức.

**Lý do:** Lời nhắc chốt hướng này (không cho đổi thiết kế). Nó đúng với hai ràng buộc đối nghịch:
(i) compose không được dùng `:?` vì làm chết `make scan` (regression v2); (ii) gateway không được chạy
với key rỗng vì nginx `map` coi `""` là hợp lệ cho request không header (auth bypass). Guard ở image là
fail-closed đúng lúc nhất — trước khi template render — và bao trùm mọi cách khởi động (kể cả
`docker compose --profile target up` trực tiếp, không qua Makefile).

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Khôi phục `${SENTINEL_GATEWAY_API_KEY:?...}` trong compose | Fail loud ngay khi compose up | Làm chết `make scan` khi không có `.env` (chính regression v2); test `test_no_required_env_var_breaks_scan_profile` cấm |
| Validate key trong template nginx (if $sentinel_key_valid = 0 ở mọi location) | Giữ một nơi check | Không xử lý được trường hợp `""` (request không header) — map vẫn match; để lý luận chunk này là design đã chốt không được tự đổi |
| Script dùng `[ -z ... ]` và `exit 1` trong Dockerfile CMD | — | CMD nginx trong image là `nginx -g ...` cố định; thêm hook entrypoint là cơ chế chuẩn của image |

**Đánh đổi đã chấp nhận:** Guard ở image chỉ bảo vệ **runtime** — ai đó `docker run` image không nạp
entrypoint (override `--entrypoint`) vẫn thoát được, nhưng mọi đường `docker compose` (đường chính thống)
đều đi qua entrypoint.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `python3 -m pytest tests/unit/infra -v` (trước sửa) | 1 | Đỏ: `test_gateway_image_refuses_empty_api_key` fail (`docker-entrypoint.d` không có) |
| `python3 -m pytest tests/unit/infra -q` (sau sửa) | 0 | **8 passed** |
| `docker compose --profile target build gateway` (SENTINEL_GATEWAY_API_KEY=test-key) | 0 | Image `sentinel-sec-gateway` built |
| `SENTINEL_GATEWAY_API_KEY= docker compose --profile target up --no-deps gateway` | 0* | `gateway-1 exited with code 1` + log từ chối |
| `docker inspect sentinel-sec-gateway-1 --format '{{.State.ExitCode}} {{.State.Status}}'` | 0 | `1 exited` — **exit code 1 thật của container** (*exit 0 ở trên là do `tail` trong pipe) |
| `SENTINEL_GATEWAY_API_KEY=test-key docker compose --profile target up -d gateway webgoat` | 0 | Gateway Started, WebGoat Healthy |
| `curl -o /dev/null -w '%{http_code}' http://127.0.0.1:9080/WebGoat/attack` | 0 | **401** |
| `curl -o /dev/null -w '%{http_code}' -H 'X-Sentinel-Api-Key: test-key' http://127.0.0.1:9080/WebGoat/actuator/health` | 0 | **200** |
| `docker compose --profile target down` | 0 | Network removed |
| `env -u SENTINEL_GATEWAY_API_KEY docker compose --profile scan --env-file /dev/null config --quiet` | 0 | scan profile parse OK khi không có key |
| `grep -n ':?' docker-compose.yml` | 1 | Không có `:?` (PASS) |
| `grep -nE 'changeme|API_KEY=(test|dev)|"test"|"dev"|"changeme"' docker-compose.yml` | 1 | Không có default key (PASS) |

**Test mới thêm:**

- `test_compose_invariants.py::test_gateway_image_refuses_empty_api_key` — đọc thật Dockerfile (phải tham
  chiếu `docker-entrypoint.d`) và script guard (phải có `SENTINEL_GATEWAY_API_KEY`, `exit 1`).

**Bất biến đã giữ:** no mock/stub · test không skip · không lộ secret (key giả `test-key` khi cần) · chỉ
Gateway bind loopback · không đụng `reports/week-XX/` · không tự commit · compose không có `:?`/default key.

**Còn fail / chưa chạy được:** Không có — tất cả mục kiểm chứng của lời nhắc đã chạy và đạt.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Hành vi `set -e` + vòng `while read` với pipeline `find | sort | while read`
  trong entrypoint nginx — đã xác nhận bằng source entrypoint và chạy thật (container exited 1). Nhưng
  nếu ai đó override entrypoint thì guard không chạy; đã ghi nhận ở mục 6.
- **Giả định đã đặt:** `00-require-key.sh` chạy trước `20-envsubst-on-templates.sh` nhờ `sort -V` — đúng
  với thứ tự filename; nếu nginx image đổi entrypoint ở version khác thì phải rà lại.
- **Việc còn nợ:** Chưa chạy `make agent-test`/`make gateway-live-test` (cần `.env` có key thật — dùng key
  giả chỉ để kiểm chứng này); chưa commit — chờ người dùng duyệt theo `.agents/rules/git_commit_workflow.md`.
- **Câu hỏi cho người dùng:** Bạn có muốn tôi chạy `make gateway-up` + `make agent-test` với key thật trong
  `.env` để xác nhận toàn bộ live suite không bị ảnh hưởng bởi guard mới không?