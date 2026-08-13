# Task cho Coding Agent: Triển khai Tuần 4 — API Gateway & Safe Test Request Tool
### Project Sentinel — repo: `longngx04/2026-07-29_NguyenDinhBaoLong_Week3`

---

## Phase 0 — Bối cảnh & ràng buộc cứng (đọc trước khi làm bất cứ việc gì)

**Bối cảnh:** Repo đã có sẵn pipeline Tuần 1–3 (`src/project_sentinel/{ingestion,analysis,retrieval,llm}`, `configs/`, `tests/`, `reports/week-01..03`). Nhiệm vụ này thêm một tính năng mới: một API Gateway (Nginx) đứng trước ứng dụng thử nghiệm WebGoat, và một Python tool gửi request kiểm thử an toàn qua gateway đó.

**Ràng buộc cứng — KHÔNG được vi phạm, không cần hỏi lại:**

1. Package mới `src/project_sentinel/gateway/` **tuyệt đối không** import bất cứ gì từ `project_sentinel.analysis` hoặc `project_sentinel.llm`. Đây là feature độc lập, không tích hợp Security Analysis Agent (quyết định đã chốt với mentor).
2. Payload gửi đi chỉ được lấy từ một bảng cố định 4 loại (`long_string`, `special_chars`, `empty_value`, `wrong_type`) định nghĩa trong code. **Không** implement bất kỳ cách nào cho phép truyền chuỗi tấn công tự do (SQLi thật, XSS thật, path traversal, shell injection...) làm payload.
3. WebGoat **không được** expose port ra host trực tiếp nữa sau khi xong Phase 1 — chỉ gateway mới lộ ra `127.0.0.1`.
4. API key (biến môi trường `SENTINEL_API_KEY`) và mọi HTTP header của request **không bao giờ** được ghi vào file log dưới bất kỳ hình thức nào, kể cả khi debug. Không viết `print(headers)` hay tương tự rồi quên xoá.
5. Không commit `.env` hoặc bất kỳ giá trị API key thật nào vào git. Kiểm tra `.gitignore` đã che `.env` trước khi tạo commit đầu tiên.
6. Trước khi kết thúc mỗi Phase bên dưới, **chạy lệnh kiểm tra ở mục "Gate"** của phase đó và xác nhận PASS. Nếu FAIL, sửa cho tới khi pass rồi mới sang phase tiếp theo — không được bỏ qua gate để "làm cho xong".
7. Nếu phát hiện quy ước đã có trong repo (ví dụ exit code CLI, style logging, cấu trúc test) khác với đề xuất trong tài liệu này, **ưu tiên theo quy ước đã có sẵn trong repo** để giữ nhất quán, và ghi chú lại sự khác biệt đó trong report cuối (Phase 7).

**Danh sách file/thư mục sẽ tạo mới hoặc sửa (tổng quan):**

```
infra/docker/gateway/{Dockerfile,nginx.conf,templates/default.conf.template}
configs/gateway/allowlist.yaml
src/project_sentinel/gateway/{__init__.py,models.py,allowlist.py,payloads.py,client.py,request_log.py,cli.py}
tests/{test_gateway_allowlist.py,test_gateway_payloads.py,test_gateway_client.py,test_gateway_log_redaction.py,test_gateway_cli.py}
tests/integration/test_gateway_live.py   (optional)
docker-compose.yml        (sửa)
.env.example               (sửa)
Makefile                    (sửa)
pyproject.toml              (sửa — thêm httpx, pyyaml, respx nếu chưa có)
reports/week-04/report.md
```

---

## Phase 1 — Hạ tầng: Nginx Gateway + Docker Compose

**Mục tiêu:** Dựng được một reverse proxy Nginx đứng trước WebGoat, enforce API key + allowlist ở tầng hạ tầng.

**Việc cần làm:**

1. Tạo `infra/docker/gateway/Dockerfile`:

