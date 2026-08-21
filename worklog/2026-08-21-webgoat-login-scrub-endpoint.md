# Worklog — Mở allowlist cho trang đăng nhập WebGoat để kiểm chứng scrub

**Ngày:** 2026-08-21 · **Agent/Model:** Codex · GPT-5 ·
**Branch:** `feat/webgoat-scrub-endpoint` · **Plan:** [`.agents/implementation_plan.md`](../.agents/implementation_plan.md) · **Task ID:** D4 allowlist extension

---

## 1. Tóm tắt

Đã thêm endpoint chính xác `GET /WebGoat/login` vào cả Python allowlist và Nginx Gateway sau khi người vận hành duyệt nguồn WebGoat. Test tích hợp dùng Gateway và WebGoat thật, lấy response 200 rồi đưa chính response đó qua `step_scrub`. Kết quả cuối là 8 test live Gateway và 414 test không tốn token đều xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cho phép một probe GET không payload tới trang đăng nhập công khai của WebGoat, tạo response body thật để pipeline thực thi bước scrub.
- **Nằm ở đâu trong luồng:** `SafeProbe` → Python allowlist → Gateway loopback → WebGoat `/login` → `probe-result.json` → `step_scrub` → `scrubbed.json`.
- **Không có nó thì hỏng gì:** Hai lớp allowlist cùng từ chối `/WebGoat/login`, nên luồng thật không có response body ổn định để kích hoạt scrub.
- **Ngoài phạm vi (cố ý không làm):** Không đổi logic để LLM ưu tiên hay bắt buộc chọn endpoint này; không thêm payload, method khác, wildcard hoặc subpath; không gọi WebGoat trực tiếp ngoài Gateway.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `configs/gateway/endpoint-allowlist.json` | Sửa | Thêm `ep_login`, GET-only, template cố định, header hữu hạn và nguồn Java chính xác | Python Tool phải deny-by-default trước khi mở kết nối |
| `infra/docker/gateway/templates/default.conf.template` | Sửa | Thêm exact location `/WebGoat/login`, bắt API key, GET-only, rate limit và timeout | Gateway là lớp allowlist độc lập thứ hai |
| `tests/integration/test_gateway_live.py` | Sửa | Thêm test live cho 200 + scrub, exact path/method và API key | Chứng minh cả đường tốt lẫn đường xấu trên dịch vụ thật |
| `docs/target-webgoat.md` | Sửa | Đồng bộ danh sách ba endpoint và mục đích của `/login` | Test tài liệu yêu cầu mọi endpoint allowlist đều được công khai cho reviewer |
| `.agents/implementation_plan.md` | Sửa | Ghi quyết định D4 mới và nguồn đã được người vận hành duyệt | D4 cấm thêm route đoán và yêu cầu human review |
| `worklog/2026-08-21-webgoat-login-scrub-endpoint.md` | Tạo | Ghi phạm vi, quyết định và bằng chứng thật | Worklog là deliverable bắt buộc |

**`git diff --stat`:**

```text
 .agents/implementation_plan.md                     |  2 +-
 configs/gateway/endpoint-allowlist.json            | 13 ++++
 docs/target-webgoat.md                             |  7 +-
 .../docker/gateway/templates/default.conf.template |  9 +++
 tests/integration/test_gateway_live.py             | 86 +++++++++++++++++++++-
 5 files changed, 112 insertions(+), 5 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Xác minh route từ source WebGoat trước khi sửa cấu hình. Thêm cùng một exact path ở cả Python Tool và Nginx Gateway, không dùng prefix hay regex. Viết test trước và chạy với cấu hình cũ để chứng minh ba lớp kiểm soát đều từ chối, sau đó rebuild Gateway và chạy lại trên WebGoat thật. Response thật được ghi theo cấu trúc `probe-result.json` rồi đi qua implementation `step_scrub` hiện có.

**Luồng dữ liệu:** `SafeProbe(GET /WebGoat/login)` → `Allowlist.is_allowed` → `send_probe` → `127.0.0.1:9080` → WebGoat nội bộ → preview tối đa 512 byte → `step_scrub` → `scrubbed.json`

**Các quyết định kỹ thuật:**

- Chỉ cho phép exact path `/WebGoat/login`, method GET và không có payload.
- Nguồn route là `MvcConfiguration.java:53`; trạng thái không cần đăng nhập là `WebSecurityConfig.java:48-54`.
- Test đường xấu tại cả hai lớp: Python từ chối POST/subpath; Gateway trả 405 cho POST, 403 cho subpath và 401 khi thiếu key.
- Giữ giới hạn response 65.536 byte ở catalog, trong khi audit/pipeline chỉ giữ preview tối đa 512 byte.

**Xử lý lỗi / trường hợp biên:** Route con không khớp exact location; method sai dừng ở Gateway; thiếu key dừng trước proxy; dependency live không sẵn sàng làm test fail, không skip.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Config | `ep_login` | `configs/gateway/endpoint-allowlist.json` | Catalog GET-only được Python Tool dùng |
| Config | exact Nginx location | `/WebGoat/login` | Lớp Gateway yêu cầu key và GET |
| Test live | `test_login_get_reaches_webgoat_and_activates_scrub` | `tests/integration/test_gateway_live.py` | Chứng minh 200 và scrub response thật |
| Test live | `test_login_policy_is_exact_and_get_only` | `tests/integration/test_gateway_live.py` | Chứng minh POST/subpath bị chặn |
| Test live | `test_login_get_requires_the_gateway_key` | `tests/integration/test_gateway_live.py` | Chứng minh thiếu key bị 401 |

**Cách chạy:**

```bash
make gateway-live-test
```

**Output thật (đã che secret):**

```text
tests/integration/test_gateway_live.py::test_login_get_reaches_webgoat_and_activates_scrub PASSED
tests/integration/test_gateway_live.py::test_login_policy_is_exact_and_get_only PASSED
tests/integration/test_gateway_live.py::test_login_get_requires_the_gateway_key PASSED
============================== 8 passed in 0.75s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Mở một route đọc-only, exact-match ở cả hai lớp và chứng minh response của nó thực sự đi qua scrub.

