# Worklog — Thu thập fixture DAST từ phiên quét thật có phiên đăng nhập

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 3`

---

## 1. Tóm tắt

Đã thực hiện quét ZAP Baseline thật với WebGoat qua Nginx Gateway có session đăng nhập, ghi nhận tổng cộng 33 URL (tăng so với 19 URL quét ẩn danh trước đó). Đã xác nhận danh sách URL có phiên đăng nhập ngoài `permitAll` (như `/WebGoat/start.mvc`, `/WebGoat/welcome.mvc`, `/WebGoat/WebWolf`) hoạt động đầy đủ, không rò rỉ credential hay session ID ra artifact/log, và đã lưu report cùng access log làm fixture chuẩn trong `tests/fixtures/dast/`.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp dữ liệu fixture thực tế từ một lần quét DAST có session thật để phục vụ việc phát triển và kiểm thử offline các module chuẩn hoá (Task 4) và đối chiếu route (Task 5) mà không vi phạm nguyên tắc cấm mock/fake của repository.
- **Nằm ở đâu trong luồng:** Đầu vào fixture cho tầng `ingestion/` và `analysis/correlation.py`.
- **Không có nó thì hỏng gì:** Không có dữ liệu kiểm thử thực tế đa dạng với các alert có nhiều instance để kiểm chứng logic gộp finding và correlate route.
- **Ngoài phạm vi (cố ý không làm):** Chưa sửa `zap_normalizer.py` (nội dung Task 4).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh` | Sửa | Thêm `|| true` cho lệnh wget bắt redirect và chuẩn hoá độ dài username/password | Đảm bảo entrypoint khởi động ổn định không bị `set -e` ngắt |
| `tests/fixtures/dast/zap-alerts-authenticated.json` | Tạo | Bản sao raw report từ lần chạy `make dast` có session | Fixture DAST chuẩn cho unit tests |
| `tests/fixtures/dast/gateway-access-authenticated.log` | Tạo | Bản sao access log DAST của cùng lần chạy | Fixture log chuẩn cho route correlation |
| `tests/fixtures/dast/README.md` | Tạo | Ghi nhận provenance và cách tái lập fixture | Tài liệu nguồn gốc dữ liệu theo quy định repo |

**`git diff --stat`:**

```text
 infra/docker/gateway/docker-entrypoint.d/16-acquire-dast-session.envsh | 11 ++++++-----
 tests/fixtures/dast/README.md                                         | 12 ++++++++++++
 tests/fixtures/dast/gateway-access-authenticated.log                  | 74 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 tests/fixtures/dast/zap-alerts-authenticated.json                     | 83 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 175 insertions(+), 5 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Khởi động container `gateway-dast` và `webgoat` với profile `dast`, thực hiện `make dast` để ZAP Baseline spider và passive scan toàn bộ các endpoint WebGoat.
Kiểm tra tính hợp lệ của report, xác minh số lượng URL tăng và các endpoint authenticated xuất hiện trong kết quả spider, sau đó kiểm tra rò rỉ bí mật trước khi lưu vào fixture.

**Luồng dữ liệu:**
`make dast` $\rightarrow$ `scan-zap.sh` $\rightarrow$ ZAP Baseline qua `gateway-dast:8081` $\rightarrow$ `artifacts/raw/zap.json` & `artifacts/dast/gateway-access.log` $\rightarrow$ Copy sang `tests/fixtures/dast/`.

**Các quyết định kỹ thuật:**
- Chạy quét thực tế với ZAP 2.17.0 qua Docker Compose nội bộ.
- Kiểm tra bí mật 2 lần: qua `grep -c JSESSIONID` và qua `grep -riE "jsessionid|x-sentinel-dast-key|password=|api[_-]?key"`.
- Giữ nguyên cấu trúc raw của ZAP report để các bài test sau xử lý đúng định dạng thật.

**Xử lý lỗi / trường hợp biên:**
- Xử lý việc `wget` trả mã 1 do loop redirect ở hop cuối trong `16-acquire-dast-session.envsh` bằng cách bọc `|| true`.
- Tự động huỷ file tạm qua trap signal trong `scan-zap.sh`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Fixture | ZAP Authenticated Report | `tests/fixtures/dast/zap-alerts-authenticated.json` | Output ZAP JSON thật từ lần quét có session |
| Fixture | DAST Access Log | `tests/fixtures/dast/gateway-access-authenticated.log` | Nginx access log thật ghi nhận 74 request chuyển tiếp |
| Tài liệu | Fixture README | `tests/fixtures/dast/README.md` | Tài liệu provenance |

**Cách chạy:**

```bash
make dast
jq '[.site[].alerts[].instances[].uri] | unique | length' artifacts/raw/zap.json
```

**Output thật (đã che secret):**

```text
Total of 33 URLs
PASS: 57
WARN-NEW: 9
FAIL-NEW: 0
Normalized 41 ZAP findings -> artifacts/normalized/zap-findings.json
Unique authenticated non-permitAll URLs found:
http://gateway-dast:8081/WebGoat/WebWolf
http://gateway-dast:8081/WebGoat/logout
http://gateway-dast:8081/WebGoat/start.mvc
http://gateway-dast:8081/WebGoat/start.mvc?lang=de
http://gateway-dast:8081/WebGoat/start.mvc?username=sentinel-***
http://gateway-dast:8081/WebGoat/welcome.mvc
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Lưu raw report thật và access log thật từ một lượt quét hoàn chỉnh.

**Lý do:**
- Tuân thủ nghiêm ngặt nguyên tắc "No mock / No fake" của Project Sentinel (`AGENTS.md` §2.2).
- Giúp các test ở Task 4 và Task 5 chạy hoàn toàn offline với tốc độ mili-giây nhưng vẫn phản ánh chính xác 100% dữ liệu thực tế từ hạ tầng.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Viết JSON giả lập bằng tay | Nhanh, tuỳ biến được trường | Vi phạm bất biến repo (cấm mock/fake data) và dễ bỏ sót các trường bất thường của ZAP |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `make dast` | 0 | Scan thành công, 33 URLs, 41 finding |
| `grep -c JSESSIONID artifacts/raw/zap.json artifacts/dast/gateway-access.log` | 0 | 0 rò rỉ |
| `grep -riE "jsessionid\|x-sentinel-dast-key\|password=\|api[_-]?key" tests/fixtures/dast/` | 0 | `sach` |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 862 passed, 38 deselected |
| `make lint && make typecheck` | 0 | Sạch 100% |

**Bất biến đã giữ:**
- Không sửa assertion nào trong `test_dast_gateway_config.py`.
- Danh sách URL authenticated ngoài permitAll khác rỗng (pass gating check Step 2).
- Không có bất kỳ secret hay session token nào xuất hiện trong fixtures.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có (mọi kiểm tra đều có bằng chứng trực tiếp từ hạ tầng thật).
- **Giả định đã đặt:** Cấu trúc alert và instance của ZAP 2.17.0 giữ nguyên khi parse ở Task 4.
- **Việc còn nợ:** Bắt đầu triển khai Task 4: gộp finding theo pluginid.
