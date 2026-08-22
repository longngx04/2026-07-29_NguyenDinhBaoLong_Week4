# Reachability cho endpoint POST — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho lane DAST gửi được POST tới một danh sách endpoint đã review, để 19 finding SAST đang mắc ở `route_known_not_reached` chuyển thành `reachable`.

**Architecture:** Lane DAST giữ nguyên bốn lớp bảo vệ (credential riêng, xoá header caller, xoá body caller, chỉ nội bộ) và đổi đúng một lớp: POST được phép, **chỉ với path có trong `dast-allowlist.json`**. Body là hằng số do lane quyết định, ép bằng `proxy_set_body` — ZAP không ảnh hưởng được method, path, header hay body. Traffic POST do một lần gọi ZAP **thứ hai** sinh ra, chạy Automation Framework `requestor` job; lần gọi baseline hiện tại không bị đụng tới.

**Tech Stack:** Nginx 1.27-alpine, OWASP ZAP (Automation Framework `requestor`), Docker Compose, Python 3.10+, pytest, jq, bash.

**Spec:** [`docs/superpowers/specs/2026-08-22-dast-post-reachability-design.md`](../specs/2026-08-22-dast-post-reachability-design.md)

## Global Constraints

- **Branch:** `feat/zap-dast`. Chạy `git branch --show-current` trước khi chạm file nào. Không `git add -A`.
- **Worklog bắt buộc** sau mỗi task: `worklog/2026-08-22-dastpost-<task-slug>.md` theo [`worklog/_TEMPLATE.md`](../../../worklog/_TEMPLATE.md), đủ 8 mục, số liệu là output chạy thật.
- **Không mock, không stub.** Test không tới được dependency thì **fail**, không skip (`AGENTS.md` §2.2).
- **Không bịa bằng chứng** (`AGENTS.md` §2.6).
- **Bốn lớp giữ nguyên tuyệt đối:** `proxy_pass_request_headers off`, `proxy_pass_request_body off`, credential `SENTINEL_DAST_API_KEY` riêng, không bind cổng host. Thay đổi nào đụng bốn thứ này là sai.
- **Không sinh map nginx từ JSON.** Người viết cả hai bên; một test đối chiếu chúng. Script sinh cả hai từ một nguồn biến hai lớp kiểm thành một lớp.
- **`zap-baseline.py` hiện tại không được sửa**, kể cả cờ `--autooff` — `test_zap_scan_script.py` ghi rõ lý do (*ZAP 2.17 Automation Framework ignores -I exit semantics*).
- Ruff `line-length = 100`, target `py310`. `make lint` và `make typecheck` xanh trước mỗi commit.
- Mốc test hiện tại: **926 passed**. Con số giảm ⇒ DỪNG, hỏi người dùng.

## Ràng buộc từ test đang có

| Test | Khoá điều gì | Hệ quả |
| :--- | :--- | :--- |
| `test_dast_gateway_config.py::test_dast_listener_only_forwards_read_only_methods` | `$request_method !~ ^(GET\|HEAD)$`, `$content_length`, `Content-Length ""` | **Phải viết lại** — chính sách là thứ đang đổi. Viết lại để khoá chính sách MỚI, không nới cho qua |
| `test_dast_gateway_config.py` — các test còn lại | Key riêng, chỉ proxy `/WebGoat/`, bootstrap tĩnh, xoá header caller | **Không được đụng** |
| `test_zap_scan_script.py::test_zap_wrapper_runs_baseline_not_active_scan` | `zap-baseline.py`, `--autooff`, không `zap-full-scan.py` | Lần gọi ZAP thứ hai không được phá các assert này |
| `test_zap_gateway_live.py::test_gateway_log_proves_zap_requests_crossed_the_boundary` | Mọi method ngoài GET/HEAD phải là 405 | **Phải sửa** — POST hợp lệ giờ trả 2xx |
| `test_compose_invariants.py` | `zap`, `gateway-dast` không có `ports` | Không được đụng |

---

## File Structure

| File | Trách nhiệm | Task |
| :--- | :--- | :--- |
| `configs/gateway/dast-allowlist.json` | Danh sách path POST đã review + body hằng số + dòng nguồn | 2 |
| `infra/docker/gateway/templates/default.conf.template` | Map body theo path, cổng method, `proxy_set_body` | 3 |
| `tests/unit/gateway/test_dast_post_policy.py` | Khoá chính sách POST mới | 3 |
| `tests/unit/gateway/test_dast_gateway_config.py` | Viết lại một test; giữ nguyên phần còn lại | 3 |
| `infra/docker/zap/requestor-plan.yaml` | Automation Framework plan gửi POST đã allowlist | 4 |
| `scripts/scan-zap.sh` | Thêm lần gọi ZAP thứ hai | 4 |
| `tests/unit/infra/test_dast_requestor_plan.py` | Plan khớp allowlist, chỉ trỏ Gateway | 4 |
| `src/project_sentinel/analysis/correlation.py` | Chỉ 2xx mới là reachable | 5 |
| `tests/integration/test_zap_gateway_live.py` | Test live cho POST + canary | 6 |
| `docs/limitations.md`, `docs/architecture.md` | Số đo mới + chính sách lane mới | 6 |

---

## Task 1: Trả lời bốn câu hỏi chặn cả plan

