# Mở rộng DAST bằng ZAP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho ZAP quét WebGoat **trong một phiên đã đăng nhập**, rồi dùng bằng chứng runtime đó để đối chiếu với finding SAST và thay lời khai `reachability` của Agent bằng một phép đo.

**Architecture:** Giữ nguyên lane Gateway của `f6d174c`. ZAP vẫn ẩn danh, vẫn GET/HEAD, vẫn không body — **Gateway** mới là thứ giữ session: `gateway-dast` tự lấy `JSESSIONID` lúc khởi động rồi `proxy_set_header Cookie` cho mọi request chuyển tiếp. Bản đồ endpoint đọc từ chính Nginx access log, không thêm hook ZAP.

**Tech Stack:** Python 3.10+, Docker Compose, Nginx 1.27-alpine, OWASP ZAP Baseline, pytest, jq, bash.

**Spec:** [`docs/superpowers/specs/2026-08-22-dast-zap-design.md`](../specs/2026-08-22-dast-zap-design.md)

## Global Constraints

- **Branch:** `feat/zap-dast`. Chạy `git branch --show-current` trước khi chạm file nào. Không `git add -A`.
- **Worklog bắt buộc** sau mỗi task: `worklog/2026-08-22-dast-<task-slug>.md` theo [`worklog/_TEMPLATE.md`](../../../worklog/_TEMPLATE.md), đủ 8 mục, số liệu là output chạy thật.
- **Không mock, không stub.** Test không tới được dependency thì **fail**, không skip (`AGENTS.md` §2.2).
- **Không bịa bằng chứng** (`AGENTS.md` §2.6).
- **Không sửa một assertion nào** trong `tests/unit/gateway/test_dast_gateway_config.py`. Nếu một thay đổi làm nó đỏ thì thay đổi đó sai, không phải test sai.
- **`zap` và `gateway-dast` không bao giờ có khoá `ports`.** Chỉ `gateway` (`127.0.0.1:9080`) và `web` (`127.0.0.1:8000`) bind cổng host.
- **`scripts/scan-zap.sh` không được chứa chuỗi `http://webgoat:8080`** — `test_zap_targets_only_the_dast_gateway` khoá điều này.
- **`JSESSIONID` không được xuất hiện** trong report, access log hay bất kỳ artifact nào.
- Ruff `line-length = 100`, target `py310`. `make lint` và `make typecheck` xanh trước mỗi commit.

## Ràng buộc từ test đang có (đọc trước khi sửa gì)

| Test | Khoá điều gì | Hệ quả |
| :--- | :--- | :--- |
| `test_zap_targets_only_the_dast_gateway` | `scan-zap.sh` không nhắc `webgoat:8080` | Bootstrap session phải ở entrypoint Gateway, không ở script |
| `test_zap_report_came_from_the_gateway_target` | `"webgoat:8080" not in report` | Session không được làm lộ địa chỉ upstream |
| `test_gateway_log_proves_zap_requests_crossed_the_boundary` | parse `path=([^ ]+) ` — **cần khoảng trắng sau path** | Thêm field mới phải đặt **sau** `path=`, không chen vào giữa |
| cùng test trên | path ngoài `/WebGoat/` phải là 403 | Chặn `/WebGoat/logout` bằng 403 là hợp lệ |
| `test_dast_gateway_rejects_post_even_with_the_internal_key` | POST vẫn 405 | Không được nới method |
| `test_zap_normalizer.py::test_alerts_from_...` | `findings[0]["http_method"] == "GET"` | Khi gộp phải **giữ** `http_method` top-level |

---

## File Structure

| File | Trách nhiệm | Task |
| :--- | :--- | :--- |
| `infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh` | Lấy `JSESSIONID`, export cho envsubst | 2 |
| `infra/docker/gateway/Dockerfile` | `COPY` + `chmod 0755` script mới | 2 |
| `infra/docker/gateway/templates/default.conf.template` | `proxy_set_header Cookie`, chặn `/logout` | 2 |
| `infra/docker/gateway/nginx.conf` | Thêm `query=$args` vào log format DAST | 2 |
| `tests/unit/gateway/test_dast_session.py` | Khoá chính sách session | 2 |
| `tests/fixtures/dast/` | Report ZAP thật từ scan **có session** | 3 |
| `src/project_sentinel/ingestion/zap_normalizer.py` | Gộp theo `pluginid`, giữ `instances[]` | 4 |
| `src/project_sentinel/analysis/correlation.py` | Đọc access log, trích route, đối chiếu | 5 |
| `src/project_sentinel/analysis/calibration.py` | Nhận `measured_reachability` | 6 |
| `src/project_sentinel/orchestrator/context.py` | `dast_command` | 7 |
| `src/project_sentinel/orchestrator/steps/ingest.py` | Nhánh DAST + trộn + correlate | 7 |
| `schemas/security-analysis-record.schema.json` | `locations` chấp nhận URL | 8 |
| `src/project_sentinel/analysis/validators.py` | Provenance cho URL | 8 |
| `src/project_sentinel/analysis/evidence.py` | Điều phối bằng chứng | 8 |
| `src/project_sentinel/orchestrator/metrics.py` | `findings_by_tool`, khối `dast` | 9 |

---

## Task 1: Xác minh busybox wget trích được `Set-Cookie`

Spec §3.3 ghi rõ đây là điều **chưa kiểm chứng**. Task này không viết code sản phẩm — nó trả lời một câu hỏi và ghi câu trả lời vào worklog.

**Files:** không tạo file sản phẩm nào. Chỉ worklog.

**Interfaces:**
- Consumes: `gateway-dast`, `webgoat` từ compose hiện có.
- Produces: một quyết định — dùng busybox `wget` hay phải thêm `curl` vào Dockerfile; kèm **lệnh chính xác** đã chạy được.

- [ ] **Step 1: Dựng WebGoat**

```bash
make target-up
```
Expected: `Gateway is ready and WebGoat is healthy on the internal network.`

- [ ] **Step 2: Thử POST đăng ký từ bên trong một container cùng mạng**

```bash
docker compose --profile target run --rm --no-deps \
  --entrypoint sh gateway -c '
    wget -S -O /dev/null \
      --post-data="username=sentinel-probe1&password=sent1nel&matchingPassword=sent1nel&agree=agree" \
      http://webgoat:8080/WebGoat/register.mvc 2>&1 | grep -i "set-cookie"
  '
```

Expected: ít nhất một dòng chứa `Set-Cookie: JSESSIONID=...`.

**Nếu lệnh không ra gì**, thử lần lượt và ghi lại cái nào chạy được:
- Thêm `--header="Content-Type: application/x-www-form-urlencoded"`.
- Bỏ theo redirect: busybox wget đi theo 302 nên header của hop đầu có thể bị lẫn — dùng `--max-redirect=0`.
- Nếu vẫn không được: kết luận **phải thêm `curl`**, ghi vào worklog, và Task 2 dùng `curl` thay `wget`.

- [ ] **Step 3: Xác minh session dùng được thật**

Lấy giá trị `JSESSIONID` vừa nhận, rồi:

```bash
docker compose --profile target run --rm --no-deps \
  --entrypoint sh gateway -c '
    wget -S -O - --header="Cookie: JSESSIONID=<GIA_TRI>" \
      http://webgoat:8080/WebGoat/start.mvc 2>&1 | head -20
  '
```

Expected: HTTP 200 và nội dung **không phải** trang login. Nếu vẫn bị đẩy về `/login` thì session không hợp lệ — vấn đề nằm ở bước đăng ký, phải giải quyết trước khi sang Task 2.

- [ ] **Step 4: Đếm bề mặt ẩn danh để có mốc so sánh**

```bash
jq '[.site[].alerts[].instances[].uri] | unique | length' artifacts/raw/zap.json
```
Ghi con số này vào worklog. Task 3 phải cho ra số **lớn hơn hẳn**; không lớn hơn nghĩa là session không có tác dụng.

- [ ] **Step 5: Viết worklog**

Ghi: lệnh chính xác chạy được, giá trị `Set-Cookie` (che phần giá trị bằng `***`), quyết định wget-hay-curl, và con số mốc ở Step 4.

- [ ] **Step 6: Commit worklog**

```bash
git add worklog/2026-08-22-dast-verify-session-bootstrap.md
git commit -m "docs(worklog): xác minh cách lấy JSESSIONID từ bên trong mạng Docker"
```

---

## Task 2: Gateway giữ session, chặn `/logout`, log thêm query

**Files:**
- Create: `infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh`
- Create: `tests/unit/gateway/test_dast_session.py`
- Modify: `infra/docker/gateway/Dockerfile`
- Modify: `infra/docker/gateway/templates/default.conf.template`
- Modify: `infra/docker/gateway/nginx.conf`

**Interfaces:**
- Produces: biến `SENTINEL_DAST_SESSION` sẵn sàng cho `20-envsubst-on-templates.sh`; log format DAST có thêm field `query=`.

- [ ] **Step 1: Viết test khoá chính sách trước**

`tests/unit/gateway/test_dast_session.py`:

