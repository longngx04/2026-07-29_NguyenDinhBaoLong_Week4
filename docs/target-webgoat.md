# Target thử nghiệm — OWASP WebGoat

> WebGoat là ứng dụng **cố ý chứa lỗ hổng**. Nó chỉ chạy trong mạng nội bộ của
> Docker Compose và không bao giờ được mở ra host hay Internet.

## Kiến trúc

WebGoat là ứng dụng Spring Boot đóng gói sẵn (`webgoat/webgoat:v2025.3`), chạy
trên cổng 8080 trong mạng `sentinel-net`. Nó **không** khai báo `ports`, nên
không tiếp cận được từ host.

Mọi request đi vào WebGoat đều phải qua Nginx Gateway — thành phần duy nhất
bind cổng loopback `127.0.0.1:9080`. Gateway kiểm tra header
`X-Sentinel-API-Key`, áp rate limit 30 request/phút, rồi mới proxy vào trong.

```
Python tool ──X-Sentinel-API-Key──► Gateway (127.0.0.1:9080) ──► WebGoat (nội bộ :8080)
```

Mã nguồn Java của WebGoat nằm ở submodule `benchmarks/targets/webgoat/`, và đây
là thứ OpenGrep quét ở bước 1 của pipeline.

## Endpoint chính

Chỉ hai endpoint dưới đây nằm trong allowlist. Mọi đường dẫn khác bị Gateway
từ chối. Nguồn sự thật là `configs/gateway/endpoint-allowlist.json`.

| Endpoint | Method | Mục đích |
|---|---|---|
| `/WebGoat/actuator/health` | GET | Kiểm tra WebGoat còn sống qua Gateway |
| `/WebGoat/attack` | GET, POST | Điểm vào bài học WebGoat, chỉ nhận probe lành tính đã duyệt |

Giới hạn cho cả hai: response tối đa 65.536 byte; header được phép chỉ gồm
`Accept` và `User-Agent` với giá trị đã liệt kê sẵn.

## Cảnh báo đã phát hiện

Chạy `make scan` sinh ra `artifacts/raw/opengrep.json`.

| Rule | Số lượng |
|---|---|
| `configs.opengrep.java-sql-statement-execution` | 20 |
| `configs.opengrep.java-unsafe-deserialization` | 2 |
| `configs.opengrep.java-command-execution` | 1 |

Tổng số finding: 23. Xem `make normalize` để đổi sang định dạng chuẩn hoá.

## Cách chạy lại

```bash
make scan                 # quét mã nguồn WebGoat
make target-up            # bật WebGoat + Gateway
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9080/WebGoat/actuator/health   # 401, đúng như mong đợi
make target-down
```