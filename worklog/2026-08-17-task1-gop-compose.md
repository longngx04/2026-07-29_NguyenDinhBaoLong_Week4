# Worklog — Task 1: Gộp compose và khoá bất biến mạng bằng test

**Ngày:** 2026-08-17 · **Agent/Model:** opencode · deepseek-v4-flash-free ·
**Branch:** `week4-cont` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 1

---

## 1. Tóm tắt

- Đã gộp `compose.scan.yml` vào `docker-compose.yml` theo hệ profile (`scan`/`target`/`app`) để `make scan`, Gateway + WebGoat và web app dùng chung một compose, tạo nền tảng cho các task sau.
- Phục vụ toàn bộ bản dựng lại Project Sentinel (W1→W6): các task sau đều gọi `docker compose --profile target up`.
- Kết quả: 6/6 test bất biến mạng pass, `make scan` sinh `artifacts/raw/opengrep.json` hợp lệ (23 findings, jq `true`).

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Dọn cơ sở hạ tầng Docker trước khi dựng lại — một file compose duy nhất quản lý 4 service, phân vai bằng profile.
- **Nằm ở đâu trong luồng:** Là task đầu của Plan 1; mọi task sau (2–12) và toàn bộ Plan 2–4 phụ thuộc cấu trúc compose này (`--profile target`/`scan`/`app`).
- **Không có nó thì hỏng gì:** `make scan` vẫn phụ thuộc file `compose.scan.yml` riêng; web (Plan 3–4) chưa có chỗ đứng trong compose; bất biến "WebGoat không bao giờ publish host port" chưa được test khoá lại.
- **Ngoài phạm vi (cố ý không làm):** Không xây nội dung web app thật (chỉ Dockerfile placeholder, chạy `--help`); không chạm các task sau (target doc, probe, bài tập gateway).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `pyproject.toml` | Sửa | Thêm `pyyaml>=6.0` vào `[project.optional-dependencies] dev` | Test đọc YAML compose cần `yaml` |
| `tests/unit/infra/__init__.py` | Tạo | Package marker rỗng | Cho phép `tests/unit/infra` là test package |
| `tests/unit/infra/test_compose_invariants.py` | Tạo | 6 test khoá bất biến: compose.scan bị xoá, đủ 4 service, đúng profile, WebGoat không `ports`, chỉ gateway bind loopback, không service nào bind `0.0.0.0` | Nghiệm thu yêu cầu plan (Step 2) |
| `docker-compose.yml` | Sửa | Thêm service `scanner` (profile `scan`) và `web` (profile `app`); thêm `profiles: ["target"]` cho `webgoat`/`gateway`; giữ nguyên bind `127.0.0.1:9080:8080` | Gộp compose scan vào compose chính theo profile |
| `infra/docker/web/Dockerfile` | Tạo | Placeholder Python 3.12, copy requirements, `CMD python -m project_sentinel.cli --help` | Service `web` phải build được ngay (Step 5); web thật dựng ở Plan 3 |
| `scripts/scan-opengrep.sh` | Sửa | Thay `scan_compose_file` → `compose_file` (`docker-compose.yml`), thêm `--profile scan` | Quét thật dùng compose hợp nhất |
| `Makefile` | Sửa | Thêm `--profile target` vào 7 lệnh `docker compose` (up/down/logs/build/restart) trong `target-up`, `target-down`, `gateway-build`, `gateway-down`, `gateway-live-test` | Compose dùng profile; các target này phải kích hoạt profile `target` |
| `compose.scan.yml` | Xoá | `git rm` toàn bộ | Gộp xong, không còn dùng riêng |
| `requirements.txt` | Sửa | Sinh lại bằng `uv export --locked --extra dev` — thêm `pyyaml==6.0.3` | Đồng bộ dep sau khi thêm pyyaml |
| `uv.lock` | Sửa | `uv lock` thêm `pyyaml v6.0.3` | Khoá phiên bản pyyaml |

**`git diff --stat` (chỉ phần task này):**