```python
"""Gateway giữ session DAST — ZAP không bao giờ thấy credential.

Lane DAST chặn đăng nhập bằng hai cơ chế (405 cho POST, xoá header của
caller). Thay vì nới chúng, Gateway tự lấy session và tự gắn cookie. Các
test dưới đây khoá đúng ranh giới đó.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY = REPO_ROOT / "infra/docker/gateway"
TEMPLATE = GATEWAY / "templates/default.conf.template"
SESSION_SCRIPT = GATEWAY / "docker-entrypoint.d/16-acquire-dast-session.envsh"
DOCKERFILE = GATEWAY / "Dockerfile"
LIMITS = GATEWAY / "nginx.conf"


def _dast_server() -> str:
    return TEMPLATE.read_text(encoding="utf-8").split("# DAST boundary", 1)[1]


def test_session_script_is_envsh_because_sh_cannot_export():
    # /docker-entrypoint.sh cua nginx SOURCE file .envsh va CHAY file .sh.
    # Dat sai duoi thi export khong toi duoc 20-envsubst-on-templates.sh va
    # cookie se rong — crawl chay an danh nhung van "thanh cong".
    assert SESSION_SCRIPT.suffix == ".envsh"
    assert SESSION_SCRIPT.exists()


def test_session_script_runs_after_local_resolvers_and_before_envsubst():
    prefix = int(SESSION_SCRIPT.name.split("-", 1)[0])
    assert 15 < prefix < 20, f"Thu tu {prefix} phai nam giua 15 va 20"


def test_dockerfile_makes_the_session_script_executable():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "16-acquire-dast-session.envsh" in text
    assert "chmod 0755" in text, "nginx bo qua file .envsh khong co exec bit"


def test_session_script_only_runs_in_dast_mode():
    text = SESSION_SCRIPT.read_text(encoding="utf-8")
    assert "SENTINEL_GATEWAY_MODE" in text
    assert "dast" in text


def test_session_script_fails_loudly_when_it_cannot_authenticate():
    text = SESSION_SCRIPT.read_text(encoding="utf-8")
    assert "exit 1" in text, (
        "Gateway DAST khong session se crawl an danh va van ra report — "
        "kieu hong te nhat vi no trong giong thanh cong"
    )


def test_gateway_injects_the_cookie_itself():
    server = _dast_server()
    assert 'proxy_set_header Cookie "JSESSIONID=${SENTINEL_DAST_SESSION}";' in server


def test_caller_headers_are_still_stripped():
    # Bat bien cu khong duoc mat: ZAP van khong gui duoc header nao qua.
    server = _dast_server()
    assert "proxy_pass_request_headers off;" in server


def test_logout_is_blocked_at_the_gateway():
    server = _dast_server()
    assert "location ^~ /WebGoat/logout" in server
    logout = server.split("location ^~ /WebGoat/logout", 1)[1][:120]
    assert "return 403" in logout
    assert "proxy_pass" not in logout


def test_logout_block_is_declared_before_the_general_webgoat_location():
    server = _dast_server()
    assert server.index("location ^~ /WebGoat/logout") < server.index(
        "location ^~ /WebGoat/ "
    ), "Nginx chon prefix dai nhat, nhung dat truoc cho nguoi doc thay ro y dinh"


def test_dast_log_format_records_the_query_string():
    text = LIMITS.read_text(encoding="utf-8")
    dast_format = text.split("log_format sentinel_dast_access", 1)[1]
    assert "query=$args" in dast_format, (
        "path=$uri khong mang query; ban do endpoint can ten tham so"
    )
    assert dast_format.index("path=$uri") < dast_format.index("query=$args"), (
        "test_gateway_log_proves_zap_requests_crossed_the_boundary parse "
        "`path=([^ ]+) ` nen field moi phai dat SAU path"
    )
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/gateway/test_dast_session.py -v`
Expected: FAIL — script chưa tồn tại, template chưa có cookie.

- [ ] **Step 3: Viết script lấy session**

`infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh`. Thay `wget` bằng `curl` nếu Task 1 kết luận vậy:

```sh
#!/bin/sh
# Lay mot phien WebGoat cho lane DAST.
#
# Vi sao o day va khong o cho khac. Lane DAST chan dang nhap bang hai co che:
# POST bi 405, va proxy_pass_request_headers off xoa cookie cua caller. Ca hai
# dang duoc test khoa. Nen ZAP khong the tu dang nhap — Gateway phai giu phien.
#
# File nay phai co duoi .envsh: /docker-entrypoint.sh SOURCE file .envsh va CHAY
# file .sh, ma bien chi truyen duoc sang 20-envsubst-on-templates.sh khi duoc
# source. Dat sai duoi thi cookie rong va crawl chay an danh trong im lang.

if [ "${SENTINEL_GATEWAY_MODE:-probe}" != "dast" ]; then
    return 0 2>/dev/null || exit 0
fi

_webgoat="${SENTINEL_DAST_UPSTREAM:-http://webgoat:8080/WebGoat}"
# UserForm.java:22-34 — username [a-z0-9-]* dai 6-45, mat khau dai 6-10.
_user="sentinel-$(hexdump -n 4 -e '4/1 "%02x"' /dev/urandom)"
_pass="sent1nel"

# RegistrationController.java:60 goi request.login(...) ngay sau khi tao user,
# nen mot POST la ra JSESSIONID. WebSecurityConfig.java:61 tat CSRF nen khong
# can token.
_headers=$(
    wget -S -O /dev/null \
        --header="Content-Type: application/x-www-form-urlencoded" \
        --post-data="username=${_user}&password=${_pass}&matchingPassword=${_pass}&agree=agree" \
        "${_webgoat}/register.mvc" 2>&1
)

SENTINEL_DAST_SESSION=$(
    printf '%s\n' "$_headers" \
    | sed -n 's/.*[Ss]et-[Cc]ookie: *JSESSIONID=\([^;]*\).*/\1/p' \
    | head -n 1
)

if [ -z "$SENTINEL_DAST_SESSION" ]; then
    echo "Khong lay duoc JSESSIONID tu WebGoat — tu choi khoi dong mot DAST gateway an danh" >&2
    exit 1
fi

export SENTINEL_DAST_SESSION
# KHONG in gia tri session ra log.
echo "DAST gateway da co phien WebGoat cho user ${_user}"
```

- [ ] **Step 4: Sửa Dockerfile**

```dockerfile
FROM nginx:1.27-alpine
COPY docker-entrypoint.d/ /docker-entrypoint.d/
RUN chmod 0755 /docker-entrypoint.d/00-require-key.sh \
               /docker-entrypoint.d/16-acquire-dast-session.envsh
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/00-limits.conf
EXPOSE 8080 8081
```

- [ ] **Step 5: Sửa template**

Trong khối `# DAST boundary`, thay `location ^~ /WebGoat/` bằng hai location, **logout đứng trước**:

```nginx
    # Spider bam trung logout se giet phien dung chung, va toan bo phan con lai
    # cua scan chay an danh nhung van ra report. Chan o Gateway vi do la cho
    # khong caller nao quen duoc.
    location ^~ /WebGoat/logout {
        return 403;
    }

    location ^~ /WebGoat/ {
        limit_req zone=sentinel_dast_rl burst=20 nodelay;
        proxy_set_header Cookie "JSESSIONID=${SENTINEL_DAST_SESSION}";
        proxy_pass http://webgoat:8080;
        proxy_redirect http://webgoat:8080/ http://gateway-dast:8081/;
    }
```

- [ ] **Step 6: Sửa log format**

Trong `infra/docker/gateway/nginx.conf`, chỉ đổi format **DAST**, giữ nguyên format probe:

```nginx
log_format sentinel_dast_access
  '$time_iso8601 channel=dast method=$request_method path=$uri query=$args status=$status '
  'bytes=$body_bytes_sent rt=$request_time';
```

`query=` đặt **sau** `path=` để `re.search(r"path=([^ ]+) ")` trong test live vẫn khớp.

- [ ] **Step 7: Chạy test unit**

Run: `.venv/bin/python -m pytest tests/unit/gateway/ -v`
Expected: PASS toàn bộ, **kể cả `test_dast_gateway_config.py` không sửa dòng nào**.

- [ ] **Step 8: Dựng và chạy thật**

```bash
docker compose --profile dast build gateway-dast
SENTINEL_DAST_API_KEY=$(openssl rand -hex 32) \
  docker compose --profile dast up --detach gateway-dast webgoat
docker compose --profile dast logs gateway-dast | grep -i "phien WebGoat"
```
Expected: dòng `DAST gateway da co phien WebGoat cho user sentinel-xxxxxxxx`, **không có giá trị session nào trong log**.

- [ ] **Step 9: Khẳng định cookie thật sự tới WebGoat**

```bash
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    http://127.0.0.1:8081/WebGoat/start.mvc 2>&1 | head -30'
```
Expected: HTTP 200, nội dung **không phải** trang login. Đây là bằng chứng session có tác dụng.

- [ ] **Step 10: Khẳng định logout bị chặn**

```bash
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O /dev/null --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    http://127.0.0.1:8081/WebGoat/logout 2>&1 | grep -E "HTTP/"'
```
Expected: `403`.

- [ ] **Step 11: Commit**

```bash
git add infra/docker/gateway/ tests/unit/gateway/test_dast_session.py
git commit -m "feat(dast): Gateway giữ phiên WebGoat, chặn logout, log thêm query"
```

---

## Task 3: Scan thật có session — ghi fixture mới

**Files:**
- Create: `tests/fixtures/dast/zap-alerts-authenticated.json`
- Create: `tests/fixtures/dast/gateway-access-authenticated.log`
- Modify: `tests/fixtures/dast/README.md` (tạo nếu chưa có)

**Interfaces:**
- Produces: fixture thật cho Task 4 và Task 5.

- [ ] **Step 1: Chạy DAST đầu-cuối**

```bash
make dast
```
Expected: exit 0, in ra đường dẫn report và evidence log.

- [ ] **Step 2: So bề mặt với mốc ẩn danh ở Task 1 Step 4**