Task này **không viết code sản phẩm**. Nó trả lời bốn câu và ghi câu trả lời vào worklog. Spec §6.1 liệt kê chúng vì không câu nào suy luận được.

**Files:** chỉ `worklog/2026-08-22-dastpost-verify.md`

**Interfaces:**
- Consumes: lane DAST hiện có, WebGoat đang chạy.
- Produces: bốn quyết định — cách xử lý `Content-Length`, status thật của body rỗng, lệnh chạy `requestor` job đúng, và cách gắn header key cho autorun.

- [ ] **Step 1: Dựng target**

```bash
make target-up
SENTINEL_DAST_API_KEY=$(openssl rand -hex 32) \
  docker compose --profile dast up --detach --build gateway-dast webgoat
docker compose --profile dast logs gateway-dast | grep -i "phien WebGoat"
```
Expected: dòng `[gateway-dast] Da lay session thanh cong (do dai: N)`. Không có nghĩa là session hỏng — dừng và báo.

- [ ] **Step 2: WebGoat trả status gì cho POST body rỗng**

Gọi thẳng WebGoat từ trong mạng, **bỏ qua Gateway**, để tách bạch hai biến:

```bash
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O - --header="Content-Type: application/x-www-form-urlencoded" \
    --header="Cookie: JSESSIONID=$SENTINEL_DAST_SESSION" \
    --post-data="query=" \
    http://webgoat:8080/WebGoat/SqlInjection/attack2 2>&1 | head -30'
```

Ghi lại **status thật**. Thiết kế giả định 2xx (exception bị bắt, trả `AttackResult`).
- Nếu là **2xx** → tiếp tục theo plan.
- Nếu là **4xx/5xx** → body rỗng không dùng được. Thử `query=SELECT%201`, ghi lại status. Nếu vẫn không 2xx, **DỪNG và báo người dùng**: thiết kế body chính tắc phải đổi trước khi viết bất cứ gì.

- [ ] **Step 3: `Content-Length ""` có làm hỏng POST không**

Lane hiện đặt `proxy_set_header Content-Length "";`. Tạm thêm một location POST thử nghiệm để đo. Sửa `infra/docker/gateway/templates/default.conf.template`, thêm **tạm** vào khối `# DAST boundary`, ngay trước `location ^~ /WebGoat/`:

```nginx
    # TAM THOI — chi de do o Task 1, se xoa o cuoi task nay.
    location = /WebGoat/SqlInjection/attack2 {
        proxy_set_header Cookie "JSESSIONID=${SENTINEL_DAST_SESSION}";
        proxy_set_header Content-Type "application/x-www-form-urlencoded";
        proxy_set_body "query=";
        proxy_pass http://webgoat:8080;
    }
```

Và tạm đổi `if ($request_method !~ ^(GET|HEAD)$)` thành `^(GET|HEAD|POST)$`, tạm bỏ `if ($content_length) { return 413; }`, tạm đổi `client_max_body_size 1;` thành `8k`.

```bash
docker compose --profile dast up --detach --build gateway-dast
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="khac_hoan_toan=canary123" \
    http://127.0.0.1:8081/WebGoat/SqlInjection/attack2 2>&1 | head -30'
```

Ghi lại: status trả về, và response có dấu hiệu WebGoat nhận đúng `query=` hay không.
- POST **2xx** → `Content-Length ""` không gây vấn đề, giữ nguyên dòng đó.
- POST **400/411/413** → phải bỏ hoặc điều kiện hoá `proxy_set_header Content-Length "";`. Thử bỏ dòng đó, đo lại, ghi kết quả.

Ghi **kết luận dứt khoát** vào worklog: giữ hay bỏ dòng Content-Length.

- [ ] **Step 4: Hoàn tác toàn bộ sửa tạm**

```bash
git checkout -- infra/docker/gateway/templates/default.conf.template
git status --short infra/docker/gateway/
```
Expected: **rỗng**. Task 1 không để lại thay đổi nào trong code sản phẩm.

- [ ] **Step 5: Sinh mẫu plan của Automation Framework**

```bash
docker compose --profile dast run --rm --no-deps zap \
  zap-baseline.py -t http://gateway-dast:8081/WebGoat/login --plan-only 2>&1 | head -60
```
Dán nguyên output vào worklog. Đây là **schema thật** của plan YAML; Task 4 bám theo nó chứ không bám theo trí nhớ.

- [ ] **Step 6: Xác minh cách chạy plan và gắn header key**

```bash
docker compose --profile dast run --rm --no-deps --entrypoint sh zap -c \
  '/zap/zap.sh -h 2>&1 | grep -iE "autorun|cmd|config"'
```

`ZAP_AUTH_HEADER` là biến mà **packaged scan script** đọc, không chắc `zap.sh -autorun` đọc. Xác định cách gắn header `X-Sentinel-DAST-Key` cho autorun và **ghi lệnh chính xác chạy được** vào worklog. Hai hướng để thử, ghi lại cái nào chạy:
- `-config replacer.full_list(0).description=key -config replacer.full_list(0).enabled=true ...`
- Khai header trong chính plan YAML nếu schema ở Step 5 cho phép.

- [ ] **Step 7: Viết worklog và commit**

Worklog phải có bốn kết luận dứt khoát: status của body rỗng, giữ-hay-bỏ `Content-Length ""`, schema plan thật, lệnh autorun kèm header.