```dockerfile
FROM nginx:1.27-alpine
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/00-limits.conf
EXPOSE 8080
```

2. Tạo `infra/docker/gateway/nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=sentinel_rl:10m rate=30r/m;

log_format sentinel_access
  '$time_iso8601 method=$request_method path=$uri status=$status '
  'bytes=$body_bytes_sent rt=$request_time';

access_log /dev/stdout sentinel_access;
```

3. Tạo `infra/docker/gateway/templates/default.conf.template`:

```nginx
map $http_x_sentinel_key $sentinel_key_valid {
    default 0;
    "${SENTINEL_API_KEY}" 1;
}

server {
    listen 8080;

    location = /WebGoat/actuator/health {
        if ($sentinel_key_valid = 0) { return 401; }
        proxy_pass http://webgoat:8080;
        proxy_connect_timeout 3s;
        proxy_read_timeout 5s;
    }

    location /WebGoat/attack {
        if ($sentinel_key_valid = 0) { return 401; }
        limit_req zone=sentinel_rl burst=5 nodelay;
        client_max_body_size 64k;
        proxy_connect_timeout 3s;
        proxy_read_timeout 5s;
        proxy_pass http://webgoat:8080;
    }

    location / {
        return 403;
    }
}
```

   Lưu ý: `${SENTINEL_API_KEY}` được `envsubst` thay thế lúc container start (tính năng có sẵn của ảnh `nginx` chính chủ khi file nằm trong `/etc/nginx/templates/`). Không đổi tên biến này thành thứ trùng với biến nội bộ Nginx.

4. Sửa `docker-compose.yml`:
   - Service `webgoat`: đổi `ports:` thành `expose: ["8080"]`, thêm `healthcheck` gọi `/WebGoat/actuator/health`, gắn vào network `sentinel-net`.
   - Thêm service `gateway`: build từ `./infra/docker/gateway`, `ports: ["127.0.0.1:9080:8080"]`, `environment: [SENTINEL_API_KEY=${SENTINEL_API_KEY:?missing SENTINEL_API_KEY in .env}]`, `depends_on: webgoat: condition: service_healthy`, cùng network `sentinel-net`.
   - Thêm khai báo `networks: sentinel-net: driver: bridge` nếu chưa có network tương đương trong file.

5. Thêm dòng `SENTINEL_API_KEY=` vào `.env.example`. Không điền giá trị thật.

### Gate kiểm tra (bắt buộc pass trước khi sang Phase 2)

```bash
export SENTINEL_API_KEY=$(openssl rand -hex 32)
echo "SENTINEL_API_KEY=$SENTINEL_API_KEY" >> .env
docker compose up -d --build gateway webgoat

# (1) sai key -> 401
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9080/WebGoat/actuator/health
# expect: 401

# (2) đúng key, endpoint allowlist -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-Sentinel-Key: $SENTINEL_API_KEY" http://127.0.0.1:9080/WebGoat/actuator/health
# expect: 200

# (3) đúng key, endpoint ngoài allowlist -> 403
curl -s -o /dev/null -w "%{http_code}\n" -H "X-Sentinel-Key: $SENTINEL_API_KEY" http://127.0.0.1:9080/WebGoat/login
# expect: 403

# (4) WebGoat không còn lộ port trực tiếp
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/WebGoat/actuator/health
# expect: lỗi connection refused (không phải một status code HTTP)
```

Cả 4 lệnh phải cho kết quả đúng như expect trước khi tạo bất kỳ file Python nào ở phase sau.

---

## Phase 2 — Allowlist: config + module Python

**Mục tiêu:** Một nguồn cấu hình allowlist mà Python đọc được, có thể validate (method, path) trước khi gọi mạng.

1. Tạo `configs/gateway/allowlist.yaml`:

```yaml
allowlist:
  - method: GET
    path: /WebGoat/actuator/health
    match: exact
  - method: GET
    path: /WebGoat/attack
    match: prefix
  - method: POST
    path: /WebGoat/attack
    match: prefix
```

