# Target thử nghiệm — OWASP WebGoat

> WebGoat là ứng dụng **cố ý chứa lỗ hổng**. Nó chỉ chạy trong mạng nội bộ của
> Docker Compose và không bao giờ được mở ra host hay Internet.

## Kiến trúc

WebGoat là ứng dụng Spring Boot đóng gói sẵn (`webgoat/webgoat:v2025.3`), chạy
trên cổng 8080 trong mạng `sentinel-net`. Nó **không** khai báo `ports`, nên
không tiếp cận được từ host.

Mọi request do Sentinel tạo đi vào WebGoat đều phải qua một trong hai lane Nginx
Gateway. Chỉ lane Agent bind cổng loopback `127.0.0.1:9080`; lane DAST và WebGoat
đều không publish cổng host.

```
Python tool ──X-Sentinel-API-Key──► Gateway Agent (127.0.0.1:9080) ─┐
ZAP baseline ─X-Sentinel-DAST-Key► gateway-dast (nội bộ :8081) ────┤
                                                                    ▼
                                                    WebGoat (nội bộ :8080)
```

Lane Agent áp allowlist request chính xác, cổng phê duyệt và rate limit 30 request/phút.
Lane DAST chỉ tồn tại trong profile `dast`, dùng khoá tạm riêng, chỉ nhận `GET`/`HEAD`
trong `/WebGoat/`, bỏ body và header do ZAP gửi, và áp giới hạn 120 request/phút.

Đặc biệt, cấu hình Spring Security của WebGoat (`WebSecurityConfig.java:34-44`) chỉ mở `permitAll`
cho các tài nguyên công khai (`/login`, `/registration`, `/css/**`, `/images/**`, `/js/**`, `/plugins/**`).
Mọi bài học bảo mật thực sự (`/WebGoat/SqlInjection/**`, `/WebGoat/start.mvc`, v.v.) đều yêu cầu phiên
đăng nhập. Gateway DAST tự động đăng nhập user thử nghiệm tại thời điểm khởi động container và tiêm
`JSESSIONID` vào request forward, giúp ZAP spider được toàn bộ bề mặt bài học mà ZAP không cần biết thông tin tài khoản.

Mã nguồn Java của WebGoat nằm ở submodule `benchmarks/targets/webgoat/`, và đây
là thứ OpenGrep quét ở bước 1 của pipeline.


## Endpoint chính

Chỉ ba endpoint dưới đây nằm trong **allowlist của lane Agent**. Mọi đường dẫn khác
ở lane này bị Gateway từ chối. Nguồn sự thật là
`configs/gateway/endpoint-allowlist.json`.

| Endpoint | Method | Mục đích |
|---|---|---|
| `/WebGoat/actuator/health` | GET | Kiểm tra WebGoat còn sống qua Gateway |
| `/WebGoat/login` | GET | Lấy trang đăng nhập công khai để kiểm chứng bước scrub trên response thật |
| `/WebGoat/attack` | GET, POST | Điểm vào bài học WebGoat, chỉ nhận probe lành tính đã duyệt |

Giới hạn cho cả ba: response tối đa 65.536 byte; header được phép chỉ gồm
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
make dast                 # ZAP baseline qua gateway-dast; không active scan
make scan-all             # quét + chuẩn hoá + hợp nhất SAST/DAST
make target-up            # bật WebGoat + Gateway
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9080/WebGoat/actuator/health   # 401, đúng như mong đợi
make target-down
```

Raw report nằm ở `artifacts/raw/zap.json`, finding chuẩn hoá ở
`artifacts/normalized/zap-findings.json`, và bằng chứng đường đi ở
`artifacts/dast/gateway-access.log`. File log phải có các request `GET`/`HEAD` do ZAP
gửi qua lane DAST và không được chứa khoá; thiếu bằng chứng này thì
`scripts/scan-zap.sh` trả lỗi thay vì tạo một kết quả quét tưởng như hợp lệ.