```text
 Makefile                                           |   14 +-
 docker-compose.yml                                 |   26 +
 pyproject.toml                                     |    1 +
 requirements.txt                                   |    2 +
 scripts/scan-opengrep.sh                           |    5 +-
 uv.lock                                            |   66 ++
 compose.scan.yml                                   |   Deleted
 tests/unit/infra/                                  |   Untracked (2 file)
 infra/docker/web/Dockerfile                        |   Untracked
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** TDD theo đúng thứ tự plan — viết test bất biến trước, chạy thấy đỏ, rồi mới sửa compose để test xanh. Điều này đảm bảo guardrail mạng được khoá bằng test độc lập với cách implement.

**Luồng dữ liệu:** `docker-compose.yml` (một nguồn duy nhất) → `scripts/scan-opengrep.sh` đọc với `--profile scan` → scanner container chạy OpenGrep → `artifacts/raw/opengrep.json` → test `test_compose_invariants.py` đọc cùng file YAML và kiểm tra cấu trúc.

**Các quyết định kỹ thuật:**

- Dùng `yaml.safe_load` (không `yaml.load`) — không chấp nhận tag tuỳ ý từ file cấu hình.
- Fixture `scope="module"` để chỉ đọc/parse file YAML một lần cho cả 6 test.
- `REPO_ROOT = Path(__file__).resolve().parents[3]` — tính từ `tests/unit/infra/` lên 3 cấp tới repo root, độc lập thư mục làm việc hiện hành.
- Dùng `compose --profile target config --quiet` để xác nhận file compose mới parse hợp lệ.

**Xử lý lỗi / trường hợp biên:** Nếu `pyyaml` chưa cài, test sẽ lỗi import (không skip). Nếu Docker chưa sẵn sàng, `make scan` fail loud. Các test yêu cầu Gateway (`tests/unit/verification`) vẫn fail loud khi thiếu `SENTINEL_GATEWAY_API_KEY` — hành vi bắt buộc của repo (D10), không bị ảnh hưởng bởi task này.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| File config | `docker-compose.yml` | `services: {scanner, webgoat, gateway, web}` | 4 service, profile `scan`/`target`/`app` |
| Test | `test_compose_invariants.py` | `test_*` × 6 | Khoá bất biến mạng và bố cục compose |
| Dockerfile | `infra/docker/web/Dockerfile` | — | Placeholder cho service `web` |
| File script | `scan-opengrep.sh` | — | Quét dùng compose hợp nhất + `--profile scan` |

**Cách chạy:**

```bash
python3 -m pytest tests/unit/infra -v
make scan
jq -e '(.results | type == "array") and (.errors | type == "array")' artifacts/raw/opengrep.json
```

**Output thật (đã che secret):**

```text
$ python3 -m pytest tests/unit/infra -v
tests/unit/infra/test_compose_invariants.py::test_scan_compose_file_is_merged_away PASSED
tests/unit/infra/test_compose_invariants.py::test_all_four_services_exist PASSED
tests/unit/infra/test_compose_invariants.py::test_service_profiles PASSED
tests/unit/infra/test_compose_invariants.py::test_webgoat_is_never_published_on_host PASSED
tests/unit/infra/test_compose_invariants.py::test_only_gateway_binds_loopback PASSED
tests/unit/infra/test_compose_invariants.py::test_no_service_binds_all_interfaces PASSED
============================== 6 passed in 0.04s ===============================

$ make scan
...
Ran 3 rules on 296 files: 23 findings.
OpenGrep report: /home/longngx04/VinSOC/project_sentinel_main/artifacts/raw/opengrep.json

$ jq -e '(...)' artifacts/raw/opengrep.json
true
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Gộp toàn bộ service vào một `docker-compose.yml` với `profiles`, và khoá cấu trúc bằng pytest đọc trực tiếp file YAML.

**Lý do:** Plan Task 1 chỉ định chính xác cấu trúc này (profile `scan`/`target`/`app`, test 6 bất biến). `profiles` của Compose v2 cho phép một file quản lý nhiều nhóm service; spec §5.3 xác nhận topology 4 service. Test đọc YAML trực tiếp phù hợp rule "Real Verification Only" — không mock, kiểm tra đúng file thật.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ `compose.scan.yml` riêng | Không phải đổi script/Makefile | Plan yêu cầu gộp (test `test_scan_compose_file_is_merged_away`), quản lý 2 file dễ lệch cấu hình |
| `docker compose -f docker-compose.yml -f compose.scan.yml` (merge nhiều file) | Tách file theo nhóm | Vẫn giữ 2 file và phức tạp thứ tự merge; profile là cơ chế chính thống của Compose |
| Không thêm `pyyaml` vào dev deps, test parse bằng regex | Không thêm dependency | Parse YAML bằng regex giòn; `pyyaml` là thư viện chuẩn cho việc này, dev dep phù hợp |