2. Tạo `src/project_sentinel/gateway/__init__.py` (rỗng hoặc export public API).

3. Tạo `src/project_sentinel/gateway/allowlist.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
import yaml


@dataclass(frozen=True)
class AllowlistRule:
    method: str
    path: str
    match: str  # "exact" | "prefix"


class Allowlist:
    def __init__(self, rules: list[AllowlistRule]):
        self._rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "Allowlist":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = [AllowlistRule(**r) for r in data.get("allowlist", [])]
        if not rules:
            raise ValueError(f"Allowlist rỗng hoặc không hợp lệ: {path}")
        return cls(rules)

    def is_allowed(self, method: str, path: str) -> bool:
        method = method.upper()
        for rule in self._rules:
            if rule.method.upper() != method:
                continue
            if rule.match == "exact" and path == rule.path:
                return True
            if rule.match == "prefix" and path.startswith(rule.path):
                return True
        return False
```

4. Tạo `tests/test_gateway_allowlist.py` với tối thiểu các case:
   - exact match đúng path → `True`
   - exact match sai path → `False`
   - prefix match với path con → `True`
   - method không khớp cùng path → `False`
   - load file allowlist rỗng → raise `ValueError`

### Gate

```bash
pytest tests/test_gateway_allowlist.py -v
# tất cả test PASS
```

---

## Phase 3 — Payload cố định + Models + Logging an toàn

**Mục tiêu:** Payload chỉ chọn được từ enum cố định; logging không có đường nào nhận secret.

1. Tạo `src/project_sentinel/gateway/models.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class SafePayloadType(str, Enum):
    LONG_STRING = "long_string"
    SPECIAL_CHARS = "special_chars"
    EMPTY_VALUE = "empty_value"
    WRONG_TYPE = "wrong_type"


class GatewayErrorType(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    FORBIDDEN_BY_ALLOWLIST = "forbidden_by_allowlist"
    HTTP_ERROR = "http_error"


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    status_code: int | None
    body_preview: str | None
    error_type: GatewayErrorType | None
    elapsed_ms: float
```

2. Tạo `src/project_sentinel/gateway/payloads.py`:

```python
from __future__ import annotations
from typing import Any
from .models import SafePayloadType

SAFE_PAYLOADS: dict[SafePayloadType, Any] = {
    SafePayloadType.LONG_STRING: "A" * 5000,
    SafePayloadType.SPECIAL_CHARS: "!@#$%^&*()'\"<>;",
    SafePayloadType.EMPTY_VALUE: "",
    SafePayloadType.WRONG_TYPE: 12345,
}
```

3. Tạo `src/project_sentinel/gateway/request_log.py`:

```python
from __future__ import annotations
import json
import time
from pathlib import Path
from .models import GatewayErrorType


def log_request(
    log_path: str,
    method: str,
    path: str,
    payload_type: str | None,
    status_code: int | None,
    error_type: GatewayErrorType | None,
    elapsed_ms: float,
) -> None:
    """Chữ ký hàm CHỈ nhận field đã biết trước là an toàn — không có
    tham số headers/body nào ở đây, nên không có cách nào vô tình log
    API key. Không thêm tham số mới vào hàm này mà không xem lại ràng
    buộc số 4 ở Phase 0."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": method,
        "path": path,
        "payload_type": payload_type,
        "status_code": status_code,
        "error_type": error_type.value if error_type else None,
        "elapsed_ms": round(elapsed_ms, 1),
    }
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

4. Tạo `tests/test_gateway_payloads.py`:
   - `SAFE_PAYLOADS` có đúng 4 key, khớp với `SafePayloadType`.
   - Không giá trị nào trong `SAFE_PAYLOADS.values()` chứa các chuỗi nguy hiểm điển hình: `"; rm"`, `"DROP TABLE"`, `"../../"`, `"<script>"` (test bằng cách assert các substring này không xuất hiện trong bất kỳ giá trị string nào).

### Gate

```bash
pytest tests/test_gateway_payloads.py -v
# tất cả test PASS
```

---

## Phase 4 — `GatewayClient`

**Mục tiêu:** Client Python gọi qua gateway, tự chặn theo allowlist trước khi ra mạng, có timeout, giới hạn kích thước response, xử lý lỗi mạng.

1. Thêm dependency vào `pyproject.toml` nếu chưa có: `httpx`, `pyyaml` (runtime), `respx` (dev, dùng cho test).

2. Tạo `src/project_sentinel/gateway/client.py`:

```python
from __future__ import annotations
import time
import httpx
from .allowlist import Allowlist
from .models import GatewayResult, GatewayErrorType, SafePayloadType
from .payloads import SAFE_PAYLOADS
from .request_log import log_request


class GatewayClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        allowlist: Allowlist,
        log_path: str,
        timeout_s: float = 5.0,
        max_response_bytes: int = 65_536,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._allowlist = allowlist
        self._log_path = log_path
        self._timeout = timeout_s
        self._max_bytes = max_response_bytes

    def request(
        self,
        method: str,
        path: str,
        payload_type: SafePayloadType | None = None,
        target_field: str | None = None,
    ) -> GatewayResult:
        if not self._allowlist.is_allowed(method, path):
            log_request(self._log_path, method, path,
                        payload_type.value if payload_type else None,
                        None, GatewayErrorType.FORBIDDEN_BY_ALLOWLIST, 0.0)
            return GatewayResult(False, None, None,
                                  GatewayErrorType.FORBIDDEN_BY_ALLOWLIST, 0.0)

        body = None
        if payload_type is not None and target_field is not None:
            body = {target_field: SAFE_PAYLOADS[payload_type]}

        headers = {"X-Sentinel-Key": self._api_key}
        start = time.monotonic()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream(
                    method, f"{self._base_url}{path}", headers=headers, json=body
                ) as resp:
                    chunks, total = [], 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > self._max_bytes:
                            chunks.append(chunk[: max(0, self._max_bytes - (total - len(chunk)))])
                            break
                        chunks.append(chunk)
                    preview = b"".join(chunks).decode("utf-8", errors="replace")
                    elapsed = (time.monotonic() - start) * 1000
                    log_request(self._log_path, method, path,
                                payload_type.value if payload_type else None,
                                resp.status_code, None, elapsed)
                    return GatewayResult(resp.status_code < 400, resp.status_code,
                                          preview, None, elapsed)
        except httpx.TimeoutException:
            elapsed = (time.monotonic() - start) * 1000
            log_request(self._log_path, method, path,
                        payload_type.value if payload_type else None,
                        None, GatewayErrorType.TIMEOUT, elapsed)
            return GatewayResult(False, None, None, GatewayErrorType.TIMEOUT, elapsed)
        except httpx.ConnectError:
            elapsed = (time.monotonic() - start) * 1000
            log_request(self._log_path, method, path,
                        payload_type.value if payload_type else None,
                        None, GatewayErrorType.CONNECTION, elapsed)
            return GatewayResult(False, None, None, GatewayErrorType.CONNECTION, elapsed)
