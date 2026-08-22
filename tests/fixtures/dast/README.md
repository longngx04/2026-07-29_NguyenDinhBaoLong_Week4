# Fixture DAST

Mọi file ở đây là **output thật đã ghi lại**, không phải JSON viết tay. Repo cấm
mock (`AGENTS.md` §2.2), nên test đọc lại chính output thật này.

| File | Sinh ra bằng | Ngày |
| :--- | :--- | :--- |
| `zap-alerts-authenticated.json` | `make dast` với Gateway giữ phiên WebGoat | 2026-08-22 |
| `gateway-access-authenticated.log` | Access log `gateway-dast` của cùng lần chạy | 2026-08-22 |

Chép lại: xem `docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md` Task 3.