```bash
git add worklog/2026-08-22-dastpost-verify.md
git commit -m "docs(worklog): xác minh bốn giả định chặn việc mở POST cho lane DAST"
```

---

## Task 2: Dựng `dast-allowlist.json` từ source thật

**Files:**
- Create: `configs/gateway/dast-allowlist.json`
- Test: `tests/unit/gateway/test_dast_allowlist.py`

**Interfaces:**
- Consumes: kết luận Task 1 về body chính tắc.
- Produces: file allowlist với các mục `{path, method, canonical_body, content_type, purpose, source}`.

- [ ] **Step 1: Đọc `@RequestParam` của từng endpoint ứng viên**

Danh sách route lấy từ chính `correlation.extract_route` trên finding thật:

```bash
.venv/bin/python - <<'PY'
import json, glob
from pathlib import Path
from project_sentinel.analysis.correlation import correlate, parse_gateway_access_log
src = sorted(glob.glob('artifacts/runs/*/findings.json'))[-1]
sast = [f for f in json.load(open(src))['findings'] if f.get('tool') != 'zap']
out = correlate(sast, parse_gateway_access_log('artifacts/dast/gateway-access.log'),
                project_root=Path('.'))
routes = sorted({f['runtime_evidence']['route'] for f in out
                 if f['runtime_evidence']['strength'] == 'route_known_not_reached'})
for r in routes: print(r)
PY
```

Với **mỗi** route, mở file Java khai nó và đọc chữ ký method. Ghi vào worklog một bảng: route · file:dòng · tên tham số · kiểu.

```bash
grep -rn -A 4 '@PostMapping("/SqlInjection/attack2")' \
  benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/
```

- [ ] **Step 2: Loại các route không dùng được**

Bỏ khỏi danh sách, và **ghi lý do vào worklog** cho từng cái:
- Route có path template (`/JWT/kid/follow/{user}`) — không phải URL cụ thể, map nginx cần key chính xác.
- Route mà tham số không thể để rỗng một cách vô hại.

- [ ] **Step 3: Viết test trước**

`tests/unit/gateway/test_dast_allowlist.py`:

```python
"""Allowlist POST cho lane DAST: mỗi mục là một request thật vào ứng dụng có lỗ hổng.

Cổng bảo vệ duy nhất là người đọc @RequestParam rồi chọn body làm ít nhất có
thể. Các test dưới đây không thay được việc review, nhưng chúng chặn những
kiểu sai máy móc: trích sai dòng nguồn, method lạ, path ngoài /WebGoat/.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST = REPO_ROOT / "configs" / "gateway" / "dast-allowlist.json"

REQUIRED_FIELDS = {
    "path", "method", "canonical_body", "content_type", "purpose", "source",
}


def _entries() -> list[dict]:
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    return data["endpoints"]


def test_every_entry_has_all_required_fields():
    for entry in _entries():
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"{entry.get('path')}: thiếu {sorted(missing)}"


def test_every_entry_is_post_under_the_webgoat_prefix():
    for entry in _entries():
        assert entry["method"] == "POST", (
            f"{entry['path']}: allowlist này CHỈ dành cho POST. GET/HEAD đã "
            "được lane cho phép sẵn và không cần khai ở đây."
        )
        assert entry["path"].startswith("/WebGoat/"), entry["path"]
        assert "?" not in entry["path"], "Path không được mang query"
        assert "{" not in entry["path"], (
            f"{entry['path']}: path template không dùng được — map nginx cần "
            "key chính xác"
        )


def test_no_duplicate_paths():
    paths = [entry["path"] for entry in _entries()]
    assert len(paths) == len(set(paths)), f"Path trùng: {paths}"


def test_every_source_points_at_a_real_postmapping():
    """Trích sai dòng nguồn làm cả review mất căn cứ."""
    for entry in _entries():
        raw = entry["source"]
        file_part, line_part = raw.rsplit(":", 1)
        start = int(line_part.split("-")[0])
        path = REPO_ROOT / file_part
        assert path.is_file(), f"{entry['path']}: không có file {file_part}"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        assert start <= len(lines), f"{entry['path']}: file chỉ có {len(lines)} dòng"
        window = "\n".join(lines[start - 1 : start + 4])
        route = entry["path"].removeprefix("/WebGoat")
        assert "@PostMapping" in window, (
            f"{entry['path']}: dòng {start} của {file_part} không có @PostMapping"
        )
        assert route in window, (
            f"{entry['path']}: dòng {start} không khai route {route}"
        )


def test_every_canonical_body_names_a_parameter_the_endpoint_declares():
    """Body chính tắc phải dùng đúng tên tham số Java khai, không phải tên đoán."""
    for entry in _entries():
        body = entry["canonical_body"]
        assert body, f"{entry['path']}: canonical_body rỗng chuỗi"
        param = body.split("=", 1)[0]
        file_part, line_part = entry["source"].rsplit(":", 1)
        start = int(line_part.split("-")[0])
        lines = (REPO_ROOT / file_part).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        window = "\n".join(lines[start - 1 : start + 6])
        assert re.search(rf"\b{re.escape(param)}\b", window), (
            f"{entry['path']}: tham số '{param}' không xuất hiện trong chữ ký "
            f"method tại {file_part}:{start}"
        )


def test_canonical_body_carries_no_sql_or_shell():
    """Body chính tắc phải làm ÍT NHẤT có thể, không phải một payload khéo léo."""
    banned = ["select", "union", "drop", "'", '"', ";", "--", "$(", "`"]
    for entry in _entries():
        low = entry["canonical_body"].lower()
        hits = [token for token in banned if token in low]
        assert not hits, (
            f"{entry['path']}: canonical_body chứa {hits}. Body chỉ để chứng "
            "minh endpoint sống, không để thử gì cả."
        )
