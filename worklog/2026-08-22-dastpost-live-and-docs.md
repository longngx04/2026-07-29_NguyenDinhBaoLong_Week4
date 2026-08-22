# Worklog — Test live cho POST, đo phân bố reachability thực tế, và đồng bộ tài liệu

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-post-reachability.md`](../docs/superpowers/plans/2026-08-22-dast-post-reachability.md) · **Task ID:** `Task 6`

---

## 1. Tóm tắt

Task 6 đã hoàn thành việc tích hợp và kiểm chứng live cho toàn bộ cơ chế DAST POST reachability, chạy kiểm thử tích hợp thực tế với Gateway và ZAP, đo đạc phân bố strength trên run pipeline thật với OpenRouter LLM, và đồng bộ tài liệu hệ thống. Kết quả chạy pipeline thật trên 23 SAST finding của WebGoat ghi nhận 17 finding đạt `reachable` (tăng từ 0 lên 17), 4 finding `no_route`, và 2 finding `route_known_not_reached`. Toàn bộ bộ test suite gồm 945 test unit/offline, 7 test live DAST, 23 test live gateway, cùng các test honesty và completeness tài liệu đều đạt 100% PASS.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Kiểm chứng tính toàn vẹn của luồng DAST POST thông qua test live thật, xác minh bất biến canary của caller không bao giờ lọt tới ứng dụng đích WebGoat, đo đạc thực tế tỷ lệ reachability trên toàn bộ pipeline SAST + DAST + LLM, và cập nhật tài liệu kiến trúc cùng giới hạn đã biết.
- **Nằm ở đâu trong luồng:** Bước nghiệm thu cuối cùng sau khi hoàn thiện Gateway allowlist (Task 2-3), ZAP Automation Framework requestor (Task 4), và bộ lọc status correlation (Task 5).
- **Không có nó thì hỏng gì:** Không có kiểm chứng live, không thể khẳng định body canary có bị forward hay không, không có số liệu đo đạc thực tế của pipeline để cập nhật tài liệu trung thực, và test suite live của DAST sẽ bị gãy do giả định cũ về GET/HEAD-only.
- **Ngoài phạm vi (cố ý không làm):** Không sinh payload khai thác hay active scan; không mở thêm endpoint ngoài danh sách đã review; không tự động push code lên remote.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/integration/test_zap_gateway_live.py` | Sửa | Cập nhật `test_gateway_log_proves_zap_requests_crossed_the_boundary` chấp nhận POST trả về 200, 204, 405; thêm 3 test live `test_zap_cannot_influence_the_body_webgoat_receives` (canary test), `test_post_to_an_unlisted_path_is_refused_at_the_gateway`, `test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path`. | Yêu cầu Step 1 & 2 của Task 6 để khoá bất biến canary và kiểm chứng live POST. |
| `configs/gateway/dast-allowlist.json` | Sửa | Bổ sung đầy đủ tham số `@RequestParam` trong `canonical_body` cho 3 endpoint `assignment5a` (`account=&operator=&injection=`), `attack8` (`name=&auth_tan=`), `attack9` (`name=&auth_tan=`). | WebGoat Spring MVC yêu cầu đủ required `@RequestParam`, nếu thiếu tham số sẽ trả HTTP 400 thay vì 200. |
| `infra/docker/gateway/templates/default.conf.template` | Sửa | Đồng bộ map `` với allowlist cho 3 endpoint `assignment5a`, `attack8`, `attack9`. | Đảm bảo Nginx dựng đúng canonical body tương ứng với allowlist. |
| `infra/docker/zap/requestor-plan.yaml` | Sửa | Đồng bộ trường `data` trong requestor plan với canonical body của 3 endpoint. | Giữ tính nhất quán và tự mô tả của plan Automation Framework. |
| `docs/limitations.md` | Sửa | Cập nhật số liệu phân bố strength thực tế `{'no_route': 4, 'reachable': 17, 'route_known_not_reached': 2}` và thêm 3 lưu ý về cơ chế allowlist POST DAST, sự phụ thuộc phiên bản WebGoat, và ý nghĩa của `reachable`. | Yêu cầu Step 5 của Task 6. |
| `docs/architecture.md` | Sửa | Cập nhật sơ đồ luồng DAST (bao gồm AF requestor job và POST qua gateway-dast:8081) cùng phát biểu bất biến: nội dung WebGoat nhận do lane quyết định hoàn toàn, ZAP không ảnh hưởng được method, path, header hay body. | Yêu cầu Step 6 của Task 6. |