```bash
jq '[.site[].alerts[].instances[].uri] | unique | length' artifacts/raw/zap.json
jq -r '[.site[].alerts[].instances[].uri] | unique | .[]' artifacts/raw/zap.json \
  | grep -vE '/(login|registration|register\.mvc|css|js|images|fonts|plugins|favicon)' \
  | head -30
```

Số thứ nhất **phải lớn hơn hẳn** mốc Task 1. Danh sách thứ hai **phải khác rỗng** — nếu rỗng thì session không có tác dụng, quay lại Task 2, **đừng đi tiếp**.

- [ ] **Step 3: Khẳng định session không rò ra artifact**

```bash
grep -c "JSESSIONID" artifacts/raw/zap.json artifacts/dast/gateway-access.log || echo "sach"
```
Expected: `sach` hoặc `0`. Có thì phải che trước khi commit và mở một task sửa rò.

- [ ] **Step 4: Lưu fixture**

```bash
mkdir -p tests/fixtures/dast
cp artifacts/raw/zap.json tests/fixtures/dast/zap-alerts-authenticated.json
cp artifacts/dast/gateway-access.log tests/fixtures/dast/gateway-access-authenticated.log
```

- [ ] **Step 5: Ghi provenance**

`tests/fixtures/dast/README.md`:

```markdown
# Fixture DAST

Mọi file ở đây là **output thật đã ghi lại**, không phải JSON viết tay. Repo cấm
mock (`AGENTS.md` §2.2), nên test đọc lại chính output thật này.

| File | Sinh ra bằng | Ngày |
| :--- | :--- | :--- |
| `zap-alerts-authenticated.json` | `make dast` với Gateway giữ phiên WebGoat | 2026-08-22 |
| `gateway-access-authenticated.log` | Access log `gateway-dast` của cùng lần chạy | 2026-08-22 |

Chép lại: xem `docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md` Task 3.
```

- [ ] **Step 6: Quét secret lần cuối**

```bash
grep -riE "jsessionid|x-sentinel-dast-key|password=|api[_-]?key" tests/fixtures/dast/ || echo "sach"
```
Expected: `sach`.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/dast/
git commit -m "test(dast): fixture từ lần quét thật có phiên đăng nhập"
```

---

## Task 4: Gộp finding theo loại alert

Phải xong **trước** khi bất kỳ thứ gì đọc `zap-findings.json` ở quy mô có session.

**Files:**
- Modify: `src/project_sentinel/ingestion/zap_normalizer.py`
- Modify: `tests/unit/ingestion/test_zap_normalizer.py`

**Interfaces:**
- Produces: `normalize_zap_report(raw, *, max_instances: int = 20) -> list[dict]`
- Mỗi finding thêm `instances: list[dict]` và `instances_total: int`.
- **Giữ nguyên** `http_method` và `parameter` top-level (lấy từ instance đầu) — test hiện có phụ thuộc vào chúng.

- [ ] **Step 1: Thêm test mới vào file test đang có**

Thêm vào cuối `tests/unit/ingestion/test_zap_normalizer.py`:

```python
def _report_many_urls(count: int) -> dict:
    """Mot alert cau hinh trai tren nhieu URL — dung canh WebGoat that.

    WebSecurityConfig.java:62 goi headers.disable(), nen alert thieu security
    header ban tren MOI URL. Mot-finding-mot-URL se lam no findings.json.
    """
    return {
        "@version": "2.17.0",
        "site": [
            {
                "@name": "http://gateway-dast:8081",
                "alerts": [
                    {
                        "pluginid": "10021",
                        "alert": "X-Content-Type-Options Header Missing",
                        "riskcode": "1",
                        "confidence": "2",
                        "desc": "<p>Missing header.</p>",
                        "solution": "<p>Set nosniff.</p>",
                        "cweid": "693",
                        "instances": [
                            {
                                "uri": f"http://gateway-dast:8081/WebGoat/lesson{i}",
                                "method": "GET",
                                "param": "",
                            }
                            for i in range(count)
                        ],
                    }
                ],
            }
        ],
    }


def test_one_alert_type_yields_one_finding_regardless_of_url_count():
    findings = normalize_zap_report(_report_many_urls(300))
    assert len(findings) == 1, (
        "Gop theo pluginid: 300 URL khong duoc thanh 300 finding"
    )


def test_instances_are_capped_but_the_true_total_is_kept():
    findings = normalize_zap_report(_report_many_urls(300))
    assert len(findings[0]["instances"]) == 20
    assert findings[0]["instances_total"] == 300


def test_the_cap_is_configurable():
    findings = normalize_zap_report(_report_many_urls(300), max_instances=5)
    assert len(findings[0]["instances"]) == 5
    assert findings[0]["instances_total"] == 300


def test_each_instance_keeps_url_method_and_param():
    findings = normalize_zap_report(_report_many_urls(3))
    instance = findings[0]["instances"][0]
    assert instance["url"].startswith("http://gateway-dast:8081/WebGoat/")
    assert instance["method"] == "GET"
    assert "param" in instance


def test_gateway_filter_still_runs_per_instance_before_grouping():
    report = _report_many_urls(2)
    report["site"][0]["alerts"][0]["instances"].append(
        {"uri": "http://webgoat:8080/WebGoat/direct", "method": "GET", "param": ""}
    )
    findings = normalize_zap_report(report)
    urls = [item["url"] for item in findings[0]["instances"]]
    assert all("gateway-dast" in url for url in urls)
    assert findings[0]["instances_total"] == 2


def test_two_alert_types_stay_two_findings():
    report = _report_many_urls(2)
    second = dict(report["site"][0]["alerts"][0])
    second["pluginid"] = "10038"
    second["alert"] = "CSP Header Not Set"
    report["site"][0]["alerts"].append(second)
    assert len(normalize_zap_report(report)) == 2
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/ingestion/test_zap_normalizer.py -v`
Expected: các test cũ PASS, các test mới FAIL (`KeyError: 'instances'`).

- [ ] **Step 3: Sửa `normalize_zap_report`**

Thay thân vòng lặp. Giữ nguyên `_was_forwarded_by_dast_gateway`, `_fingerprint`, `_plain_text`, `_cwe`, `RISK`, `CONFIDENCE`:

```python
DEFAULT_MAX_INSTANCES = 20


def normalize_zap_report(
    raw: dict[str, Any], *, max_instances: int = DEFAULT_MAX_INSTANCES
) -> list[dict[str, Any]]:
    """Gop alert ZAP theo pluginid, tra danh sach finding schema chung.

    Gop theo LOAI alert chu khong theo instance. WebGoat goi headers.disable()
    (WebSecurityConfig.java:62) nen alert thieu security header ban tren moi
    URL; quet co phien ra hang tram URL, va mot-finding-mot-URL se lam no
    findings.json va dot token o buoc analyze.
    """
    if not isinstance(raw, dict):
        raise ValueError("ZAP report must be a JSON object")
    sites = raw.get("site")
    if not isinstance(sites, list):
        raise ValueError("ZAP report missing site array")

    version = str(raw.get("@version") or raw.get("version") or "unknown")
    grouped: dict[str, dict[str, Any]] = {}

    for site in sites:
        if not isinstance(site, dict):
            continue
        alerts = site.get("alerts")
        if not isinstance(alerts, list):
            raise ValueError("ZAP site entry missing alerts array")
        site_url = str(site.get("@name") or "")

        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            plugin_id = str(alert.get("pluginid") or alert.get("alertRef") or "unknown")

            instances = alert.get("instances")
            if not isinstance(instances, list) or not instances:
                instances = [{"uri": site_url, "method": "GET", "param": ""}]

            bucket = grouped.setdefault(
                plugin_id,
                {"alert": alert, "instances": [], "seen": set()},
            )

            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                uri = str(instance.get("uri") or site_url)
                method = str(instance.get("method") or "GET").upper()
                # Loc TRUOC khi gop: trang 401/403 cua chinh Gateway khong
                # duoc tinh thanh lo hong cua WebGoat.
                if not _was_forwarded_by_dast_gateway(method, uri):
                    continue
                parameter = str(instance.get("param") or "")
                fingerprint = _fingerprint(plugin_id, method, uri, parameter)
                if fingerprint in bucket["seen"]:
                    continue
                bucket["seen"].add(fingerprint)
                bucket["instances"].append(
                    {
                        "url": uri,
                        "method": method,
                        "param": parameter,
                        "fingerprint": fingerprint,
                    }
                )

    findings: list[dict[str, Any]] = []
    for plugin_id, bucket in sorted(grouped.items()):
        collected = bucket["instances"]
        if not collected:
            continue
        alert = bucket["alert"]
        first = collected[0]
        title = _plain_text(alert.get("alert") or alert.get("name") or plugin_id)
        description = _plain_text(alert.get("desc") or alert.get("description"))
        solution = _plain_text(alert.get("solution"))
        message = description
        if solution:
            message = f"{description} Recommended fix: {solution}".strip()

        findings.append(
            {
                "id": f"zap-{plugin_id}-{first['fingerprint'][:10]}",
                "tool": "zap",
                "tool_version": version,
                "severity": RISK.get(str(alert.get("riskcode")), "low"),
                "file_or_url": first["url"],
                "line": 0,
                "title": title or f"ZAP alert {plugin_id}",
                "rule_id": plugin_id,
                "cwe": _cwe(alert.get("cweid")),
                "owasp": [],
                "message": message or title,
                "confidence": CONFIDENCE.get(str(alert.get("confidence")), "medium"),
                "fingerprint": first["fingerprint"],
                "raw_check_id": plugin_id,
                # Giu hai truong nay o top-level: test hien co phu thuoc vao
                # chung, va chung van dung nghia — thuoc ve instance dai dien.
                "http_method": first["method"],
                "parameter": first["param"],
                "instances": [
                    {k: v for k, v in item.items() if k != "fingerprint"}
                    for item in collected[:max_instances]
                ],
                "instances_total": len(collected),
            }
        )

    return findings