**Lý do:** D4 yêu cầu endpoint phải có nguồn từ WebGoat và được người vận hành review. `GET /WebGoat/login` được khai báo trực tiếp trong `MvcConfiguration.java` và được `permitAll` trong `WebSecurityConfig.java`, nên phù hợp hơn route đoán hoặc route cần phiên đăng nhập. Hai lớp allowlist độc lập giữ nguyên nguyên tắc deny-by-default.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Cho phép prefix `/WebGoat/` | Dễ tìm route có body | Mở phạm vi quá rộng và vi phạm exact allowlist |
| Thêm POST hoặc payload cho `/login` | Có thêm biến thể probe | Không cần để lấy trang công khai và tăng rủi ro |
| Ép logic proposal chọn `/login` | Happy path dễ lặp lại | Người dùng duyệt phạm vi chỉ thêm endpoint, không đổi hành vi LLM |
| Gọi thẳng WebGoat trong test | Test ngắn hơn | Vi phạm bất biến Gateway-only |

**Đánh đổi đã chấp nhận:** Endpoint đã sẵn sàng cho pipeline nhưng LLM vẫn có quyền trả `NOT_APPLICABLE` hoặc chọn endpoint khác; task này không bảo đảm mọi lần chạy tự động đều dùng `/login`.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `SENTINEL_GATEWAY_API_KEY="***" python -m pytest tests/integration/test_gateway_live.py -k 'login_' -v` trước sửa | 1 | 3 failed, 5 deselected: Tool/catalog từ chối route; Gateway trả 403 thay vì 401 |
| `make gateway-live-test` | 0 | 8 passed in 0.75s |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q` trước đồng bộ tài liệu | 1 | 1 failed, 413 passed, 18 deselected; bắt thiếu `/WebGoat/login` trong tài liệu |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q` | 0 | 414 passed, 18 deselected in 3.19s |
| `python3 -m compileall -q src/project_sentinel` | 0 | Không có output |
| `git diff --check` | 0 | Không có output |

**Test mới thêm:**

- `test_login_get_reaches_webgoat_and_activates_scrub` — request qua Gateway nhận HTTP 200, body không rỗng, preview không quá 512 byte và tạo `scrubbed.json`.
- `test_login_policy_is_exact_and_get_only` — chỉ exact GET được cả catalog và Gateway chấp nhận.
- `test_login_get_requires_the_gateway_key` — request không key bị Gateway trả 401.

**Bất biến đã giữ:** Không mock/stub · test live không skip · không in secret · WebGoat không bind host · mọi request live qua Gateway loopback · exact method/path · không đụng báo cáo lịch sử.

**Còn fail / chưa chạy được:** Không có.

---

## 7b. Vì sao luồng tự động chưa kích hoạt được `scrub`, và cách giải quyết

### Triệu chứng

Sau khi thêm `GET /WebGoat/login` vào allowlist, ba lần chạy thật liên tiếp vẫn
kết thúc `DONE` mà `scrub` chạy trên chuỗi rỗng. Nguyên nhân **không** nằm ở
allowlist mà ở đề xuất của agent:

| Lần chạy | Tổng đề xuất | `GET` | Probe đi tới | Body |
|---|---:|---:|---|---:|
| `20260820T174049Z` (trước khi sửa prompt) | 17 | 0 | `POST /WebGoat/attack` | 0 |
| `20260821T015104Z` (sau khi sửa prompt) | 19 | 1 | `POST /WebGoat/attack` | 0 |
| `20260821T020353Z` (sau khi sửa luật chọn) | 18 | 0 | `POST /WebGoat/attack` | 0 |

`POST /WebGoat/attack` trả HTTP 302 (chuyển hướng đăng nhập) nên không có nội
dung để lọc.

### Hai bản sửa đã làm, và giới hạn của chúng

1. **`configs/prompts/security-analysis-system.md` — luật 4**: dạy agent chọn
   method theo việc cần quan sát, `GET` + `empty_value` khi muốn đọc nội dung.
   Kết quả: đề xuất `GET` đi từ 0 → 1 → 0. Có tác dụng nhưng **không tin cậy**,
   vì đầu ra LLM bất định.
2. **`step_propose` — `_choose_objective`**: trong số đề xuất được allowlist
   duyệt, ưu tiên `GET` vì nó không làm đổi trạng thái ứng dụng đích. Đúng về
   nguyên tắc an toàn, nhưng **không chọn được thứ không tồn tại** trong danh
   sách đề xuất.

Ép agent đề xuất một endpoint không liên quan tới finding chỉ để demo sẽ tạo ra
số liệu đẹp nhưng phản ánh sai hành vi thật, nên không làm.

### Bản sửa thật sự: người vận hành chỉ định bước kiểm chứng

Thêm `--probe-method` / `--probe-path` / `--probe-payload-kind` cho `cli run`.
Đây là tính năng đứng vững độc lập với demo — con người quyết định muốn kiểm
chứng cái gì — và **không nới lỏng lớp bảo vệ nào**: chỉ định vẫn đi qua
`validate_objective` rồi allowlist Gateway như mọi đề xuất khác.

### Bằng chứng luồng thật đầy đủ (`20260821T024650Z`)

```bash
SENTINEL_GATEWAY_API_KEY="$KEY" python -m project_sentinel.cli run --yes \
  --probe-method GET --probe-path /WebGoat/login
```

```text
Lần chạy 20260821T024650Z: AWAITING_APPROVAL
Kết thúc: DONE
exit=0
```

```
proposal.json : probe = GET /WebGoat/login [empty_value]
                operator_override = true, agent vẫn đề xuất 18 objective
gateway log   : {"method":"GET","path":"/WebGoat/login","payload_type":"empty_value",
                 "status":"SENT","status_code":200,"response_bytes_observed":1929,
                 "policy_decision":"ALLOWED"}
probe-result  : status=200, body_preview = 512 ký tự
scrubbed.json : original_bytes=512, injection verdict=clean, redactions=[]
                safe_text = "<untrusted_app_response>\n<!DOCTYPE html>..."
events.jsonl  : approval {approved:true, method:GET, path:/WebGoat/login}
metrics.json  : state=DONE, requests_total=1, requests_denied=0,
                findings_total=23, approvals={approved:1,rejected:0},
                errors={llm:0,app:0,other:0,total:0}
```

Đây là lần chạy đầu tiên bước `scrub` nhận được nội dung thật: 512 ký tự HTML
qua Gateway, được quét injection rồi bọc trong `<untrusted_app_response>`.

### Guardrail nào được dùng trong luồng thật

| Guardrail | Trạng thái |
|---|---|
| Cổng phê duyệt, ràng buộc `request_fingerprint` | ✅ có sự kiện, có `decision.json` |
| Che dữ liệu trước khi gửi LLM | ✅ chạy trên mọi packet |
| Che dữ liệu trước khi ghi log | ✅ chạy trên mọi dòng |
| Allowlist kiểm method + path | ✅ `policy_decision: ALLOWED` trong audit |
| Quét injection trên response | ✅ 512 byte thật, verdict `clean` |

Ca `verdict: suspicious` và ca `redactions` khác rỗng không xuất hiện vì trang
login WebGoat sạch — hai ca đó được phủ bởi `make guardrails-test` (118 test) và
`tests/fixtures/injection/`.

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `infra/docker/gateway/templates/default.conf.template` — reviewer nên xác nhận thứ tự auth → method → rate limit phù hợp chính sách Gateway.
- **Giả định đã đặt:** WebGoat image đang chạy tương ứng source submodule và tiếp tục giữ `/login` là trang công khai; test live sẽ phát hiện nếu giả định này thay đổi.
- **Việc còn nợ:** `.agents/context.md` còn mô tả hai endpoint nhưng phần này đã cũ cùng nhiều đường dẫn cấu hình không còn tồn tại; chưa sửa để tránh mở rộng task ngoài D4 và tài liệu target có test bảo vệ.
- **Câu hỏi cho người dùng:** Không có.