**`git diff --stat`:**

```text
 configs/gateway/dast-allowlist.json                | 12 +++---
 docs/architecture.md                               | 13 +++---
 docs/limitations.md                                | 23 ++++++++---
 infra/docker/gateway/templates/default.conf.template |  6 +--
 infra/docker/zap/requestor-plan.yaml               |  6 +--
 tests/integration/test_zap_gateway_live.py         | 46 ++++++++++++++++++++--
 6 files changed, 81 insertions(+), 25 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. Cập nhật `tests/integration/test_zap_gateway_live.py` để phản ánh chính sách POST mới của lane DAST và thêm 3 test live quan trọng: gửi canary body từ ZAP và kiểm tra phản hồi từ WebGoat để chứng minh caller không thể can thiệp body; kiểm tra POST tới unlisted path bị 405; và kiểm tra report/log không lộ canary.
2. Qua kiểm tra live thực tế, phát hiện Spring MVC trong WebGoat đòi hỏi đầy đủ các `@RequestParam` có trong chữ ký method (nếu thiếu, Spring trả 400 Bad Request thay vì 200). Đã cập nhật `canonical_body` cho `assignment5a` (`account=&operator=&injection=`), `attack8` (`name=&auth_tan=`), và `attack9` (`name=&auth_tan=`) trên cả allowlist JSON, template Nginx và requestor plan YAML.
3. Chạy `make dast-test` qua Gateway thật để chứng minh toàn bộ 7 test live tích hợp đều PASS.
4. Chạy toàn bộ pipeline Sentinel (`python -m project_sentinel.cli run --yes`) với real external OpenRouter LLM và Gateway, đo đạc phân bố `strength` của 23 SAST finding: 17 đạt `reachable` (vượt qua cổng dừng `reachable > 0`).
5. Cập nhật tài liệu `docs/limitations.md` và `docs/architecture.md` với các số liệu thật và phân tích rủi ro/giới hạn trung thực.
6. Chạy toàn bộ suite nghiệm thu gồm unit tests, static checks, live tests và doc tests.

**Luồng dữ liệu:**
`ZAP baseline (spider + AF requestor)` $ightarrow$ `POST + canary body` $ightarrow$ `Gateway DAST (8081)` $ightarrow$ `Strip header & body caller, thế bằng canonical body` $ightarrow$ `WebGoat (8080)` $ightarrow$ `HTTP 200 OK` $ightarrow$ `Gateway Access Log (path, status 200)` $ightarrow$ `correlation.py` $ightarrow$ `finding.runtime_evidence.strength = 'reachable'`.

**Các quyết định kỹ thuật:**
- Điền đầy đủ các tham số `@RequestParam` rỗng vào `canonical_body` (ví dụ `account=&operator=&injection=`) thay vì chỉ 1 tham số đầu tiên, giúp Spring MVC thoả mãn điều kiện parameter mapping và trả về HTTP 200 an toàn mà không chạy SQL query độc hại nào.
- Giữ nguyên test canary để đảm bảo `proxy_pass_request_body off` và `proxy_set_body ` hoạt động chuẩn xác ở tầng Nginx.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Test | `test_zap_cannot_influence_the_body_webgoat_receives` | `tests/integration/test_zap_gateway_live.py` | Kiểm chứng body canary gửi từ ZAP bị Nginx thay thế hoàn toàn bằng canonical body |
| Test | `test_post_to_an_unlisted_path_is_refused_at_the_gateway` | `tests/integration/test_zap_gateway_live.py` | Kiểm chứng POST tới path chưa allowlist bị 405 |
| Test | `test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path` | `tests/integration/test_zap_gateway_live.py` | Kiểm chứng log/artifact không chứa canary |
| Doc | `docs/limitations.md` | `docs/limitations.md` | Ghi nhận số liệu phân bố strength mới và các phân tích hạn chế |
| Doc | `docs/architecture.md` | `docs/architecture.md` | Ghi nhận luồng DAST POST và bất biến ranh giới |

**Cách chạy:**

```bash
make dast-test
KEY=e33b4a8c128317f0f096833cb4e429b6f7c18bf8481714d1   SENTINEL_GATEWAY_API_KEY="$KEY"   .venv/bin/python -m project_sentinel.cli run --yes
```

**Output thật (đã che secret):**

*Output `make dast-test`:*
```text
ZAP Baseline report: /home/longngx04/VinSOC/project_sentinel_main/artifacts/raw/zap.json
DAST Gateway evidence: /home/longngx04/VinSOC/project_sentinel_main/artifacts/dast/gateway-access.log
Normalized 14 ZAP findings -> artifacts/normalized/zap-findings.json
============================= test session starts ==============================
collected 7 items