```

- [ ] **Step 4: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/gateway/test_dast_allowlist.py -v`
Expected: FAIL — file allowlist chưa tồn tại.

- [ ] **Step 5: Viết file allowlist**

`configs/gateway/dast-allowlist.json`. Dùng **đúng** tên tham số và dòng nguồn đọc được ở Step 1. Mẫu một mục — các mục khác viết cùng dạng, **không chép mù**:

```json
{
  "schema_version": "1.0",
  "endpoints": [
    {
      "path": "/WebGoat/SqlInjection/attack2",
      "method": "POST",
      "canonical_body": "query=",
      "content_type": "application/x-www-form-urlencoded",
      "purpose": "Chứng minh endpoint sống. Body rỗng làm executeQuery ném exception, WebGoat bắt lại và trả 200 — không câu SQL nào chạy.",
      "source": "benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson2.java:40"
    }
  ]
}
```

- [ ] **Step 6: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/gateway/test_dast_allowlist.py -v`
Expected: PASS. Test nào đỏ thì **sửa allowlist**, không sửa test.

- [ ] **Step 7: Commit**

```bash
git add configs/gateway/dast-allowlist.json tests/unit/gateway/test_dast_allowlist.py
git commit -m "feat(dast): allowlist POST cho lane DAST, mỗi mục trích dòng nguồn Java"
```

---

## Task 3: Cổng method và body hằng số trong nginx

**Files:**
- Modify: `infra/docker/gateway/templates/default.conf.template`
- Create: `tests/unit/gateway/test_dast_post_policy.py`
- Modify: `tests/unit/gateway/test_dast_gateway_config.py`

**Interfaces:**
- Consumes: `dast-allowlist.json` (Task 2), kết luận Content-Length (Task 1).
- Produces: lane DAST nhận POST cho path đã allowlist, trả 405 cho mọi path khác.

- [ ] **Step 1: Viết test khoá chính sách mới trước**

`tests/unit/gateway/test_dast_post_policy.py`:

```python
"""Lane DAST cho POST, nhưng ZAP không chọn được gì cả.

ZAP chỉ nêu một path. Nếu path đó có trong allowlist thì lane tự dựng toàn bộ
request: method, header, body đều là hằng số của lane. Đây là quyết định tin
cậy HẸP HƠN lane probe của Agent, nơi caller còn chọn được template.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "infra/docker/gateway/templates/default.conf.template"
ALLOWLIST = REPO_ROOT / "configs/gateway/dast-allowlist.json"


def _dast_server() -> str:
    return TEMPLATE.read_text(encoding="utf-8").split("# DAST boundary", 1)[1]


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _allowlist() -> list[dict]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["endpoints"]


def test_post_is_gated_by_the_canonical_body_map():
    """"Không có body chính tắc" và "không được POST" phải là CÙNG một điều.

    Hai danh sách riêng thì sẽ có ngày quên đồng bộ một bên.
    """
    text = _template_text()
    assert "map $uri $sentinel_dast_post_body" in text
    assert 'map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok' in text
    server = _dast_server()
    assert "$sentinel_dast_method_ok = 0" in server
    assert "return 405" in server


def test_the_method_map_denies_by_default():
    text = _template_text()
    block = text.split('map "$request_method:$sentinel_dast_post_body"', 1)[1]
    block = block.split("}", 1)[0]
    assert "default 0;" in block, "Thiếu default 0 nghĩa là mở mặc định"
    assert '"~^POST:.+"' in block, "POST chỉ hợp lệ khi body chính tắc khác rỗng"


def test_every_allowlisted_path_appears_in_the_nginx_body_map():
    """Hai bên suy ra ĐỘC LẬP, nên phải có test đối chiếu chúng.

    Sinh nginx từ JSON sẽ biến hai lớp kiểm thành một lớp — đó là lý do việc
    đồng bộ được kiểm bằng test chứ không bằng script sinh mã.
    """
    text = _template_text()
    body_map = text.split("map $uri $sentinel_dast_post_body", 1)[1].split("}", 1)[0]
    for entry in _allowlist():
        assert f'"{entry["path"]}"' in body_map, (
            f"{entry['path']} có trong dast-allowlist.json nhưng thiếu trong map nginx"
        )
        assert f'"{entry["canonical_body"]}"' in body_map, (
            f"{entry['path']}: body trong map nginx không khớp canonical_body"
        )


def test_the_nginx_body_map_advertises_nothing_beyond_the_allowlist():
    """Chiều ngược lại: map nginx không được có path mà JSON chưa duyệt."""
    text = _template_text()
    body_map = text.split("map $uri $sentinel_dast_post_body", 1)[1].split("}", 1)[0]
    allowed = {entry["path"] for entry in _allowlist()}
    for line in body_map.splitlines():
        stripped = line.strip()
        if not stripped.startswith('"/WebGoat/'):
            continue
        path = stripped.split('"')[1]
        assert path in allowed, (
            f"{path} có trong map nginx nhưng KHÔNG có trong dast-allowlist.json"
        )


def test_the_lane_dictates_the_body_not_the_caller():
    server = _dast_server()
    assert "proxy_set_body $sentinel_dast_post_body;" in server
    assert "proxy_pass_request_body off;" in server, (
        "Bỏ dòng này là cho ZAP gửi body tới WebGoat"
    )


def test_caller_headers_are_still_stripped():
    assert "proxy_pass_request_headers off;" in _dast_server()


def test_body_size_is_bounded():
    """Lane đọc rồi vứt body của ZAP, nhưng vẫn phải có trần."""
    server = _dast_server()
    assert "client_max_body_size 8k;" in server
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/gateway/test_dast_post_policy.py -v`
Expected: FAIL — map chưa tồn tại.

- [ ] **Step 3: Thêm hai map vào template**

Trong `infra/docker/gateway/templates/default.conf.template`, đặt cạnh các map hiện có (trước khối `server {` đầu tiên):

```nginx
# Body chinh tac cua tung path POST duoc phep tren lane DAST. Rong nghia la path
# do KHONG duoc POST. Ban sao cua configs/gateway/dast-allowlist.json; hai ben
# duoc suy ra DOC LAP va tests/unit/gateway/test_dast_post_policy.py doi chieu
# chung — sinh mot ben tu ben kia se bien hai lop kiem thanh mot lop.
map $uri $sentinel_dast_post_body {
    default "";
    "/WebGoat/SqlInjection/attack2" "query=";
}

# GET/HEAD luon hop le. POST chi hop le khi path co body chinh tac. Mot POST toi
# path khong co trong map roi vao `default 0` -> 405. Deny-by-default nam trong
# chinh cau truc map, khong nam trong mot danh sach phu dinh phai nho cap nhat.
map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok {
    default 0;
    "~^GET:"     1;
    "~^HEAD:"    1;
    "~^POST:.+"  1;
}
```

Các dòng path khác thêm theo đúng `dast-allowlist.json` của Task 2.

- [ ] **Step 4: Sửa khối server DAST**

Trong khối `# DAST boundary`, thay ba dòng:

```nginx
    client_max_body_size 1;
    ...
    if ($request_method !~ ^(GET|HEAD)$) { return 405; }
    if ($content_length) { return 413; }
```

thành:

```nginx
    # ZAP se gui body form. Nginx doc roi VUT no; WebGoat chi nhan body chinh
    # tac cua lane. 8k du cho form cua ZAP va xa duoi muc dang lo.
    client_max_body_size 8k;
    ...
    if ($sentinel_dast_method_ok = 0) { return 405; }
```

Bỏ hẳn dòng `if ($content_length) { return 413; }`. Giữ nguyên `if ($http_transfer_encoding) { return 400; }`.

Thêm vào khối `location ^~ /WebGoat/`:

```nginx
        proxy_set_body $sentinel_dast_post_body;
        proxy_set_header Content-Type "application/x-www-form-urlencoded";
```

Xử lý `proxy_set_header Content-Length "";` **theo đúng kết luận Task 1 Step 3** — giữ hoặc bỏ, không đoán.

- [ ] **Step 5: Viết lại test đang khoá chính sách cũ**

Trong `tests/unit/gateway/test_dast_gateway_config.py`, thay **duy nhất** hàm `test_dast_listener_only_forwards_read_only_methods`:

```python
def test_dast_listener_forwards_only_reviewed_methods_and_bodies():
    """Chính sách MỚI, chặt hơn ở hai điểm.

    Trước: GET/HEAD-only, mọi body bị 413.
    Nay:   GET/HEAD luôn được; POST chỉ với path có body chính tắc trong
           allowlist; body của caller vẫn bị vứt và thay bằng hằng số của lane.
    Đây là nới method nhưng THU HẸP quyền của ZAP: nó không còn chọn được nội
    dung gửi đi nữa.
    """
    server = _dast_server()
    assert "$sentinel_dast_method_ok = 0" in server
    assert "return 405" in server
    assert "proxy_pass_request_body off;" in server
    assert "proxy_set_body $sentinel_dast_post_body;" in server
    assert "$http_transfer_encoding" in server
```

**Không đụng hàm nào khác trong file này.**

- [ ] **Step 6: Chạy toàn bộ test gateway**

```bash
.venv/bin/python -m pytest tests/unit/gateway/ -v
make lint && make typecheck
```
Expected: PASS.

- [ ] **Step 7: Dựng và đo thật**

```bash
docker compose --profile dast up --detach --build gateway-dast
docker compose --profile dast exec -T gateway-dast sh -c '
  echo "--- POST path DA allowlist ---"
  wget -S -O /dev/null --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="canary=999" http://127.0.0.1:8081/WebGoat/SqlInjection/attack2 2>&1 | grep "HTTP/"
  echo "--- POST path CHUA allowlist ---"
  wget -S -O /dev/null --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="x=1" http://127.0.0.1:8081/WebGoat/login 2>&1 | grep "HTTP/"
  echo "--- GET van chay ---"
  wget -S -O /dev/null --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    http://127.0.0.1:8081/WebGoat/login 2>&1 | grep "HTTP/"'
```
Expected: POST allowlist → **2xx**; POST chưa allowlist → **405**; GET → **200**. Lệch thì dừng, đừng đi tiếp.

- [ ] **Step 8: Commit**

```bash
git add infra/docker/gateway/templates/default.conf.template \
        tests/unit/gateway/test_dast_post_policy.py \
        tests/unit/gateway/test_dast_gateway_config.py
git commit -m "feat(dast): lane nhận POST cho path đã review, body do lane quyết định"
```

---

## Task 4: `requestor` job và lần gọi ZAP thứ hai

**Files:**
- Create: `infra/docker/zap/requestor-plan.yaml`
- Modify: `scripts/scan-zap.sh`
- Create: `tests/unit/infra/test_dast_requestor_plan.py`

**Interfaces:**
- Consumes: `dast-allowlist.json`, lane POST từ Task 3, schema plan và lệnh autorun từ Task 1.
- Produces: access log có dòng `channel=dast method=POST path=/WebGoat/... status=2xx`.

- [ ] **Step 1: Viết test tĩnh trước**

`tests/unit/infra/test_dast_requestor_plan.py`:

```python
"""Plan requestor chỉ được gửi đúng những gì allowlist đã duyệt."""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = REPO_ROOT / "infra/docker/zap/requestor-plan.yaml"
ALLOWLIST = REPO_ROOT / "configs/gateway/dast-allowlist.json"


def _plan() -> dict:
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


def _requests() -> list[dict]:
    for job in _plan()["jobs"]:
        if job.get("type") == "requestor":
            return job["requests"]
    raise AssertionError("Plan không có job requestor nào")


def _allowlist() -> list[dict]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["endpoints"]


def test_every_request_targets_the_dast_gateway_not_webgoat():
    for request in _requests():
        assert request["url"].startswith("http://gateway-dast:8081/"), request["url"]
    assert "webgoat:8080" not in PLAN.read_text(encoding="utf-8"), (
        "ZAP không bao giờ được biết địa chỉ trực tiếp của WebGoat"
    )


def test_requests_match_the_allowlist_exactly():
    """Không thừa, không thiếu. Thừa là gửi thứ chưa duyệt; thiếu là bỏ sót."""
    planned = {
        (r["method"].upper(), r["url"].removeprefix("http://gateway-dast:8081"))
        for r in _requests()
    }
    allowed = {(e["method"], e["path"]) for e in _allowlist()}
    assert planned == allowed, (
        f"Chỉ trong plan: {sorted(planned - allowed)} · "
        f"Chỉ trong allowlist: {sorted(allowed - planned)}"
    )


def test_the_plan_runs_no_scanner_job():
    """Plan này chỉ để chạm endpoint, không quét. Active scan bị cấm hẳn."""
    types = {job.get("type") for job in _plan()["jobs"]}
    assert "activeScan" not in types
    assert "spider" not in types
    assert "spiderAjax" not in types
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/infra/test_dast_requestor_plan.py -v`
Expected: FAIL — plan chưa tồn tại.

- [ ] **Step 3: Viết plan YAML**

`infra/docker/zap/requestor-plan.yaml`. Bám theo **schema thật** đã dán vào worklog ở Task 1 Step 5, không theo trí nhớ. Hình dạng dự kiến:

```yaml
env:
  contexts:
    - name: sentinel-dast
      urls:
        - http://gateway-dast:8081/WebGoat/
  parameters:
    failOnError: true
    progressToStdout: true

jobs:
  - type: requestor
    parameters:
      user: ""
    requests:
      - url: http://gateway-dast:8081/WebGoat/SqlInjection/attack2
        method: POST
        data: "query="
```

Trường `data` ở đây **không quyết định** thứ WebGoat nhận — lane thay bằng body chính tắc của nó. Đặt trùng canonical body chỉ để plan tự mô tả đúng ý định.

Nếu schema thật ở Task 1 khác chỗ nào thì theo schema thật và **ghi vào worklog chỗ khác biệt**.

- [ ] **Step 4: Chạy test để pass**

Run: `.venv/bin/python -m pytest tests/unit/infra/test_dast_requestor_plan.py -v`
Expected: PASS.

- [ ] **Step 5: Thêm lần gọi ZAP thứ hai vào `scan-zap.sh`**

Ngay **sau** khối `zap-baseline.py` hiện có (dòng ~66-73), **không sửa khối đó**:

```bash
# Lan goi ZAP THU HAI: cham toi cac endpoint POST da review, de chung minh
# reachability cho finding SAST tro vao @PostMapping. Baseline o tren khong bi
# dung toi — no dung --autooff vi Automation Framework bo qua ngu nghia exit
# cua -I, con lan goi nay thi khong dung -I.
"${compose[@]}" run --rm zap \
  /zap/zap.sh -cmd -autorun /zap/wrk/requestor-plan.yaml \
  <cac-tham-so-header-key-tu-Task-1-Step-6>
```

Thay `<cac-tham-so-header-key-tu-Task-1-Step-6>` bằng **đúng** tham số đã xác minh chạy được ở Task 1. Nếu Task 1 kết luận header phải khai trong plan YAML thì bỏ phần này.

Plan phải nằm trong `/zap/wrk` để container thấy — thêm vào `infra/docker/zap/Dockerfile`:

```dockerfile
COPY requestor-plan.yaml /zap/wrk/requestor-plan.yaml
```

- [ ] **Step 6: Không phá contract tĩnh của script**

Run: `.venv/bin/python -m pytest tests/unit/infra/test_zap_scan_script.py -v`
Expected: PASS. Đặc biệt `test_zap_targets_only_the_dast_gateway` — script vẫn không được chứa `http://webgoat:8080`.

- [ ] **Step 7: Chạy thật và xác minh access log**

```bash
make dast
grep -E "channel=dast method=POST" artifacts/dast/gateway-access.log
```
Expected: ít nhất một dòng `method=POST path=/WebGoat/... status=2xx`. Không có dòng nào nghĩa là `requestor` không chạy hoặc không qua Gateway — dừng, đọc log của lần gọi thứ hai.

- [ ] **Step 8: Commit**

```bash
git add infra/docker/zap/requestor-plan.yaml infra/docker/zap/Dockerfile \
        scripts/scan-zap.sh tests/unit/infra/test_dast_requestor_plan.py
git commit -m "feat(dast): requestor job chạm tới endpoint POST đã review"
```

---

## Task 5: Chỉ 2xx mới là reachable

**Files:**
- Modify: `src/project_sentinel/analysis/correlation.py`
- Modify: `tests/unit/analysis/test_correlation.py`

**Interfaces:**
- Produces: `parse_gateway_access_log` chỉ tính request có status 2xx.

- [ ] **Step 1: Viết test fail trước**

Thêm vào `tests/unit/analysis/test_correlation.py`:

```python
def test_a_redirect_is_not_reachable(tmp_path):
    """302 về /login nghĩa là KHÔNG chạm tới được.

    Trước đây điều kiện là `status >= 400`, nên 302 được tính là chạm tới được.
    Đó là đếm sai theo hướng LẠC QUAN — kiểu sai tệ nhất cho một công cụ đo độ
    phủ, vì nó làm reachability trông tốt hơn thực tế.
    """
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=GET "
        "path=/WebGoat/SqlInjection/attack2 query=- status=302 bytes=0 rt=0.01\n",
        encoding="utf-8",
    )
    assert parse_gateway_access_log(log)["endpoints"] == []


def test_a_2xx_post_is_reachable(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=POST "
        "path=/WebGoat/SqlInjection/attack2 query=- status=200 bytes=42 rt=0.05\n",
        encoding="utf-8",
    )
    endpoints = parse_gateway_access_log(log)["endpoints"]
    assert endpoints == [
        {"method": "POST", "path": "/WebGoat/SqlInjection/attack2", "params": []}
    ]


def test_a_204_is_reachable(tmp_path):
    """Toàn bộ dải 2xx, không chỉ 200."""
    log = tmp_path / "access.log"
    log.write_text(
        "2026-08-22T09:00:00+00:00 channel=dast method=POST "
        "path=/WebGoat/X/y query=- status=204 bytes=0 rt=0.01\n",
        encoding="utf-8",
    )
    assert len(parse_gateway_access_log(log)["endpoints"]) == 1
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v -k "redirect or 2xx or 204"`
Expected: `test_a_redirect_is_not_reachable` FAIL (302 đang được tính).

- [ ] **Step 3: Siết điều kiện**

Trong `src/project_sentinel/analysis/correlation.py`, thay:

```python
        status = int(match.group("status"))
        if status >= 400:
            continue
```

bằng:

```python
        status = int(match.group("status"))
        # CHI 2xx moi la cham toi duoc. Truoc day dieu kien la `>= 400`, nen mot
        # 302 ve /login — tuc la KHONG cham toi duoc — van duoc tinh la reachable.
        # Do la dem sai theo huong lac quan, kieu sai te nhat cho mot cong cu do
        # do phu.
        if not 200 <= status < 300:
            continue
```

- [ ] **Step 4: Chạy test để pass**

```bash
.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
```
Expected: PASS, không test cũ nào đỏ.

- [ ] **Step 5: Commit**

```bash
git add src/project_sentinel/analysis/correlation.py tests/unit/analysis/test_correlation.py
git commit -m "fix(dast): chỉ 2xx mới tính là chạm tới được, 302 thì không"
```

---

## Task 6: Test live, đo lại, và tài liệu

**Files:**
- Modify: `tests/integration/test_zap_gateway_live.py`
- Modify: `docs/limitations.md`, `docs/architecture.md`

**Interfaces:**
- Consumes: mọi thứ từ Task 1–5.

- [ ] **Step 1: Sửa test live đang giả định GET/HEAD-only**

Trong `tests/integration/test_zap_gateway_live.py`, hàm `test_gateway_log_proves_zap_requests_crossed_the_boundary` khẳng định mọi method ngoài GET/HEAD phải là 405. Nay POST hợp lệ trả 2xx. Thay khối đó:

```python
        if method.group(1) not in {"GET", "HEAD", "POST"}:
            assert status.group(1) == "405", line
        if method.group(1) == "POST":
            # POST chi hop le voi path co trong dast-allowlist.json. Moi POST
            # khac phai bi 405 ngay tai Gateway.
            assert status.group(1) in {"200", "204", "405"}, line
```

- [ ] **Step 2: Thêm test canary — bất biến quan trọng nhất**

```python
def test_zap_cannot_influence_the_body_webgoat_receives():
    """ZAP POST một canary; WebGoat phải nhận body chính tắc của lane.

    Đây là bản sao của test_a_reviewed_template_does_not_licence_an_unreviewed_body
    ở lane probe — test đó đã bắt được một bypass thật ở vòng review 82/100.
    """
    import json as _json

    allowlist = _json.loads(
        (REPO_ROOT / "configs/gateway/dast-allowlist.json").read_text(
            encoding="utf-8"
        )
    )["endpoints"]
    assert allowlist, "Không có mục nào để kiểm"
    path = allowlist[0]["path"]
    canary = "sentinel-canary-do-not-forward-9f3a2b"

    result = _request_from_inside_gateway(
        f'wget -S -O /tmp/resp --post-data="{canary}=1" '
        '--header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" '
        f'http://127.0.0.1:8081{path} 2>&1; cat /tmp/resp'
    )
    assert canary not in result.stdout, (
        "Canary của ZAP vọng lại trong response — body của caller đã tới WebGoat"
    )
    assert canary not in result.stderr


def test_post_to_an_unlisted_path_is_refused_at_the_gateway():
    result = _request_from_inside_gateway(
        'wget -S -O /dev/null --post-data="x=1" '
        '--header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" '
        "http://127.0.0.1:8081/WebGoat/login"
    )
    assert result.returncode != 0
    assert "405" in result.stderr


def test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path():
    """Report và log không được lộ thứ chưa duyệt."""
    combined = REPORT.read_text(encoding="utf-8") + GATEWAY_LOG.read_text(
        encoding="utf-8"
    )
    assert "sentinel-canary" not in combined
```

- [ ] **Step 3: Chạy test live thật**

```bash
make dast-test
```
Expected: PASS toàn bộ. Dán output vào worklog.

- [ ] **Step 4: Chạy đầu-cuối và đo phân bố mới**

```bash
KEY=$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env) \
  SENTINEL_GATEWAY_API_KEY="$KEY" \
  .venv/bin/python -m project_sentinel.cli run --yes
```

Rồi đo:

```bash
R=$(ls -td artifacts/runs/*/ | head -1)
.venv/bin/python -c "
import json, collections
d = json.load(open('$R/findings.json'))
c = collections.Counter(
    (f.get('runtime_evidence') or {}).get('strength')
    for f in d['findings'] if f.get('tool') != 'zap')
print('phan bo strength:', dict(c))
"
```

Mốc trước: `{'no_route': 4, 'route_known_not_reached': 19}`, `reachable: 0`.

**Cổng dừng:** nếu `reachable` vẫn bằng **0**, cả plan chưa đạt mục tiêu. DỪNG và báo người dùng kèm access log — đừng cập nhật tài liệu bằng một con số không đổi.

- [ ] **Step 5: Cập nhật `docs/limitations.md`**

Thay đoạn hiện ghi `{'no_route': 4, 'route_known_not_reached': 19}` và "không có `reachable`" bằng **số thật vừa đo**. Và thêm:

```markdown
- Lane DAST gửi được POST tới một danh sách endpoint đã review trong
  `configs/gateway/dast-allowlist.json`. Body là hằng số do Gateway quyết định,
  không phải do ZAP chọn — ZAP chỉ nêu path. Mỗi mục trong danh sách đó là một
  request thật vào một ứng dụng cố ý có lỗ hổng, và cổng bảo vệ duy nhất là
  người đọc `@RequestParam` rồi chọn body làm ít nhất có thể.
- Body chính tắc gắn với `webgoat:v2025.3`. Nâng WebGoat lên bản khác có thể đổi
  tên tham số; lúc đó POST vẫn trả 2xx nhưng không còn chứng minh điều gì. Test
  trích dẫn dòng nguồn bắt được nếu file đổi, **không** bắt được nếu chỉ tên
  tham số đổi.
- `reachable` nghĩa là endpoint tồn tại và chạm tới được, **không** nghĩa là lỗ
  hổng đã được chứng minh. `attacker_control` vẫn `not_proven`, nên `confirmed`
  vẫn ngoài tầm với.
```

- [ ] **Step 6: Cập nhật `docs/architecture.md`**

Ghi lane DAST giờ nhận POST cho path đã review, và phát biểu bất biến mới: *nội dung WebGoat nhận được từ lane DAST do lane quyết định hoàn toàn; ZAP không ảnh hưởng được method, path, header hay body.*

- [ ] **Step 7: Chạy toàn bộ nghiệm thu**

```bash
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests   # >= 926
make lint && make typecheck
make dast-test
make gateway-live-test
.venv/bin/python -m pytest tests/unit/infra/test_docs_complete.py tests/test_docs_are_honest.py -q
```

- [ ] **Step 8: Commit**

```bash
git add tests/integration/test_zap_gateway_live.py docs/limitations.md docs/architecture.md
git commit -m "test(dast): bằng chứng live cho POST và đồng bộ tài liệu"
```

---

## Nghiệm thu cuối

- [ ] `reachable` **lớn hơn 0** trong phân bố strength của một lần chạy thật
- [ ] Canary của ZAP không bao giờ tới WebGoat, không xuất hiện trong report hay log
- [ ] POST tới path chưa allowlist → 405 tại Gateway
- [ ] `proxy_pass_request_headers off` và `proxy_pass_request_body off` còn nguyên
- [ ] `zap` và `gateway-dast` vẫn không có `ports`
- [ ] `zap-baseline.py` và cờ `--autooff` không bị đụng
- [ ] `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` ≥ 926
- [ ] `make lint && make typecheck` xanh
- [ ] `make dast-test` và `make gateway-live-test` xanh
- [ ] Mỗi task có một worklog đủ 8 mục, số liệu là output chạy thật
