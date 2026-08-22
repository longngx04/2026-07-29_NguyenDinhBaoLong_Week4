# Worklog — ZAP DAST qua Gateway nội bộ

**Ngày:** 2026-08-22 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/zap-dast` · **Plan:** Không có · **Task ID:** DAST Gateway

---

## 1. Tóm tắt

Đã thêm OWASP ZAP Baseline để spider và passive scan WebGoat qua một lane Gateway
nội bộ riêng, không cho ZAP biết địa chỉ trực tiếp của WebGoat. Finding ZAP được lọc
các response do Gateway chặn, chuẩn hoá và có thể hợp nhất với OpenGrep. Lượt chạy thật
cuối cùng quét 19 URL, chuẩn hoá 25 finding và toàn bộ 5 test bằng chứng live đều pass.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Bổ sung nguồn finding DAST thật bằng ZAP, kèm bằng chứng
  mọi traffic đi qua Gateway và lớp chuẩn hoá chung với SAST.
- **Nằm ở đâu trong luồng:** Là lane quét tùy chọn trước bước phân tích; `make scan-all`
  tạo OpenGrep + ZAP rồi hợp nhất thành `artifacts/normalized/all-findings.json`.
- **Không có nó thì hỏng gì:** Gateway chỉ được dùng cho một probe cuối luồng; hệ thống
  không có quan sát động rộng hơn trên bề mặt HTTP và không thể kết hợp SAST/DAST.
- **Ngoài phạm vi (cố ý không làm):** Không active scan, không đăng nhập WebGoat, không
  tự động chạy DAST trong CLI chín bước, không ánh xạ một alert DAST vào một finding SAST.
  Các phần này cần threat model và hợp đồng sản phẩm riêng để tránh gửi payload phá hoại.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `docker-compose.yml` | Sửa | Thêm profile `dast`, `gateway-dast`, ZAP 2.17.0 pin digest | Cô lập scanner và không publish WebGoat/DAST ra host |
| `infra/docker/gateway/*` | Sửa | Thêm mode/key/listener DAST, GET/HEAD-only, rate/timeout/header/body policy | Tạo ranh giới độc lập, deny-by-default cho ZAP |
| `scripts/scan-zap.sh` | Tạo | Khoá tạm, baseline scan, validate report, kiểm chứng log và chống leak | Một entry point chạy thật, fail loud khi thiếu bằng chứng |
| `src/project_sentinel/ingestion/zap_normalizer.py` | Tạo | Chuyển ZAP JSON thành finding chung, lọc request không được forward | Không biến 403/405 của Gateway thành finding WebGoat |
| `src/project_sentinel/ingestion/merge_findings.py` | Tạo | Hợp nhất nhiều artifact, giữ provenance và chặn ID trùng | Cho SAST/DAST cùng đi vào pipeline phân tích |
| `Makefile` | Sửa | Thêm `dast`, `scan-zap`, `normalize-zap`, `scan-all`, `analyze-dast`, `dast-test` | Cung cấp lệnh vận hành và kiểm chứng nhất quán |
| `tests/unit/**`, `tests/integration/test_zap_gateway_live.py` | Tạo/Sửa | Khoá topology, policy, script, normalizer, merge và bằng chứng Docker thật | Chứng minh cả cấu hình tĩnh và hành vi tại boundary |
| `README.md`, `docs/*.md`, `.gitignore` | Sửa | Mô tả hai lane, artifact, giới hạn passive/unauthenticated; ignore runtime | Tránh overclaim và không đưa output quét vào Git |

**`git diff --stat` (không tính chính worklog này):**

```text
 .gitignore                                         |   2 +
 Makefile                                           |  29 +++-
 README.md                                          |  19 ++-
 docker-compose.yml                                 |  46 +++++-
 docs/architecture.md                               |  34 +++-
 docs/limitations.md                                |  11 +-
 docs/target-webgoat.md                             |  28 +++-
 infra/docker/gateway/Dockerfile                    |   2 +-
 .../gateway/docker-entrypoint.d/00-require-key.sh  |  24 ++-
 infra/docker/gateway/nginx.conf                    |   5 +
 .../docker/gateway/templates/default.conf.template |  55 ++++++-
 scripts/scan-zap.sh                                |  96 +++++++++++
 src/project_sentinel/ingestion/merge_findings.py   |  65 ++++++++
 src/project_sentinel/ingestion/zap_normalizer.py   | 176 +++++++++++++++++++++
 tests/integration/test_zap_gateway_live.py         |  99 ++++++++++++
 tests/unit/gateway/test_dast_gateway_config.py     |  60 +++++++
 .../test_gateway_config_matches_registry.py        |   5 +-
 tests/unit/infra/test_compose_invariants.py        |  42 ++++-
 tests/unit/infra/test_zap_scan_script.py           |  35 ++++
 tests/unit/ingestion/test_merge_findings.py        |  40 +++++
 tests/unit/ingestion/test_zap_normalizer.py        |  98 ++++++++++++
 21 files changed, 946 insertions(+), 25 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Giữ nguyên lane Agent probe với approval và exact-template allowlist.
ZAP chạy trong Docker network qua listener `gateway-dast:8081`, dùng credential ngẫu
nhiên riêng cho từng lệnh. Gateway chỉ proxy `GET/HEAD` dưới `/WebGoat/`, bỏ body và
header do caller kiểm soát; trang `/` chỉ là bootstrap tĩnh để spider tìm target. Raw
report được giữ nguyên, nhưng normalizer chỉ nhận instance thực sự nằm trong boundary.

**Luồng dữ liệu:** `ZAP 2.17.0` → `gateway-dast` → `WebGoat internal-only` →
`artifacts/raw/zap.json` → `zap_normalizer` → `zap-findings.json` →
`merge_findings` → `all-findings.json`

**Các quyết định kỹ thuật:**

- Pin image bằng digest đã xác minh chạy ZAP 2.17.0; digest bất biến chặt hơn tag.
- Dùng `zap-baseline.py --autooff -I`: vẫn là spider + passive scan, nhưng tránh lỗi
  ZAP 2.17 Automation Framework trả mã 4 ngoài contract dù chỉ có WARN.
- Bằng chứng Gateway chỉ được lấy từ `--since` thời điểm scan và phải có request target
  `/WebGoat/login`; healthcheck cũ không thể làm scan giả thành công.
- Normalizer chỉ giữ `GET/HEAD`, origin `gateway-dast:8081`, path `/WebGoat/…`; raw
  report vẫn giữ request POST/ngoài scope bị chặn để audit.

**Xử lý lỗi / trường hợp biên:** Script từ chối report ngoài `artifacts/`, key rỗng,
thời lượng sai, JSON sai, thiếu target evidence hoặc key xuất hiện trong artifact. Gateway
không key trả 401, method ghi dữ liệu trả 405, ngoài scope trả 403, và WebGoat không có
host port. Normalizer fail loud nếu thiếu cấu trúc `site/alerts`; merge fail nếu ID trùng.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Script | ZAP wrapper | `scripts/scan-zap.sh [report_path]` | Chạy baseline thật và tạo evidence |
| Hàm | Normalizer | `normalize_zap_report(raw)` | Chuẩn hoá + lọc instance không được forward |
| Hàm | Merger | `merge_files(inputs, output)` | Hợp nhất finding, giữ source và chặn trùng ID |
| Config | DAST Gateway | `gateway-dast:8081` | Listener nội bộ, credential riêng, read-only |
| Test | Live evidence | `tests/integration/test_zap_gateway_live.py` | Kiểm report, access log, 401, 405 và secret |

**Cách chạy:**

```bash
make dast       # ZAP baseline + normalize
make scan-all   # OpenGrep + ZAP + merge
make dast-test  # quét thật rồi chạy test boundary
```

**Output thật (đã che secret):**

```text
Total of 19 URLs
FAIL-NEW: 0  WARN-NEW: 9  INFO: 0  PASS: 57
ZAP Baseline report: .../artifacts/raw/zap.json
DAST Gateway evidence: .../artifacts/dast/gateway-access.log
Normalized 25 ZAP findings -> artifacts/normalized/zap-findings.json
============================== 5 passed in 0.27s ===============================

Merged 48 findings -> artifacts/normalized/all-findings.json
{"source":"opengrep+zap","count":48,"tools":{"opengrep":23,"zap":25}}

Gateway evidence: 41 requests = 39 GET + 2 POST;
2 POST đều status=405, 2 ngoài scope status=403, không có DAST key trong artifact.
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Hai Gateway lane tách biệt: Agent probe giữ policy chính xác hiện có;
DAST có listener/key/profile nội bộ riêng và chỉ cho spider/passive GET/HEAD.

**Lý do:** `.agents/security.md` yêu cầu WebGoat internal-only, deny-by-default, giới hạn
rate/timeout và không log secret. Dùng trực tiếp `http://webgoat:8080` sẽ bỏ qua boundary;
nới listener Agent sẽ làm yếu hợp đồng approval/exact template. Lane riêng giữ hai threat
model độc lập và để log Nginx chứng minh đường đi thật.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| ZAP gọi thẳng WebGoat | Cấu hình đơn giản | Không dùng Gateway, không có policy/evidence boundary |
| Nới listener Agent cho spider | Ít container hơn | Làm yếu allowlist và trộn credential/policy với probe đã duyệt |
| ZAP active scan | Độ phủ lớn hơn | Gửi payload có thể thay đổi/phá target; chưa có approval contract |
| Chấp nhận mọi mã thoát khi có JSON | Dễ làm lệnh xanh | Có thể nuốt lỗi ZAP thật; thay bằng chế độ baseline trả đúng contract |

**Đánh đổi đã chấp nhận:** Quét không đăng nhập nên độ phủ thấp và số alert có dao động;
đổi lại traffic read-only, hữu hạn và kiểm chứng được. Header alert phản ánh response đi
qua cả Nginx lẫn WebGoat, nên báo cáo không quy chúng tuyệt đối cho riêng ứng dụng.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `make dast-test` | 0 | ZAP thật: 19 URL, 9 WARN; 25 finding; 5 live test passed |
| `pytest -m "not llm and not live_gateway" -q` | 0 | 850 passed, 2 skipped có sẵn, 38 deselected |
| `make gateway-live-test` | 0 | 23 passed; lane Agent cũ không hồi quy |
| `python -m ruff check .` | 0 | All checks passed |
| `python -m mypy` | 0 | Success: no issues found in 77 source files |
| `docker compose --profile dast config --quiet` | 0 | Compose hợp lệ, không warning key |
| `bash -n scripts/scan-zap.sh && git diff --check` | 0 | Không lỗi cú pháp/whitespace |

**Test mới thêm:**

- `test_zap_gateway_live.py` — report có origin Gateway, target request có evidence,
  artifact không lộ key, không key bị 401 và POST có key vẫn bị 405.
- `test_dast_gateway_config.py` — listener/key/method/path/body/header/rate policy tĩnh.
- `test_zap_scan_script.py` — target không phải WebGoat trực tiếp, report path đúng,
  evidence thuộc current scan và không dùng active scan.
- `test_zap_normalizer.py` — mapping, dedupe, fail-closed và lọc response Gateway.
- `test_merge_findings.py` — merge provenance đúng và ID trùng bị chặn.

**Bất biến đã giữ:** Không mock/stub ZAP · test DAST không skip · WebGoat không có host
port · chỉ lane Agent bind loopback · DAST key tách riêng và không vào log/report · lane
Agent vẫn pass 23 live test · không sửa báo cáo lịch sử.

**Còn fail / chưa chạy được:** Không có. Hai skip trong suite offline là test có sẵn,
không thuộc task này.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `infra/docker/gateway/templates/default.conf.template` —
  prefix `/WebGoat/` rộng hơn exact allowlist của Agent vì spider cần khám phá URL động;
  hiện được bù bằng internal-only, key riêng, GET/HEAD-only, body/header stripping và rate.
- **Giả định đã đặt:** GET/HEAD baseline không gây thay đổi có hại cho WebGoat. Nếu target
  dùng GET để mutate state, cần context path allowlist hẹp hơn hoặc snapshot/reset target.
- **Việc còn nợ:** Authenticated DAST, active scan có approval, correlation SAST↔DAST và
  tích hợp DAST trực tiếp vào orchestrator/UI được cố ý hoãn.
- **Câu hỏi cho người dùng:** Không có.