```

   Ràng buộc bắt buộc: biến `headers` (chứa API key) chỉ được dùng cục bộ trong `request()`, không bao giờ truyền vào `log_request()`.

3. Tạo `tests/test_gateway_client.py`, dùng `respx` để mock `httpx` (không gọi mạng thật):
   - Case 200 OK → `GatewayResult.ok is True`, `status_code == 200`.
   - Case response lớn hơn `max_response_bytes` → `body_preview` bị cắt đúng độ dài tối đa.
   - Mock raise `httpx.TimeoutException` → `error_type == GatewayErrorType.TIMEOUT`.
   - Mock raise `httpx.ConnectError` → `error_type == GatewayErrorType.CONNECTION`.
   - Path ngoài allowlist → gọi `request()`, assert **route mock không được gọi lần nào** (`respx` route call count == 0) — đây là bằng chứng client chặn tại local trước khi ra mạng.

### Gate

```bash
pytest tests/test_gateway_client.py -v
# tất cả test PASS, không có network call thật nào (chạy được cả khi tắt mạng)
```

---

## Phase 5 — CLI + Makefile

**Mục tiêu:** Một lệnh CLI chạy được từ terminal, exit code phản ánh đúng kết quả.

1. Tạo `src/project_sentinel/gateway/cli.py`:

```python
from __future__ import annotations
import argparse
import os
import sys
from .allowlist import Allowlist
from .client import GatewayClient
from .models import SafePayloadType

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_BLOCKED = 3
EXIT_NETWORK_ERROR = 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    req = sub.add_parser("request")
    req.add_argument("--method", required=True)
    req.add_argument("--path", required=True)
    req.add_argument("--payload-type", choices=[p.value for p in SafePayloadType])
    req.add_argument("--target-field")
    req.add_argument("--base-url", default="http://127.0.0.1:9080")
    req.add_argument("--allowlist", default="configs/gateway/allowlist.yaml")
    req.add_argument("--log-path", default="artifacts/gateway/requests.log.jsonl")

    args = parser.parse_args(argv)

    api_key = os.environ.get("SENTINEL_API_KEY")
    if not api_key:
        print("Lỗi: thiếu biến môi trường SENTINEL_API_KEY", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        allowlist = Allowlist.from_yaml(args.allowlist)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Lỗi cấu hình allowlist: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    client = GatewayClient(args.base_url, api_key, allowlist, args.log_path)
    payload_type = SafePayloadType(args.payload_type) if args.payload_type else None
    result = client.request(args.method, args.path, payload_type, args.target_field)

    if result.error_type and result.error_type.value == "forbidden_by_allowlist":
        print("Bị chặn: endpoint không nằm trong allowlist", file=sys.stderr)
        return EXIT_BLOCKED
    if result.error_type and result.error_type.value in ("timeout", "connection"):
        print(f"Lỗi mạng: {result.error_type.value}", file=sys.stderr)
        return EXIT_NETWORK_ERROR

    print(f"status={result.status_code} elapsed_ms={result.elapsed_ms}")
    print(result.body_preview[:500] if result.body_preview else "(empty)")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

   **Trước khi viết file này**, mở `src/project_sentinel/cli.py` hiện có (Tuần 3) và kiểm tra quy ước exit code đang dùng — nếu khác với 0/2/3/4 ở trên, đổi lại cho khớp và ghi chú vào report.

2. Thêm vào `Makefile`:

```makefile
gateway-build:
	docker compose build gateway

gateway-up:
	docker compose up -d gateway webgoat

gateway-down:
	docker compose down

gateway-test:
	pytest tests/test_gateway_*.py -v

gateway-demo:
	python -m project_sentinel.gateway.cli request --method GET --path /WebGoat/actuator/health
```

3. Tạo `tests/test_gateway_cli.py` (mock `GatewayClient.request`, không cần Docker):
   - Thiếu `SENTINEL_API_KEY` trong env → exit code 2.
   - Allowlist file không tồn tại → exit code 2.
   - `request()` trả `FORBIDDEN_BY_ALLOWLIST` → exit code 3.
   - `request()` trả `TIMEOUT`/`CONNECTION` → exit code 4.
   - `request()` trả kết quả OK → exit code 0.

### Gate

```bash
pytest tests/test_gateway_cli.py -v
make gateway-up
make gateway-demo
# in ra "status=200 ..."
make gateway-down
```

---

## Phase 6 — Redaction test + (tuỳ chọn) integration test thật

**Mục tiêu:** Có bằng chứng tự động (không chỉ nhìn bằng mắt) rằng log không bao giờ chứa API key.

1. Tạo `tests/test_gateway_log_redaction.py`:
   - Gọi `GatewayClient(...).request(...)` với `api_key="SENTINEL_TEST_MARKER_VALUE"` (mock httpx bằng `respx` để không cần gateway thật).
   - Đọc lại file log vừa ghi, `assert "SENTINEL_TEST_MARKER_VALUE" not in content`.
   - Test cả 3 nhánh: response OK, timeout, forbidden-by-allowlist — cả 3 đều phải không rò rỉ key.

2. (Tuỳ chọn, làm nếu còn thời gian) Tạo `tests/integration/test_gateway_live.py`, đánh dấu `@pytest.mark.integration`, mặc định skip trong `pytest.ini`/`pyproject.toml` test config, chỉ chạy thủ công khi có `docker compose up -d gateway webgoat` đang sống. Test này gọi CLI thật (subprocess hoặc gọi `main()` trực tiếp) tới gateway thật, xác nhận status code như ở Phase 1 Gate.

### Gate

```bash
pytest tests/test_gateway_log_redaction.py -v
# PASS, và thử thủ công: grep -R "SENTINEL_TEST_MARKER_VALUE" artifacts/ reports/ → không có kết quả nào
```

---

## Phase 7 — Tài liệu & Definition of Done cuối cùng

**Mục tiêu:** Repo tự giải thích được cho người review, không cần hỏi thêm.

1. Viết `reports/week-04/report.md` theo cấu trúc các report Tuần 1–3 đã có, bao gồm bắt buộc các mục:
   - Kiến trúc (có thể mô tả lại luồng: CLI/kịch bản thủ công → GatewayClient → Nginx Gateway → WebGoat).
   - **Một đoạn ghi rõ**: đã thống nhất với mentor không tích hợp Security Analysis Agent (Tuần 3) ở giai đoạn này; việc này dời sang Tuần 6, và interface của `GatewayClient` (method, path, payload_type, target_field → `GatewayResult`) đã được thiết kế để Tuần 6 gọi vào mà không cần sửa lại package `gateway/`.
   - Đặc tả allowlist & API key.
   - Bảng liệt kê 4 loại safe payload và lý do không cho phép payload tự do.
   - Bảng test coverage (liệt kê từng file test + mục đích, giống bảng ở Phase 2–6 phía trên).
   - Giới hạn đã biết (ví dụ: `allowlist.yaml` và file Nginx template là hai nguồn cấu hình riêng biệt, có rủi ro lệch nhau nếu không đồng bộ thủ công).
   - Hướng dẫn chạy lại (`make gateway-up`, `make gateway-demo`, `make gateway-test`).

2. Cập nhật `README.md` gốc: thêm mục "Tuần 4" trỏ tới `reports/week-04/report.md` và lệnh chạy nhanh.

3. Chạy toàn bộ checklist sau, tick từng dòng, KHÔNG coi là xong nếu còn dòng nào chưa pass:

```
[ ] make gateway-test           -> toàn bộ test gateway pass
[ ] make gateway-up && make gateway-demo -> in ra status=200
[ ] curl sai key      -> 401
[ ] curl path ngoài allowlist -> 403
[ ] curl thẳng port 8080 (WebGoat) -> connection refused
[ ] grep API key thật trong toàn bộ log/report đã tạo -> không có kết quả
[ ] git status không có .env hoặc secret nào staged
[ ] src/project_sentinel/gateway/ không import project_sentinel.analysis hoặc project_sentinel.llm
      (kiểm tra: grep -R "project_sentinel.analysis\|project_sentinel.llm" src/project_sentinel/gateway/)
[ ] reports/week-04/report.md tồn tại và có đủ các mục ở trên
```

Chỉ báo cáo "Tuần 4 hoàn thành" sau khi toàn bộ checklist trên đều pass.