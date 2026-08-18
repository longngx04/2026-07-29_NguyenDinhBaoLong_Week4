# Bài tập tuần 4 — API Gateway kiểm soát request

Bài tập độc lập để hiểu một API Gateway kiểm soát truy cập endpoint như thế nào.
**Không** phải một phần của pipeline Project Sentinel; không import gì từ `src/`.

## Kiến trúc

```
tool.py ──X-API-Key──► gateway (127.0.0.1:9000) ──► target-app (nội bộ :8000)
                          │
                          ├─ thiếu / sai key        → 401
                          ├─ ngoài allowlist        → 403
                          ├─ quá 30 request/phút    → 429
                          └─ hợp lệ                 → proxy, trả response
```

Ứng dụng đích **không** mở cổng ra host. Đường duy nhất vào nó là qua gateway.

## Allowlist

`allowlist.json` cấu hình các endpoint được phép:

| Method | Path |
|---|---|
| GET | `/health` |
| GET | `/items` |
| POST | `/echo` |
| GET | `/echo-query` |

`/items/{id}`, `/admin`, `/debug` tồn tại trong app nhưng **không** có trong
allowlist. Gọi trực tiếp vào app thì chúng trả 200; gọi qua gateway thì 403.
Đó chính là điều bài tập muốn cho thấy: chốt chặn nằm ở gateway.

## Chạy

```bash
export EXERCISE_API_KEY="$(openssl rand -hex 16)"
docker compose -f compose.yml up --build --detach
sleep 5
python tool.py
docker compose -f compose.yml down
```

Kết quả mong đợi:

```
GET   /health    -> 200
GET   /items     -> 200
POST  /echo      -> 200
GET   /admin     -> 403
GET   /debug     -> 403
```

## Các ca chứng minh

| Ca | Kết quả | Test |
|---|---|---|
| `GET /health` với key hợp lệ | 200 | `test_allowlisted_endpoint_with_valid_key_reaches_upstream` |
| `GET /admin` ngoài allowlist | 403 | `test_endpoint_outside_allowlist_returns_403` |
| Thiếu hoặc sai API key | 401 | `test_missing_api_key_returns_401` |
| Vượt 30 request/phút | 429 | `test_exceeding_rate_limit_returns_429` |
| Chuyển tiếp query string | 200, query bảo toàn | `test_query_string_is_forwarded_to_upstream` |
| Timeout | không sập, trả lỗi | `test_send_handles_timeout_without_raising` |
| Mất kết nối | không sập, trả lỗi | `test_send_handles_connection_error_without_raising` |
| Giới hạn preview response | tối đa 512 ký tự | `test_body_preview_is_bounded` |

Cộng thêm `test_api_key_never_appears_in_the_request_log`: log ghi
method/path/status nhưng không bao giờ ghi API key.

## Chạy test

```bash
cd exercises/week4-gateway
make exercise-test
```

Test tự bật app và gateway thật. Không có mock: chạm không tới thì fail.

## Nhật ký

Gateway ghi `requests.jsonl` tại `exercises/week4-gateway/`, mỗi dòng một request:

```json
{"ts": "2026-08-17T10:15:30Z", "method": "GET", "path": "/health", "status": 200, "elapsed_ms": 4.21}
```

Log ghi method/path/status nhưng không bao giờ ghi API key, và cũng không
ghi query string — query có thể chứa token.

