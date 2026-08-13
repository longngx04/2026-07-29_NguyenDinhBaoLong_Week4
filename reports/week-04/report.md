# Báo Cáo Triển Khai Tuần 4 — API Gateway & Safe Test Request Tool

---

## 1. Kiến Trúc Tổng Quan (Architecture Overview)

Tuần 4 triển khai tầng hạ tầng kiểm thử an toàn (API Gateway) đứng trước ứng dụng WebGoat và công cụ gửi request kiểm thử độc lập (`GatewayClient`).

```text
+-----------------------+          HTTP Request (X-Sentinel-Key)           +-----------------------+                      +-----------------------+
|  Gateway CLI / Client | -----------------------------------------------> | Nginx API Gateway     | -------------------> | OWASP WebGoat         |
| (project_sentinel)    | <----------------------------------------------- | (127.0.0.1:9080)      | <------------------- | (sentinel-net:8080)   |
+-----------------------+          HTTP Response (Max 64KB)                +-----------------------+                      +-----------------------+
           |
           v (Strict Redaction - No Key / Headers)
+-----------------------+
| JSONL Request Logs    |
| (artifacts/gateway/)  |
+-----------------------+
```

> [!NOTE]
> **Quyết định Tích hợp Architecture (Tích hợp ở Tuần 6):**
> Theo đúng thống nhất với Mentor, package `src/project_sentinel/gateway/` tuyệt đối **không import** bất kỳ module nào từ `project_sentinel.analysis` hay `project_sentinel.llm`. Công cụ gateway được phát triển độc lập; interface của `GatewayClient` (`method`, `path`, `payload_type`, `target_field` -> `GatewayResult`) được chuẩn hóa sẵn sàng để Security Analysis Agent ở Tuần 6 gọi tới mà không cần thay đổi package `gateway/`.

---

## 2. Đặc Tả Allowlist & Xác Thực API Key (API Key & Allowlist Specification)

### 2.1 API Key Verification (Tầng Hạ Tầng Nginx)
* Nginx Gateway kiểm tra HTTP Header `X-Sentinel-Key` với biến môi trường `SENTINEL_API_KEY`.
* Nếu key không khớp hoặc thiếu header `X-Sentinel-Key`: Nginx lập tức trả về **HTTP 401 Unauthorized**.

### 2.2 Endpoint Allowlist Rules
Allowlist được định nghĩa tại `configs/gateway/allowlist.yaml` và được kiểm tra **2 lần**:
1. **Local Check (GatewayClient Python):** Kiểm tra trước khi ra mạng. Nếu endpoint không nằm trong allowlist, request bị chặn ngay tại chỗ (`FORBIDDEN_BY_ALLOWLIST`) và không gửi bất kỳ HTTP packet nào ra ngoài.
2. **Infrastructure Check (Nginx Gateway):** Kiểm tra tại tầng Nginx `location`. Endpoint ngoài allowlist nhận về **HTTP 403 Forbidden**.

Bảng Allowlist mặc định:

| Method | Path Matching Pattern | Match Type | Mục Đích |
| :--- | :--- | :--- | :--- |
| `GET` | `/WebGoat/actuator/health` | `exact` | Healthcheck endpoint của ứng dụng WebGoat |
| `GET` | `/WebGoat/attack` | `prefix` | Các bài tập kiểm thử WebGoat |
| `POST` | `/WebGoat/attack` | `prefix` | Các bài tập submission trên WebGoat |

---

## 3. Bảng Payload Cố Định & Nguyên Tắc An Toàn (Safe Payloads)

Để tuân thủ tuyệt đối quy tắc **không gây nguy hại cho hệ thống target** và không gửi chuỗi tấn công tự do (SQLi, XSS, Path Traversal, Shell Injection), hệ thống sử dụng duy nhất enum 4 loại payload cố định:

| Payload Type (`SafePayloadType`) | Giá Trị Thực Tế | Lý Do An Toàn & Mục Đích Kiểm Thử |
| :--- | :--- | :--- |
| `LONG_STRING` | `"A" * 5000` | Kiểm tra khả năng xử lý chuỗi dài (Buffer/Length Validation). Không chứa ký tự điều khiển hay payload tấn công. |
| `SPECIAL_CHARS` | `"!@#$%^&*()'\"<>;"` | Kiểm tra sanitization ký tự đặc biệt cơ bản. Không chứa các pattern độc hại như `<script>` hay `DROP TABLE`. |
| `EMPTY_VALUE` | `""` | Kiểm tra boundary khi input trống (Empty Value Handling). |
| `WRONG_TYPE` | `12345` | Kiểm tra Type Mismatch khi truyền kiểu integer cho field chuỗi. |

---

## 4. Ma Trận Test Coverage (Test Coverage Matrix)

| Test File | Phạm Vi & Mục Đích Kiểm Thử | Môi Trường |
| :--- | :--- | :--- |
| [`tests/test_gateway_allowlist.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/test_gateway_allowlist.py) | Kiếm thử matching rule `exact`, `prefix`, sai path, sai method, và xử lý file YAML rỗng. | Offline Unit Test |
| [`tests/test_gateway_payloads.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/test_gateway_payloads.py) | Kiểm thử enum 4 payload và assert không chứa bất kỳ pattern nguy hiểm nào. | Offline Unit Test |
| [`tests/test_gateway_client.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/test_gateway_client.py) | Mock HTTP request với `respx`: test response 200 OK, cắt ngắn response >64KB, timeout handling, connect error, và local allowlist block. | Offline Unit Test |
| [`tests/test_gateway_cli.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/test_gateway_cli.py) | Kiểm thử CLI exit codes (0: OK, 2: Config Error, 3: Blocked, 4: Network Error). | Offline Unit Test |
| [`tests/test_gateway_log_redaction.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/test_gateway_log_redaction.py) | Kiểm thử khẳng định API Key/Headers KHÔNG BAO GIỜ bị ghi vào file log dưới mọi trường hợp. | Offline Unit Test |
| [`tests/integration/test_gateway_live.py`](file:///home/longngx04/VinSOC/project_sentinel_main/tests/integration/test_gateway_live.py) | Integration test gửi request thật qua Nginx Gateway `127.0.0.1:9080` tới WebGoat container. | Live Integration Test |

---

## 5. Giới Hạn Đã Biết (Known Limitations)

1. **Dual Configuration Maintenance:** Cấu hình allowlist được khai báo độc lập ở 2 nơi: file YAML (`configs/gateway/allowlist.yaml`) cho Python Client và file Nginx template (`infra/docker/gateway/templates/default.conf.template`) cho Nginx Gateway. Khi thay đổi allowlist, cần cập nhật đồng bộ cả 2 nơi.
2. **Payload Constrained Scope:** Việc giới hạn cố định 4 loại safe payload giúp đảm bảo an toàn tuyệt đối nhưng không phục vụ mục đích fuzzing động phức tạp (đây là tính năng cố ý theo thiết kế bảo mật).

---

## 6. Hướng Dẫn Chạy (Quick Start Commands)

```bash
# 1. Chạy toàn bộ bộ test suite gateway (offline + integration)
make gateway-test

# 2. Khởi chạy Gateway và WebGoat container
make gateway-up

# 3. Chạy demo gửi request an toàn qua Gateway
make gateway-demo

# 4. Tắt container
make gateway-down
```