**Đánh đổi đã chấp nhận:** Thêm một dev dependency (`pyyaml`) và phải cập nhật `uv.lock`/`requirements.txt` — đổi lại test đọc được cấu trúc YAML chính xác.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `python3 -m pytest tests/unit/infra -v` (trước sửa) | 1 | Đỏ đúng: `test_scan_compose_file_is_merged_away`, `test_all_four_services_exist`, `test_service_profiles` fail |
| `python3 -m pytest tests/unit/infra -v` (sau sửa) | 0 | 6 passed |
| `make scan` | 0 | 23 findings, `OpenGrep report: .../artifacts/raw/opengrep.json` |
| `jq -e '(.results\|type=="array") and (.errors\|type=="array")' artifacts/raw/opengrep.json` | 0 | `true` |
| `python3 -m compileall -q src/project_sentinel` | 0 | — |
| `SENTINEL_GATEWAY_API_KEY=test-key docker compose --profile target config --quiet` | 0 | `COMPOSE_CONFIG_OK` |
| `python3 -m pytest -m "not llm" -q tests/unit` | 1 | 115 passed, 22 errors (tests/unit/verification cần Gateway + key — fail loud do không có `SENTINEL_GATEWAY_API_KEY` trong env; hành vi có sẵn, không phải do task này) |

**Test mới thêm:**

- `tests/unit/infra/test_compose_invariants.py::test_scan_compose_file_is_merged_away` — `compose.scan.yml` không còn tồn tại.
- `tests/unit/infra/test_compose_invariants.py::test_all_four_services_exist` — đúng 4 service `scanner`/`webgoat`/`gateway`/`web`.
- `tests/unit/infra/test_compose_invariants.py::test_service_profiles` — đúng profile `scan`/`target`/`target`/`app`.
- `tests/unit/infra/test_compose_invariants.py::test_webgoat_is_never_published_on_host` — WebGoat không có khoá `ports`.
- `tests/unit/infra/test_compose_invariants.py::test_only_gateway_binds_loopback` — gateway bind đúng `127.0.0.1:9080:8080`.
- `tests/unit/infra/test_compose_invariants.py::test_no_service_binds_all_interfaces` — không service nào bind `0.0.0.0`.

**Bất biến đã giữ:** no mock/stub · test không skip (thiếu dep thì fail) · không lộ secret (chỉ dùng key giả `test-key` để parse compose) · chỉ Gateway bind loopback · không đụng `reports/week-XX/` · không commit tự động.

**Còn fail / chưa chạy được:** `tests/unit/verification` (22 errors) cần `SENTINEL_GATEWAY_API_KEY` + Gateway/WebGoat up — nằm ngoài phạm vi task 1; chạy được khi `make gateway-up` với `.env` có key.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `docker-compose.yml` service `web` — Dockerfile placeholder chạy `python -m project_sentinel.cli --help`; cần `requirements.txt` ở repo root khi build context `.`. Nếu Plan 3 đổi cấu trúc `web` thì chỗ này sẽ được thay.
- **Giả định đã đặt:** Profile `app` cho service `web` giữ nguyên tên từ spec §5.3; `uv` phiên bản 0.11.29 cho `uv lock/export`.
- **Việc còn nợ:** Chưa chạy `make gateway-up`/`make agent-test` (cần `.env` có `SENTINEL_GATEWAY_API_KEY`); chưa commit (đợi người dùng duyệt theo `.agents/rules/git_commit_workflow.md`).
- **Câu hỏi cho người dùng:** Bạn có muốn tôi chạy tiếp `make gateway-up` để kiểm chứng `--profile target` hoạt động thật không? (Cần key `SENTINEL_GATEWAY_API_KEY` trong `.env`.)