```

- [ ] **Step 4: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/ingestion/test_zap_normalizer.py -v`
Expected: PASS toàn bộ — **cả test cũ lẫn test mới**, không sửa một test cũ nào.

- [ ] **Step 5: Chạy trên fixture thật**

```bash
.venv/bin/python -c "
import json
from project_sentinel.ingestion.zap_normalizer import normalize_zap_report
raw = json.load(open('tests/fixtures/dast/zap-alerts-authenticated.json'))
f = normalize_zap_report(raw)
print('finding:', len(f), '| instance tong:', sum(x['instances_total'] for x in f))
for item in f[:5]:
    print(' ', item['rule_id'], item['severity'], item['instances_total'], item['title'][:40])
"
```
Dán output vào worklog. So với 25 finding của lần ẩn danh.

- [ ] **Step 6: Lint, typecheck, toàn bộ test**

```bash
make lint && make typecheck
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
```

- [ ] **Step 7: Commit**

```bash
git add src/project_sentinel/ingestion/zap_normalizer.py \
        tests/unit/ingestion/test_zap_normalizer.py
git commit -m "feat(dast): gộp finding ZAP theo loại alert, giữ instances đã cắt"
```

---

## Task 5: Đọc bản đồ endpoint và đối chiếu SAST ↔ DAST

**Files:**
- Create: `src/project_sentinel/analysis/correlation.py`
- Test: `tests/unit/analysis/test_correlation.py`

**Interfaces:**
- Produces:
  - `parse_gateway_access_log(path: Path) -> dict` → `{"endpoints": [{"method", "path", "params"}]}`
  - `extract_route(source_path: Path) -> str | None`
  - `correlate(findings, endpoints, *, project_root: Path) -> list[dict]`
  - `STRENGTHS: tuple[str, ...]`

- [ ] **Step 1: Tìm một file WebGoat thật có annotation**

```bash
grep -rln "@PostMapping\|@GetMapping" \
  benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/ | head -5
```
Chọn một file, rồi `grep -n "@RequestMapping\|@PostMapping\|@GetMapping\|class "` trên nó. **Ghi đường dẫn và route thật vào worklog** — test ở Step 2 dùng giá trị thật, không phải ví dụ bịa.

- [ ] **Step 2: Viết test fail trước**

`tests/unit/analysis/test_correlation.py`:

```python
"""Noi finding tinh voi endpoint runtime ma ZAP that su cham toi.

Doi chieu la thao tac TAT DINH, doc file, khong hoi LLM. Chinh vi vay ket qua
cua no du tin de ghi de truong reachability ma Agent tu khai.
"""

from pathlib import Path

import pytest

from project_sentinel.analysis.correlation import (
    STRENGTHS,
    correlate,
    extract_route,
    parse_gateway_access_log,
)

REPO = Path(__file__).resolve().parents[3]
LOG_FIXTURE = REPO / "tests/fixtures/dast/gateway-access-authenticated.log"


# ---------- parse_gateway_access_log ----------

def test_parses_method_path_and_query_from_a_real_log(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=GET "
        "path=/WebGoat/SqlInjection/attack5a query=account=x&op=1 status=200 "
        "bytes=12 rt=0.01\n"
        "2026-08-22T09:00:01+00:00 channel=dast method=GET "
        "path=/WebGoat/login query=- status=200 bytes=9 rt=0.01\n",
        encoding="utf-8",
    )
    result = parse_gateway_access_log(log)
    by_path = {item["path"]: item for item in result["endpoints"]}
    assert by_path["/WebGoat/SqlInjection/attack5a"]["params"] == ["account", "op"]
    assert by_path["/WebGoat/login"]["params"] == []


def test_non_dast_lines_are_ignored(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "nginx khoi dong\n"
        "2026-08-22T09:00:00+00:00 method=GET path=/WebGoat/x status=200 "
        "bytes=1 rt=0.01\n",
        encoding="utf-8",
    )
    assert parse_gateway_access_log(log)["endpoints"] == []


def test_blocked_requests_are_not_counted_as_reachable(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=GET "
        "path=/WebGoat/logout query=- status=403 bytes=0 rt=0.01\n",
        encoding="utf-8",
    )
    assert parse_gateway_access_log(log)["endpoints"] == [], (
        "403 nghia la Gateway chan, khong phai endpoint cham toi duoc"
    )


def test_a_missing_log_is_an_empty_map_not_a_crash(tmp_path):
    assert parse_gateway_access_log(tmp_path / "khong-co.log") == {"endpoints": []}


def test_the_real_fixture_log_parses():
    assert LOG_FIXTURE.is_file(), "Task 3 phai sinh fixture nay truoc"
    result = parse_gateway_access_log(LOG_FIXTURE)
    assert result["endpoints"], "Log that phai co it nhat mot endpoint"


# ---------- extract_route ----------

@pytest.fixture
def lesson(tmp_path):
    src = tmp_path / "src" / "Lesson.java"
    src.parent.mkdir(parents=True)
    src.write_text(
        '@RequestMapping("/SqlInjection")\n'
        'public class Lesson {\n'
        '  @PostMapping("/attack5a")\n'
        '  public void attack() {}\n'
        '}\n',
        encoding="utf-8",
    )
    return tmp_path


def test_class_mapping_is_prefixed_to_method_mapping(lesson):
    assert extract_route(lesson / "src" / "Lesson.java") == "/SqlInjection/attack5a"


def test_a_file_without_mapping_returns_none(tmp_path):
    plain = tmp_path / "Plain.java"
    plain.write_text("public class Plain { void x() {} }", encoding="utf-8")
    assert extract_route(plain) is None


def test_a_missing_file_returns_none_rather_than_raising(tmp_path):
    assert extract_route(tmp_path / "KhongCoThat.java") is None


# ---------- correlate ----------

def _endpoints(*paths):
    return {"endpoints": [{"method": "GET", "path": p, "params": []} for p in paths]}


def test_route_reached_by_zap_is_reachable(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    out = correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
                    project_root=lesson)
    evidence = out[0]["runtime_evidence"]
    assert evidence["route"] == "/SqlInjection/attack5a"
    assert evidence["strength"] == "reachable"


def test_route_zap_never_reached(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    out = correlate(findings, _endpoints("/WebGoat/login"), project_root=lesson)
    assert out[0]["runtime_evidence"]["strength"] == "route_known_not_reached"


def test_no_route_when_the_file_declares_none(tmp_path):
    plain = tmp_path / "Plain.java"
    plain.write_text("public class Plain {}", encoding="utf-8")
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "Plain.java", "line": 1}]
    out = correlate(findings, _endpoints(), project_root=tmp_path)
    assert out[0]["runtime_evidence"]["strength"] == "no_route"


def test_a_zap_alert_on_the_same_route_upgrades_to_alerted(lesson):
    findings = [
        {"id": "opengrep-001", "tool": "opengrep",
         "file_or_url": "src/Lesson.java", "line": 4},
        {"id": "zap-10021-abc", "tool": "zap", "instances": [
            {"url": "http://gateway-dast:8081/WebGoat/SqlInjection/attack5a",
             "method": "GET", "param": ""}]},
    ]
    out = correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
                    project_root=lesson)
    evidence = next(f for f in out if f["id"] == "opengrep-001")["runtime_evidence"]
    assert evidence["strength"] == "reachable_and_alerted"
    assert evidence["dast_alerts"] == ["zap-10021-abc"]


def test_zap_findings_get_no_runtime_evidence_block(lesson):
    out = correlate([{"id": "zap-1", "tool": "zap", "instances": []}],
                    _endpoints(), project_root=lesson)
    assert "runtime_evidence" not in out[0], (
        "Finding dong DA LA bang chung runtime; gan them la vong lap vo nghia"
    )


def test_the_input_list_is_not_mutated(lesson):
    findings = [{"id": "opengrep-001", "tool": "opengrep",
                 "file_or_url": "src/Lesson.java", "line": 4}]
    correlate(findings, _endpoints("/WebGoat/SqlInjection/attack5a"),
              project_root=lesson)
    assert "runtime_evidence" not in findings[0]


def test_strengths_are_ordered_weakest_first():
    assert STRENGTHS[0] == "no_route"
    assert STRENGTHS[-1] == "reachable_and_alerted"
```

- [ ] **Step 3: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Viết module**

`src/project_sentinel/analysis/correlation.py`:

```python
"""Noi finding tinh voi endpoint runtime ma ZAP that su cham toi.

Vi sao can. Finding SAST la `SqlInjectionLesson5a.java:47`; endpoint DAST la
`/WebGoat/SqlInjection/attack5a`. Khong co gi noi hai thu do mot cach hien
nhien. Cau noi la annotation route trong chinh file chua finding — trich ra
duoc bang cach doc file, tat dinh, khong hoi LLM.

Ban do endpoint doc tu Nginx access log chu khong tu ZAP. Do la bang chung o
tang ha tang, cung nguyen tac ma scripts/scan-zap.sh dang dung de chung minh
traffic da di qua Gateway.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

STRENGTHS: tuple[str, ...] = (
    "no_route",
    "route_known_not_reached",
    "reachable",
    "reachable_and_alerted",
)

_LOG_LINE = re.compile(
    r"channel=dast\s+method=(?P<method>\S+)\s+path=(?P<path>\S+)\s+"
    r"query=(?P<query>\S*)\s+status=(?P<status>\d+)"
)
_CLASS_MAPPING = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]+)"')
_METHOD_MAPPING = re.compile(
    r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?"([^"]+)"'
)
_MAX_BYTES = 512 * 1024


def parse_gateway_access_log(path: str | Path) -> dict[str, Any]:
    """Doc ban do endpoint tu access log cua lane DAST.

    Chi tinh request Gateway that su chuyen tiep: status 4xx/5xx nghia la
    Gateway chan hoac upstream tu choi, khong phai mot endpoint cham toi duoc.
    """
    source = Path(path)
    if not source.is_file():
        return {"endpoints": []}

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _LOG_LINE.search(line)
        if not match:
            continue
        status = int(match.group("status"))
        if status >= 400:
            continue
        method = match.group("method").upper()
        route = match.group("path")
        query = match.group("query")
        params = (
            sorted(urllib.parse.parse_qs(query).keys())
            if query and query != "-"
            else []
        )
        key = (method, route)
        if key in seen:
            merged = sorted(set(seen[key]["params"]) | set(params))
            seen[key]["params"] = merged
            continue
        seen[key] = {"method": method, "path": route, "params": params}

    return {"endpoints": [seen[key] for key in sorted(seen)]}


def _join(prefix: str | None, suffix: str) -> str:
    if not prefix:
        return "/" + suffix.lstrip("/")
    return "/" + prefix.strip("/") + "/" + suffix.lstrip("/")


def extract_route(source_path: str | Path) -> str | None:
    """Tra route Spring khai trong file, hoac None neu khong co.

    Doc co gioi han kich thuoc: mot file khong lo khong duoc lam treo buoc
    normalize. Khong doc duoc thi tra None — thieu bang chung, khong phai loi.
    """
    path = Path(source_path)
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    class_match = _CLASS_MAPPING.search(text)
    class_prefix = class_match.group(1) if class_match else None

    for match in _METHOD_MAPPING.finditer(text):
        if class_match and match.start() == class_match.start():
            continue
        return _join(class_prefix, match.group(1))

    return _join(None, class_prefix) if class_prefix else None


def _route_matches(route: str, observed: set[str]) -> str | None:
    """Route khai trong code la tuong doi voi context path (/WebGoat)."""
    suffix = "/" + route.strip("/")
    for path in observed:
        if path == suffix or path.endswith(suffix):
            return path
    return None


def correlate(
    findings: list[dict[str, Any]],
    endpoints: dict[str, Any],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    """Gan khoi `runtime_evidence` vao moi finding TINH. Khong sua input."""
    observed = {
        str(item.get("path") or "")
        for item in endpoints.get("endpoints") or []
        if item.get("path")
    }

    alerts_by_path: dict[str, list[str]] = {}
    for finding in findings:
        if str(finding.get("tool")) != "zap":
            continue
        for instance in finding.get("instances") or []:
            route = urllib.parse.urlsplit(str(instance.get("url") or "")).path
            if route:
                alerts_by_path.setdefault(route, []).append(str(finding["id"]))

    result: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        if str(finding.get("tool")) == "zap":
            # Finding dong DA LA bang chung runtime.
            result.append(item)
            continue

        relative = str(finding.get("file_or_url") or "")
        route = extract_route(project_root / relative) if relative else None

        if not route:
            item["runtime_evidence"] = {
                "route": None, "route_source": None, "observed": None,
                "strength": "no_route", "dast_alerts": [],
            }
            result.append(item)
            continue

        matched = _route_matches(route, observed)
        alerts = sorted(set(alerts_by_path.get(matched, []))) if matched else []
        if matched and alerts:
            strength = "reachable_and_alerted"
        elif matched:
            strength = "reachable"
        else:
            strength = "route_known_not_reached"

        item["runtime_evidence"] = {
            "route": route,
            "route_source": relative,
            "observed": matched,
            "strength": strength,
            "dast_alerts": alerts,
        }
        result.append(item)
    return result


__all__ = ["STRENGTHS", "correlate", "extract_route", "parse_gateway_access_log"]
```

- [ ] **Step 5: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v`
Expected: PASS. Nếu ca thử trên file WebGoat thật fail, sửa regex theo hình dạng thật — **đừng sửa test cho khớp code sai**.

- [ ] **Step 6: Chạy trên dữ liệu thật**

```bash
.venv/bin/python -c "
from pathlib import Path
from project_sentinel.analysis.correlation import parse_gateway_access_log
m = parse_gateway_access_log('tests/fixtures/dast/gateway-access-authenticated.log')
print('endpoint:', len(m['endpoints']))
for e in m['endpoints'][:10]: print(' ', e['method'], e['path'], e['params'])
"
```
Dán output vào worklog.

- [ ] **Step 7: Commit**

```bash
git add src/project_sentinel/analysis/correlation.py \
        tests/unit/analysis/test_correlation.py
git commit -m "feat(dast): đọc bản đồ endpoint từ access log và đối chiếu với finding tĩnh"
```

---

## Task 6: `reachability` do Python đo

Task này **đổi một bất biến đã ghi thành văn**. Docstring đầu `calibration.py` viết *"Chỉ hạ, không bao giờ nâng"*. Phép đo có thể **nâng** `reachability`. Sửa docstring là phần bắt buộc của task, không phải việc dọn dẹp tuỳ hứng.

**Files:**
- Modify: `src/project_sentinel/analysis/calibration.py`
- Test: `tests/unit/analysis/test_calibration_measured.py`

**Interfaces:**
- Produces: `calibrate_record(record, *, measured_reachability: str | None = None)` — keyword-only, mặc định `None` nên mọi lời gọi cũ giữ nguyên hành vi.
- `Calibration.rules` có thêm giá trị `"reachability_measured"`.

- [ ] **Step 1: Viết test fail trước**

`tests/unit/analysis/test_calibration_measured.py`:

```python
"""reachability do duoc tu Python ghi de gia tri Agent tu khai."""

from project_sentinel.analysis.calibration import calibrate_record


def _record(**over):
    base = {
        "disposition": "confirmed", "severity": "high",
        "attacker_control": "proven", "reachability": "not_proven",
        "explanation": "", "confidence_rationale": "",
    }
    base.update(over)
    return base


def test_without_a_measurement_nothing_changes():
    after, calibration = calibrate_record(_record())
    assert after["reachability"] == "not_proven"
    assert "reachability_measured" not in calibration.rules


def test_a_measurement_overwrites_what_the_agent_claimed():
    after, calibration = calibrate_record(_record(), measured_reachability="proven")
    assert after["reachability"] == "proven"
    assert "reachability_measured" in calibration.rules


def test_measurement_can_contradict_the_agent_downward():
    after, _ = calibrate_record(
        _record(reachability="proven"), measured_reachability="not_proven"
    )
    assert after["reachability"] == "not_proven"


def test_confirmed_survives_when_both_proofs_hold():
    after, calibration = calibrate_record(_record(), measured_reachability="proven")
    assert after["disposition"] == "confirmed"
    assert "confirmed_requires_proof" not in calibration.rules


def test_confirmed_still_falls_when_attacker_control_is_missing():
    after, calibration = calibrate_record(
        _record(attacker_control="not_proven"), measured_reachability="proven"
    )
    assert after["disposition"] == "needs_review", (
        "DAST baseline chung minh reachability, KHONG chung minh attacker control"
    )
    assert "confirmed_requires_proof" in calibration.rules


def test_an_invalid_measurement_is_ignored():
    after, calibration = calibrate_record(_record(), measured_reachability="chac-chan")
    assert after["reachability"] == "not_proven"
    assert "reachability_measured" not in calibration.rules


def test_a_measurement_equal_to_the_claim_leaves_no_trace():
    after, calibration = calibrate_record(
        _record(reachability="proven"), measured_reachability="proven"
    )
    assert after["reachability"] == "proven"
    assert "reachability_measured" not in calibration.rules
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_calibration_measured.py -v`
Expected: FAIL — `unexpected keyword argument 'measured_reachability'`.

- [ ] **Step 3: Sửa docstring bất biến**

Trong `calibration.py`, thay hai gạch đầu dòng nguyên tắc đầu file bằng:

```python
- **Chi ha dua tren van xuoi cua Agent.** Moi luat doc output cua Agent chi
  duoc ha cap; mot luat sai chi lam mat do nhay, khong bao gio tu tao ra mot
  "confirmed" gia.
- **Truong DO DUOC thi lay so do, ca khi so do cao hon.** `reachability` khong
  con la thu Agent duoc phep tu khai: `correlation.py` tinh no bang cach doi
  chieu route khai trong source voi endpoint ZAP that su cham toi. Day khong
  phai nang ket luan cua Agent — day la thay mot loi khai bang mot phep do.
  Cung ly do khoi `calibration` do Agent tu sinh bi bo di.
```

- [ ] **Step 4: Sửa chữ ký và thêm luật**

```python
def calibrate_record(
    record: dict[str, Any], *, measured_reachability: str | None = None
) -> tuple[dict[str, Any], Calibration]:
```

Ngay sau `reachability = result.get("reachability")`, **trước** khối `if disposition not in DISPOSITIONS: return`:

```python
    # Phep do thang loi khai. Gia tri la thi bo qua, khong ghi bua vao record.
    if measured_reachability in PROOF_VALUES and measured_reachability != reachability:
        result["reachability"] = measured_reachability
        reachability = measured_reachability
        calibration.rules.append("reachability_measured")