tests/integration/test_zap_gateway_live.py::test_zap_report_came_from_the_gateway_target PASSED [ 14%]
tests/integration/test_zap_gateway_live.py::test_gateway_log_proves_zap_requests_crossed_the_boundary PASSED [ 28%]
tests/integration/test_zap_gateway_live.py::test_dast_artifacts_do_not_contain_a_key_header_or_value PASSED [ 42%]
tests/integration/test_zap_gateway_live.py::test_dast_gateway_rejects_a_request_without_its_key PASSED [ 57%]
tests/integration/test_zap_gateway_live.py::test_zap_cannot_influence_the_body_webgoat_receives PASSED [ 71%]
tests/integration/test_zap_gateway_live.py::test_post_to_an_unlisted_path_is_refused_at_the_gateway PASSED [ 85%]
tests/integration/test_zap_gateway_live.py::test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path PASSED [100%]

============================== 7 passed in 0.48s ===============================
```

*Output đo phân bố strength của run mới:*
```text
phan bo strength: {'no_route': 4, 'reachable': 17, 'route_known_not_reached': 2}
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Dùng Automation Framework `requestor` job kết hợp Nginx `proxy_set_body` với canonical body chứa đầy đủ tham số `@RequestParam` rỗng.
**Lý do:** Kế hoạch yêu cầu rõ: *"Nội dung WebGoat nhận được từ lane DAST do lane quyết định hoàn toàn; ZAP không ảnh hưởng được method, path, header hay body."* Việc khai báo đủ tham số giúp Spring MVC xử lý request trơn tru trả về HTTP 200, trong khi các giá trị rỗng đảm bảo không có câu lệnh SQL nào được thực thi hay gây side-effect nguy hại.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Chỉ truyền 1 tham số đầu tiên trong canonical body | Ngắn gọn hơn trong config | Bị Spring MVC từ chối với HTTP 400 (MissingServletRequestParameterException), khiến endpoint không thể trả về 2xx và không được tính là `reachable`. |
| Nới lỏng điều kiện correlation trong `correlation.py` để chấp nhận cả HTTP 400 | Không cần sửa canonical body | Vi phạm nguyên tắc bảo mật và tính trung thực: 400 có thể là do gateway hoặc router từ chối, chỉ 2xx mới chứng minh endpoint thực sự nhận diện và xử lý request thành công. |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 945 passed, 40 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 78 source files OK |
| `make dast-test` | 0 | 7 passed (live DAST + Gateway) |
| `make gateway-live-test` | 0 | 23 passed (live Gateway + WebGoat) |
| `.venv/bin/python -m pytest tests/unit/infra/test_docs_complete.py tests/test_docs_are_honest.py -q` | 0 | 35 passed |

**Test mới thêm / cập nhật:**
- `tests/integration/test_zap_gateway_live.py::test_zap_cannot_influence_the_body_webgoat_receives` — khẳng định caller không thể truyền canary body tới WebGoat.
- `tests/integration/test_zap_gateway_live.py::test_post_to_an_unlisted_path_is_refused_at_the_gateway` — khẳng định POST ngoài allowlist bị 405.
- `tests/integration/test_zap_gateway_live.py::test_no_dast_artifact_contains_the_canonical_body_of_an_unlisted_path` — khẳng định không rò rỉ canary trong artifact.

**Bất biến đã giữ:**
- Bốn lớp bảo vệ DAST giữ nguyên: credential riêng, xoá header caller, xoá body caller, không bind cổng host.
- Không có mock/stub/test double nào.
- Test không skip khi thiếu phụ thuộc.
- Không in secret / API key ra log hay console.
- Cổng dừng `reachable > 0` đạt 17 findings.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `tests/integration/test_zap_gateway_live.py` tương tác với container `gateway-dast` qua lệnh docker compose exec -T.
- **Giả định đã đặt:** Giả định WebGoat container v2025.3 giữ nguyên định nghĩa các tham số `@RequestParam`.
- **Việc còn nợ:** Không có.
- **Câu hỏi cho người dùng:** Không có.