```

- [ ] **Step 5: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_calibration_measured.py -v`
Expected: PASS.

- [ ] **Step 6: Khẳng định test calibration cũ không đổi**

Run: `.venv/bin/python -m pytest tests/unit/analysis -v -k calibration`
Expected: mọi test cũ vẫn xanh — vì `measured_reachability` mặc định `None`.

- [ ] **Step 7: Nối vào nơi gọi**

```bash
grep -rn "calibrate_record" src/project_sentinel/
```
Ở nơi pipeline gọi, tra `runtime_evidence.strength` của các finding trong `source_finding_ids`:

```python
    strengths = {
        (f.get("runtime_evidence") or {}).get("strength")
        for f in findings
        if f.get("id") in record.get("source_finding_ids", [])
    }
    if strengths & {"reachable", "reachable_and_alerted"}:
        measured = "proven"
    elif strengths & {"route_known_not_reached"}:
        measured = "not_proven"
    else:
        measured = None
    calibrated, calibration = calibrate_record(record, measured_reachability=measured)
```

`no_route` cho `None` — không đo được thì không khai, giữ nguyên lời Agent.

- [ ] **Step 8: Commit**

```bash
git add src/project_sentinel/analysis/calibration.py \
        tests/unit/analysis/test_calibration_measured.py
git commit -m "feat(dast): reachability lấy từ phép đo của Python thay vì lời khai của Agent"
```

---

## Task 7: Nối DAST vào luồng chín bước

**Files:**
- Modify: `src/project_sentinel/orchestrator/context.py`
- Modify: `src/project_sentinel/orchestrator/steps/ingest.py`
- Test: `tests/unit/orchestrator/test_step_scan_dast.py`

**Interfaces:**
- Produces: `RunContext.dast_command: list[str]`; `step_scan` ghi `detail["dast"]` ∈ `{"done","skipped"}`; `step_normalize` trộn ZAP và gọi `correlate`.

- [ ] **Step 1: Viết test fail trước**

`tests/unit/orchestrator/test_step_scan_dast.py`:

```python
"""Nhanh DAST trong step_scan.

SAST la xuong song: DAST hong thi buoc van xong. May dev khong Docker van
phai chay duoc run. Test dung script that trong tmp_path, khong mock.
"""

import json
import stat

import pytest

from project_sentinel.orchestrator.context import RunContext
from project_sentinel.orchestrator.state import new_run
from project_sentinel.orchestrator.steps.ingest import step_scan

RAW = {"version": "1.0", "results": [], "errors": []}


def _script(path, body):
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.fixture
def ctx_and_record(tmp_path):
    record = new_run(tmp_path / "runs")
    scan = _script(
        tmp_path / "scan.sh", f"printf '%s' '{json.dumps(RAW)}' > \"$1\"\n"
    )
    ctx = RunContext.default(tmp_path).replace(scan_command=[scan])
    return ctx, record


def test_dast_success_is_recorded_as_done(tmp_path, ctx_and_record):
    ctx, record = ctx_and_record
    dast = _script(
        tmp_path / "dast.sh",
        'printf \'{"site":[]}\' > "$1"\nprintf \'log\\n\' > "$2"\n',
    )
    result = step_scan(record, ctx.replace(dast_command=[dast]))
    assert result.step("scan").detail["dast"] == "done"
    assert (record.root / "zap-alerts.json").exists()
    assert (record.root / "gateway-access.log").exists()


def test_dast_failure_does_not_fail_the_scan_step(tmp_path, ctx_and_record):
    ctx, record = ctx_and_record
    dast = _script(tmp_path / "dast.sh", 'echo "khong co docker" >&2\nexit 127\n')
    result = step_scan(record, ctx.replace(dast_command=[dast]))
    assert result.step("scan").status == "done", "SAST xong thi buoc phai xong"
    assert result.step("scan").detail["dast"] == "skipped"
    assert result.step("scan").detail["dast_reason"]
    assert (record.root / "raw.json").exists(), "raw.json van phai ra"


def test_no_dast_command_means_skipped_not_error(ctx_and_record):
    ctx, record = ctx_and_record
    result = step_scan(record, ctx.replace(dast_command=[]))
    assert result.step("scan").status == "done"
    assert result.step("scan").detail["dast"] == "skipped"
```

Va them mot test cho viec chuan hoa truong, vao cung file:

```python
def test_cwe_and_owasp_are_normalised_to_lists_after_merging(tmp_path):
    """Hai normalizer cho hai hinh dang; sau khi tron chi duoc con mot.

    zap_normalizer cho cwe: ["CWE-693"], normalizer.py cua OpenGrep cho gia
    tri vo huong tu metadata. De ca hai vao findings.json thi moi thu doc no
    ve sau phai xu ly hai truong hop — do la no ky sinh, khong phai tinh nang.
    """
    import json as _json

    from project_sentinel.orchestrator.steps.ingest import _normalise_finding_fields

    findings = [
        {"id": "opengrep-001", "tool": "opengrep", "cwe": "CWE-89", "owasp": None},
        {"id": "zap-1", "tool": "zap", "cwe": ["CWE-693"], "owasp": []},
        {"id": "opengrep-002", "tool": "opengrep", "cwe": None, "owasp": ""},
    ]
    _normalise_finding_fields(findings)
    assert findings[0]["cwe"] == ["CWE-89"]
    assert findings[0]["owasp"] == []
    assert findings[1]["cwe"] == ["CWE-693"]
    assert findings[2]["cwe"] == []
    assert findings[2]["owasp"] == []
    assert _json.dumps(findings)  # van serialise duoc
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/orchestrator/test_step_scan_dast.py -v`
Expected: FAIL — `RunContext` chưa có `dast_command`.

- [ ] **Step 3: Thêm `dast_command` vào `RunContext`**

Sau `probe_override` (trường có default phải đứng sau trường không default):

```python
    dast_command: list[str] = field(default_factory=list)
```

Trong `RunContext.default`, trước `return cls(...)`:

```python
        # DAST la tuy chon: khong co script thi run van chay, chi thieu DAST.
        dast_script = root / "scripts" / "scan-zap.sh"
        dast_override = os.getenv("SENTINEL_DAST_COMMAND", "").strip()
        if dast_override:
            override = Path(dast_override)
            if override.is_file() and os.access(override, os.X_OK):
                dast_command = [dast_override]
            else:
                logger.warning(
                    "Bo qua SENTINEL_DAST_COMMAND: gia tri phai la duong dan "
                    "toi mot file executable"
                )
                dast_command = []
        elif dast_script.is_file() and os.access(dast_script, os.X_OK):
            dast_command = [str(dast_script)]
        else:
            dast_command = []
```

và thêm `dast_command=dast_command,` vào `cls(...)`.

- [ ] **Step 4: Thêm nhánh DAST vào `step_scan`**

Trong `ingest.py`, ngay **trước** `record.mark_step("scan", "done", ...)`:

```python
    # DAST chay SAU SAST va khong bao gio keo buoc nay fail. SAST la xuong song
    # cua pipeline; mot may khong co Docker van phai chay duoc run.
    dast_status = "skipped"
    dast_reason: str | None = None
    if not ctx.dast_command:
        dast_reason = "Khong cau hinh lenh DAST"
    else:
        alerts = record.root / "zap-alerts.json"
        access_log = record.root / "gateway-access.log"
        try:
            _run_command(
                [*ctx.dast_command, str(alerts), str(access_log)],
                cwd=ctx.repo_root,
                step="scan",
                root=record.root,
            )
        except StepFailure as exc:
            dast_reason = str(exc)
        else:
            if alerts.exists() and access_log.exists():
                dast_status = "done"
            else:
                dast_reason = "Lenh DAST khong sinh du hai artifact"

    if dast_status == "done":
        append_log(record.root, step="scan", level="info", message="DAST xong")
    else:
        append_log(
            record.root, step="scan", level="warn",
            message=f"Bo qua DAST: {dast_reason}",
        )
```

Rồi đổi `mark_step`:

```python
    detail = {"raw_results": count, "used_fallback": used_fallback, "dast": dast_status}
    if dast_reason:
        detail["dast_reason"] = dast_reason
    record.mark_step("scan", "done", detail=detail)
```

- [ ] **Step 5: Cho `scan-zap.sh` nhận hai tham số**

Hiện script nhận `$1` là report path và tự đặt `gateway_log`. Đổi để nhận cả hai, **giữ nguyên mọi chuỗi mà test đang khoá**:

```bash
report_path="${1:-$artifacts_root/raw/zap.json}"
gateway_log="${2:-$artifacts_root/dast/gateway-access.log}"
```

Chạy lại `.venv/bin/python -m pytest tests/unit/infra/test_zap_scan_script.py -v` để chắc không phá contract tĩnh.

- [ ] **Step 6: Trộn và correlate trong `step_normalize`**

Thêm hàm chuẩn hoá vào `ingest.py`, ở mức module:

```python
def _normalise_finding_fields(findings: list[dict]) -> None:
    """Ep cwe/owasp ve list cho moi finding, sua tai cho.

    zap_normalizer cho list, normalizer.py cua OpenGrep cho gia tri vo huong.
    De ca hai hinh dang vao findings.json thi moi thu doc no ve sau — prompt,
    validator, report — deu phai xu ly hai truong hop.
    """
    for item in findings:
        for field in ("cwe", "owasp"):
            value = item.get(field)
            if value is None or value == "":
                item[field] = []
            elif not isinstance(value, list):
                item[field] = [str(value)]
```

Rồi trong `step_normalize`, sau khối kiểm `findings` là list và trước `mark_step`:

```python
    from project_sentinel.analysis.correlation import (
        correlate,
        parse_gateway_access_log,
    )
    from project_sentinel.ingestion.merge_findings import merge_files
    from project_sentinel.ingestion.zap_normalizer import run_normalize

    zap_added = 0
    alerts_path = record.root / "zap-alerts.json"
    if alerts_path.exists():
        zap_normalized = record.root / "zap-findings.json"
        zap_added = len(run_normalize(alerts_path, zap_normalized))
        # Ghi ra file thu ba roi doi ten, KHONG merge_files([target, x], target):
        # doc va ghi cung mot duong dan chi dung duoc nho merge_files tinh co doc
        # het truoc khi ghi. Dua vao mot chi tiet noi tai nhu vay la mong manh.
        combined = record.root / ".findings.merged.json"
        merge_files([target, zap_normalized], combined)
        combined.replace(target)
        payload = json.loads(target.read_text(encoding="utf-8"))
        # Hai normalizer dung hai hinh dang cho cung mot truong: zap_normalizer
        # cho cwe/owasp la list, normalizer.py cua OpenGrep cho gia tri vo huong.
        # Chuan hoa ve list ngay sau khi tron, vi list la dang tong quat hon va
        # moi thu doc findings.json sau day chi con mot hinh dang de xu ly.
        _normalise_finding_fields(payload["findings"])
        payload["findings"] = correlate(
            payload["findings"],
            parse_gateway_access_log(record.root / "gateway-access.log"),
            project_root=ctx.repo_root,
        )
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        findings = payload["findings"]

    correlated = sum(
        1 for f in findings
        if (f.get("runtime_evidence") or {}).get("strength", "no_route") != "no_route"
    )
    record.mark_step(
        "normalize", "done",
        detail={"findings": len(findings), "zap_findings": zap_added,
                "correlated": correlated},
    )
```

- [ ] **Step 7: Chạy test**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_step_scan_dast.py -v
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
```
Expected: PASS, không test cũ nào đỏ.

- [ ] **Step 8: Commit**

```bash
git add src/project_sentinel/orchestrator/context.py \
        src/project_sentinel/orchestrator/steps/ingest.py \
        scripts/scan-zap.sh \
        tests/unit/orchestrator/test_step_scan_dast.py
git commit -m "feat(dast): chạy DAST trong step_scan và đối chiếu ở step_normalize"
```

---

## Task 8: Schema, provenance và bằng chứng cho finding URL

**Files:**
- Modify: `schemas/security-analysis-record.schema.json`
- Modify: `src/project_sentinel/analysis/validators.py`
- Modify: `src/project_sentinel/analysis/evidence.py`
- Test: `tests/unit/analysis/test_url_locations.py`, `tests/unit/analysis/test_dast_evidence.py`

**Interfaces:**
- Produces: `locations[]` chấp nhận `{file, line}` **hoặc** `{url, method?, param?}`; `evidence_for_finding(finding, *, project_root, target_root, radius=4) -> SourceEvidence`.

- [ ] **Step 1: Đọc validator hiện tại**

```bash
grep -n "locations" -B 3 -A 20 src/project_sentinel/analysis/validators.py
```
Ghi lại **tên hàm thật** kiểm provenance vị trí. Các bước sau dùng tên đó, không dùng tên giả định.

- [ ] **Step 2: Viết test fail trước**

`tests/unit/analysis/test_url_locations.py`:

```python
"""Vi tri dang URL cho finding DAST, cung ky luat provenance nhu file:line."""

import json
from pathlib import Path

SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "schemas" / "security-analysis-record.schema.json"
)


def test_schema_allows_both_location_shapes():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    location = schema["properties"]["locations"]["items"]
    assert "oneOf" in location
    required = [set(branch["required"]) for branch in location["oneOf"]]
    assert {"file", "line"} in required
    assert {"url"} in required


def test_a_url_the_agent_invented_is_rejected():
    from project_sentinel.analysis.validators import validate_provenance

    findings = [{"id": "zap-1", "tool": "zap",
                 "file_or_url": "http://gateway-dast:8081/WebGoat/login",
                 "instances": []}]
    record = {"analysis_id": "a1", "source_finding_ids": ["zap-1"],
              "locations": [{"url": "http://gateway-dast:8081/WebGoat/KHONG-CO-THAT"}]}
    assert validate_provenance(record, findings)


def test_a_url_present_in_the_input_is_accepted():
    from project_sentinel.analysis.validators import validate_provenance

    findings = [{"id": "zap-1", "tool": "zap",
                 "file_or_url": "http://gateway-dast:8081/WebGoat/login",
                 "instances": []}]
    record = {"analysis_id": "a1", "source_finding_ids": ["zap-1"],
              "locations": [{"url": "http://gateway-dast:8081/WebGoat/login"}]}
    assert not validate_provenance(record, findings)


def test_a_url_from_an_instance_is_accepted():
    from project_sentinel.analysis.validators import validate_provenance

    findings = [{"id": "zap-1", "tool": "zap", "file_or_url": "http://x/a",
                 "instances": [{"url": "http://gateway-dast:8081/WebGoat/b",
                                "method": "GET", "param": ""}]}]
    record = {"analysis_id": "a1", "source_finding_ids": ["zap-1"],
              "locations": [{"url": "http://gateway-dast:8081/WebGoat/b"}]}
    assert not validate_provenance(record, findings)
```

**Sửa `validate_provenance` thành tên và chữ ký thật** tìm được ở Step 1.

`tests/unit/analysis/test_dast_evidence.py`:

```python
"""Dieu phoi bang chung: finding tinh doc source, finding dong dung chinh alert.

Yeu cau quan trong nhat: duong CU khong doi hanh vi (AGENTS.md §2.1).
"""

from pathlib import Path

from project_sentinel.analysis.evidence import (
    evidence_for_finding,
    extract_source_window,
)

REPO = Path(__file__).resolve().parents[3]
TARGET = REPO / "benchmarks" / "targets" / "webgoat"
JAVA = (
    "benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat"
    "/container/WebSecurityConfig.java"
)


def test_static_finding_takes_the_unchanged_source_path():
    finding = {"id": "opengrep-001", "tool": "opengrep",
               "file_or_url": JAVA, "line": 61}
    routed = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    direct = extract_source_window(REPO, TARGET, JAVA, 61)
    assert routed == direct, "Duong cu phai cho ket qua y het khi goi thang"


def test_dast_finding_uses_its_own_alert_content():
    finding = {
        "id": "zap-10021-abc", "tool": "zap",
        "file_or_url": "http://gateway-dast:8081/WebGoat/login",
        "line": 0, "title": "Thieu CSP",
        "instances": [{"url": "http://gateway-dast:8081/WebGoat/login",
                       "method": "GET", "param": "username"}],
        "instances_total": 7,
    }
    evidence = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    assert evidence.error is None
    assert "GET" in evidence.content
    assert "username" in evidence.content
    assert "7" in evidence.content, "Phai noi tong so instance that"


def test_line_zero_is_not_treated_as_a_source_location():
    # zap_normalizer dat line: 0, khong phai None. Dieu phoi bang line > 0.
    finding = {"id": "zap-1", "tool": "zap", "file_or_url": "http://x/a",
               "line": 0, "instances": [], "instances_total": 0}
    evidence = evidence_for_finding(finding, project_root=REPO, target_root=TARGET)
    assert evidence.error
```

- [ ] **Step 3: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_url_locations.py tests/unit/analysis/test_dast_evidence.py -v`
Expected: FAIL.

- [ ] **Step 4: Sửa schema**

Đọc lại `properties.locations.items` hiện tại rồi thay bằng `oneOf`, **giữ nguyên mọi thuộc tính của nhánh `file`/`line`**:

```json
{
  "oneOf": [
    {
      "type": "object",
      "required": ["file", "line"],
      "additionalProperties": false,
      "properties": {
        "file": { "type": "string" },
        "line": { "type": "integer" }
      }
    },
    {
      "type": "object",
      "required": ["url"],
      "additionalProperties": false,
      "properties": {
        "url": {
          "description": "Vi tri runtime cua mot finding DAST. Phai co that trong input.",
          "type": "string"
        },
        "method": { "type": "string" },
        "param": { "type": ["string", "null"] }
      }
    }
  ]
}
```

- [ ] **Step 5: Sửa validator**

Trong hàm kiểm provenance vị trí, thêm nhánh URL bên cạnh nhánh `file`/`line`:

```python
        if "url" in location:
            known_urls: set[str] = set()
            for finding in findings:
                if finding.get("file_or_url"):
                    known_urls.add(str(finding["file_or_url"]))
                for instance in finding.get("instances") or []:
                    if instance.get("url"):
                        known_urls.add(str(instance["url"]))
            if str(location["url"]) not in known_urls:
                errors.append(f"URL {location['url']!r} khong co trong input findings")
            continue
```

- [ ] **Step 6: Thêm điều phối bằng chứng**

Cuối `src/project_sentinel/analysis/evidence.py`:

```python
def _dast_evidence(finding: dict) -> SourceEvidence:
    """Bang chung cua mot finding dong la chinh alert do ZAP quan sat."""
    instances = finding.get("instances") or []
    if not instances:
        return SourceEvidence(
            path=str(finding.get("file_or_url") or ""),
            start_line=0, end_line=0, content="",
            error="Finding DAST khong co instance nao de lam bang chung",
        )

    total = finding.get("instances_total", len(instances))
    lines = [
        f"Alert: {finding.get('title') or finding.get('rule_id')}",
        f"So vi tri bi anh huong: {total}",
    ]
    for instance in instances:
        line = f"- {instance.get('method', 'GET')} {instance.get('url', '')}"
        if instance.get("param"):
            line += f" [param={instance['param']}]"
        lines.append(line)

    return SourceEvidence(
        path=str(instances[0].get("url") or finding.get("file_or_url") or ""),
        start_line=0, end_line=0, content="\n".join(lines),
    )


def evidence_for_finding(
    finding: dict, *, project_root: Path, target_root: Path, radius: int = 4
) -> SourceEvidence:
    """Chon duong trich bang chung theo hinh dang cua finding.

    Finding co file+line di dung duong cu, khong doi mot byte hanh vi
    (AGENTS.md §2.1). zap_normalizer dat `line: 0` chu khong phai None, nen
    dieu phoi bang `line > 0`.
    """
    location = finding.get("file_or_url")
    line = finding.get("line")
    if isinstance(line, int) and line > 0 and location and "://" not in str(location):
        return extract_source_window(
            project_root, target_root, str(location), line, radius
        )
    if str(finding.get("tool")) == "zap":
        return _dast_evidence(finding)
    return extract_source_window(
        project_root, target_root, str(location or ""), line or 0, radius
    )
```

- [ ] **Step 7: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/analysis/ -v`
Expected: PASS.

- [ ] **Step 8: Đổi nơi gọi trong pipeline**

```bash
grep -rn "extract_source_window" src/project_sentinel/analysis/
```
Ở mỗi nơi **pipeline** gọi nó cho một finding, đổi sang `evidence_for_finding(...)`. Chạy lại toàn bộ test sau mỗi lần đổi.

- [ ] **Step 9: Khẳng định fixture analysis cũ vẫn hợp lệ**

```bash
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
make validate-analysis || true
```

- [ ] **Step 10: Commit**

```bash
git add schemas/security-analysis-record.schema.json \
        src/project_sentinel/analysis/validators.py \
        src/project_sentinel/analysis/evidence.py \
        tests/unit/analysis/test_url_locations.py \
        tests/unit/analysis/test_dast_evidence.py
git commit -m "feat(dast): locations chấp nhận URL và bằng chứng riêng cho finding động"
```

---

## Task 9: Số liệu và tài liệu

**Files:**
- Modify: `src/project_sentinel/orchestrator/metrics.py`
- Test: `tests/unit/orchestrator/test_metrics_dast.py`
- Modify: `docs/architecture.md`, `docs/limitations.md`, `docs/target-webgoat.md`, `README.md`, `docs/demo-script.md`

- [ ] **Step 1: Viết test fail trước**

`tests/unit/orchestrator/test_metrics_dast.py`:

```python
"""So lieu phai noi ro hai loai hat finding, khong tron im lang.

DAST gop theo loai alert nen mot finding ZAP khong cung don vi voi mot
finding OpenGrep. findings_total ma dung mot minh la con so gay hieu nham.
"""

import json

from project_sentinel.orchestrator.metrics import collect_metrics
from project_sentinel.orchestrator.state import new_run


def _write(root, findings, log_lines=None):
    (root / "findings.json").write_text(
        json.dumps({"count": len(findings), "findings": findings}), encoding="utf-8"
    )
    if log_lines is not None:
        (root / "gateway-access.log").write_text(
            "\n".join(log_lines) + "\n", encoding="utf-8"
        )


def test_findings_are_counted_per_tool(tmp_path):
    record = new_run(tmp_path / "runs")
    _write(
        record.root,
        [
            {"id": "opengrep-001", "tool": "opengrep"},
            {"id": "opengrep-002", "tool": "opengrep"},
            {"id": "zap-10021-a", "tool": "zap", "instances": [{}],
             "instances_total": 9},
        ],
        log_lines=[
            "2026-08-22T09:00:00+00:00 channel=dast method=GET "
            "path=/WebGoat/login query=- status=200 bytes=9 rt=0.01"
        ],
    )
    metrics = collect_metrics(record)
    assert metrics["findings_total"] == 3, "Nghia cu giu nguyen"
    assert metrics["findings_by_tool"] == {"opengrep": 2, "zap": 1}
    assert metrics["dast"]["alerts_total"] == 1
    assert metrics["dast"]["instances_total"] == 9
    assert metrics["dast"]["endpoints_discovered"] == 1


def test_a_run_without_dast_reports_zeros_not_missing_keys(tmp_path):
    record = new_run(tmp_path / "runs")
    _write(record.root, [{"id": "opengrep-001", "tool": "opengrep"}])
    metrics = collect_metrics(record)
    assert metrics["dast"] == {
        "endpoints_discovered": 0, "alerts_total": 0, "instances_total": 0
    }
    assert metrics["findings_by_tool"] == {"opengrep": 1}
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/orchestrator/test_metrics_dast.py -v`
Expected: FAIL — `KeyError: 'findings_by_tool'`.

- [ ] **Step 3: Sửa `collect_metrics`**

Trong khối đọc `findings.json`, sau khi có biến `findings`:

```python
    by_tool: dict[str, int] = {}
    zap_alerts = 0
    zap_instances = 0
    for item in findings:
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or "unknown")
        by_tool[tool] = by_tool.get(tool, 0) + 1
        if tool == "zap":
            zap_alerts += 1
            zap_instances += _nonnegative_count(item.get("instances_total"))

    from project_sentinel.analysis.correlation import parse_gateway_access_log

    endpoints_discovered = len(
        parse_gateway_access_log(record.root / "gateway-access.log")["endpoints"]
    )
```

Thêm vào dict trả về, cạnh `"findings_total"`:

```python
        "findings_by_tool": by_tool,
        "dast": {
            "endpoints_discovered": endpoints_discovered,
            "alerts_total": zap_alerts,
            "instances_total": zap_instances,
        },
```

- [ ] **Step 4: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/orchestrator/test_metrics_dast.py -v`
Expected: PASS.

- [ ] **Step 5: Cập nhật `docs/architecture.md`**

- Bước `scan` giờ làm hai việc (SAST bắt buộc, DAST tuỳ chọn). Số bước vẫn **chín**.
- Thêm lane `gateway-dast` vào sơ đồ vùng, ghi rõ ZAP không biết địa chỉ WebGoat.
- Ghi Gateway giữ phiên WebGoat, ZAP ẩn danh.
- §4: `reachability` giờ do Python đo, không do Agent khai.
- §6: thêm `zap-alerts.json`, `zap-findings.json`, `gateway-access.log` vào cây artifact.

- [ ] **Step 6: Cập nhật `docs/limitations.md`**

Thêm vào "Hạn chế chức năng":

```markdown
- DAST chỉ chạy baseline (spider + passive scan), không active scan. Nó chứng
  minh được một endpoint tồn tại và chạm tới được, nhưng không chứng minh được
  kẻ tấn công kiểm soát được dữ liệu tới sink. `confirmed` vì thế vẫn ngoài tầm.
- Phiên WebGoat do Gateway giữ và dùng chung cho cả lần quét. Một phiên duy
  nhất không phát hiện được lỗ hổng phụ thuộc nhiều tài khoản (IDOR giữa hai
  người dùng).
- Đối chiếu SAST ↔ DAST dựa trên annotation route của Spring. Endpoint đăng ký
  theo cách khác (cấu hình động, router tuỳ biến) sẽ nhận `no_route`.
- Bản đồ endpoint đọc từ Nginx access log, mà log ghi `path=$uri` — path đã
  chuẩn hoá. Tham số lấy từ `query=$args`, nên tham số gửi trong body (không có
  ở lane GET/HEAD-only này) không bao giờ xuất hiện.
```

- [ ] **Step 7: Cập nhật tài liệu còn lại**

- `docs/target-webgoat.md`: bề mặt `permitAll` (`WebSecurityConfig.java:34-44`) và vì sao cần phiên đăng nhập mới quét được lesson.
- `README.md`: `make dast`, `make dast-test`, và DAST trong sơ đồ mermaid.
- `docs/demo-script.md`: DAST xuất hiện ở đâu trong demo.

- [ ] **Step 8: Chạy toàn bộ**

```bash
.venv/bin/python -m pytest tests/unit/infra/test_docs_complete.py tests/test_docs_are_honest.py -v
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
make lint && make typecheck
make dast-test
make gateway-live-test
```
Expected: xanh hết. Dán số liệu thật vào worklog.

- [ ] **Step 9: Commit**

```bash
git add src/project_sentinel/orchestrator/metrics.py \
        tests/unit/orchestrator/test_metrics_dast.py \
        docs/ README.md
git commit -m "feat(dast): số liệu tách theo công cụ và đồng bộ tài liệu"
```

---

## Nghiệm thu cuối

- [ ] `make dast` chạy được; bản đồ endpoint chứa URL **ngoài** danh sách `permitAll`
- [ ] `JSESSIONID` không xuất hiện trong bất kỳ artifact nào
- [ ] `tests/unit/gateway/test_dast_gateway_config.py` xanh **không sửa một assertion nào**
- [ ] `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` xanh
- [ ] `make dast-test` xanh với ZAP và WebGoat thật
- [ ] `make agent-test` và `make gateway-live-test` xanh — lane Agent không hồi quy
- [ ] `make lint && make typecheck` xanh
- [ ] Một run đầu-cuối thật: `findings.json` có cả `opengrep-*` lẫn `zap-*`, có khối `runtime_evidence`, `metrics.json` có `findings_by_tool` và khối `dast`
- [ ] Mỗi task có một file trong `worklog/`, đủ 8 mục, số liệu là output chạy thật
