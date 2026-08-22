# Thiết kế: mở rộng DAST bằng OWASP ZAP

**Ngày:** 2026-08-22 · **Trạng thái:** thiết kế đã duyệt, chưa implement
**Branch:** `feat/zap-dast`
**Xây trên:** commit `f6d174c` — "ZAP Baseline quét WebGoat qua lane Gateway nội bộ"
(Codex · GPT-5, worklog [`2026-08-22-zap-dast-through-gateway.md`](../../../worklog/2026-08-22-zap-dast-through-gateway.md))

> **Bản này thay thế hoàn toàn bản trước.** Bản trước được viết khi chưa biết `f6d174c`
> tồn tại; nó đề xuất cho ZAP nói chuyện thẳng với WebGoat và vì thế phải phát biểu lại
> ranh giới tin cậy. Kiến trúc trong `f6d174c` không cần điều đó và tốt hơn. Tài liệu này
> giữ nguyên kiến trúc ấy và chỉ mô tả phần còn thiếu.

---

## 1. Nền đã có

`f6d174c` đưa ZAP Baseline vào chạy thật qua một **lane Gateway thứ hai**:

```text
ZAP ──X-Sentinel-DAST-Key──► gateway-dast:8081 ──► webgoat:8080
       (ZAP_AUTH_HEADER)      GET/HEAD only
                              proxy_pass_request_headers off
                              proxy_pass_request_body off
```

Nhờ đó bất biến gốc **giữ nguyên nguyên văn**: mọi traffic tới WebGoat vẫn đi qua một
Gateway. Không phải viết lại phát biểu nào.

Những gì đã chạy được, có bằng chứng thật trong worklog §7: 19 URL, 25 finding chuẩn hoá,
`make dast-test` xanh, `make gateway-live-test` 23 passed không hồi quy, ruff/mypy sạch.
Bộ test offline hiện là **852 passed** khi chạy từ thư mục chính.

Ba điểm thiết kế của bản đó cần được giữ, không được làm hỏng khi mở rộng:

| Cơ chế | Ở đâu | Vì sao quan trọng |
| :--- | :--- | :--- |
| Bằng chứng lấy từ **Nginx access log**, không phải biến đếm Python | `scripts/scan-zap.sh` grep `channel=dast method=(GET\|HEAD) path=/WebGoat/login` | Bằng chứng ở tầng hạ tầng, đúng nguyên tắc [`architecture.md`](../../architecture.md) §3 |
| Kiểm rò credential | `scan-zap.sh` grep key trong cả report lẫn log | Key DAST sinh ngẫu nhiên mỗi lần chạy, không được lọt ra artifact |
| Lọc alert không do Gateway chuyển tiếp | `zap_normalizer._was_forwarded_by_dast_gateway()` | Trang 401/403 của chính Gateway không bị tính thành lỗ hổng của WebGoat |

---

## 2. Vì sao cần mở rộng

Worklog §2 ghi rõ phần cố ý chưa làm. Bốn phần đó là nội dung của tài liệu này.

**Vấn đề lớn nhất: scan đang chạy ẩn danh.** WebGoat bắt đăng nhập cho mọi lesson
(`WebSecurityConfig.java:34-44` chỉ `permitAll` cho asset tĩnh, `/registration`,
`/register.mvc`, `/actuator/**` và `/login`). 19 URL tìm được là **toàn bộ bề mặt công
khai**; không URL nào trong đó chứa lỗ hổng thật. Alert thu được là alert cấu hình
(thiếu CSP, thiếu X-Content-Type-Options…), không phải lỗ hổng ứng dụng.

Hệ quả: DAST hiện chứng minh **đường ống chạy được**, chưa chứng minh **lỗ hổng nào**.
Và bước `propose` của Agent vẫn chưa có thêm căn cứ nào so với trước.

---

## 3. Gateway giữ session, không phải ZAP

### 3.1 Vì sao không cho ZAP giữ session

Lane DAST chặn đăng nhập bằng **hai cơ chế độc lập**, cả hai đều được
`tests/unit/gateway/test_dast_gateway_config.py` khoá:

- `if ($request_method !~ ^(GET|HEAD)$) { return 405; }` → ZAP không POST được credential.
- `proxy_pass_request_headers off;` → cookie của ZAP bị xoá trước khi tới WebGoat.

Nới hai điều này để ZAP tự đăng nhập là phá đúng thứ làm lane này an toàn.

### 3.2 Cách làm

`ZAP_AUTH_HEADER` cho thấy header chỉ sống ở chặng **ZAP → Gateway**; từ Gateway →
WebGoat thì bị xoá sạch. Vậy để **Gateway** giữ session:

```nginx
location ^~ /WebGoat/ {
    limit_req zone=sentinel_dast_rl burst=20 nodelay;
    proxy_set_header Cookie "JSESSIONID=${SENTINEL_DAST_SESSION}";
    proxy_pass http://webgoat:8080;
    proxy_redirect http://webgoat:8080/ http://gateway-dast:8081/;
}
```

ZAP vẫn ẩn danh, vẫn GET/HEAD, vẫn không body. Gateway là thứ duy nhất biết credential —
đúng vai trò nó đang đóng với `SENTINEL_GATEWAY_API_KEY`.

**Không test nào trong `test_dast_gateway_config.py` bị vi phạm.** Chúng khẳng định
`proxy_pass_request_headers off` và GET/HEAD-only; thêm một `proxy_set_header` do chính
Gateway đặt không đụng vào hai điều đó.

### 3.3 Lấy session ở đâu

Entrypoint của image `nginx:1.27-alpine` xử lý `/docker-entrypoint.d/` như sau — đã kiểm
chứng bằng cách đọc `/docker-entrypoint.sh` trong chính image:

```sh
find "/docker-entrypoint.d/" -follow -type f -print | sort -V | while read -r f; do
    case "$f" in
        *.envsh)  . "$f"   ;;   # SOURCE → export truyền được sang script sau
        *.sh)     "$f"     ;;   # CHẠY   → export KHÔNG truyền được
```

Nên script lấy session phải có đuôi **`.envsh`** và phải **executable**. Đặt tên
`16-acquire-dast-session.envsh`: chạy sau `15-local-resolvers.envsh` của nginx và trước
`20-envsubst-on-templates.sh`, nên biến nó export sẽ được envsubst thay vào template —
đúng cơ chế mà `${SENTINEL_DAST_API_KEY}` đang dùng.

Script làm ba việc:

1. `POST webgoat:8080/WebGoat/register.mvc` với username/password hợp lệ theo
   `UserForm.java:22-34` (`[a-z0-9-]*` 6–45 ký tự; mật khẩu 6–10). Vì
   `RegistrationController.java:60` gọi `request.login(...)` ngay sau khi tạo user, một
   POST là ra `JSESSIONID`. Vì `WebSecurityConfig.java:61` tắt CSRF, không cần token.
2. Trích `JSESSIONID` từ `Set-Cookie`, `export SENTINEL_DAST_SESSION=…`.
3. Thất bại thì **chết hẳn** (`exit 1`), giống `00-require-key.sh`. Một Gateway DAST khởi
   động không session sẽ crawl ẩn danh và "thành công" trong im lặng — đó là kiểu hỏng tệ
   nhất, vì nó trông giống thành công.

`depends_on: webgoat: condition: service_healthy` đã bảo đảm WebGoat sẵn sàng trước khi
gateway-dast khởi động, nên bước 1 không cần tự retry vòng đời.

**Request này đi thẳng tới WebGoat, không qua Gateway.** Điều đó chấp nhận được và cần
nói rõ: người thực hiện là **chính Gateway**, ở thời điểm khởi động, với một request cố
định đã review, không có ZAP và không có LLM tham gia. Gateway là thành phần được tin để
nói chuyện với WebGoat; đây là nó tự cấu hình chính nó.

**Chưa kiểm chứng:** `nginx:1.27-alpine` có `wget` của busybox (healthcheck đang dùng),
nhưng việc trích `Set-Cookie` từ một POST bằng busybox wget chưa được thử. Task đầu tiên
của plan phải xác minh; nếu không làm được thì thêm `curl` vào Dockerfile.

### 3.4 Chặn `/logout`

`grep -n logout` trên template hiện **không ra dòng nào**. Crawl ẩn danh thì vô hại. Có
session dùng chung thì spider bấm trúng `/WebGoat/logout` sẽ giết session, và phần còn lại
của scan âm thầm chạy ẩn danh — vẫn "thành công", vẫn ra report, nhưng rỗng.

Chặn ở lane, không ở ZAP:

```nginx
location ^~ /WebGoat/logout { return 403; }
```

Đặt trước `location ^~ /WebGoat/`. Chặn ở Gateway thay vì ở cấu hình ZAP vì đó là chỗ
không caller nào quên được — cùng lý lẽ với hai allowlist.

---

## 4. Gộp finding theo loại alert

### 4.1 Vấn đề

`zap_normalizer.normalize_zap_report` hiện tạo **một finding cho mỗi instance**, dedupe
theo `sha256(plugin_id, method, uri, param)`. Với 19 URL ẩn danh thì ra 25 finding — chấp
nhận được.

Quét có session sẽ ra hàng trăm URL. Mà `WebSecurityConfig.java:62` gọi
`headers.disable()`, nên **mọi URL** dính alert thiếu CSP / X-Content-Type-Options / HSTS.
Số finding sẽ tăng theo tích số URL × alert cấu hình, làm nổ `zap-findings.json` và đốt
token nếu đưa vào bước analyze.

### 4.2 Cách làm

Một finding cho mỗi **loại alert** (`pluginid`), kèm `instances[]` liệt kê URL/method/param
bị ảnh hưởng, **cắt ở 20 instance đầu** và giữ `instances_total` là con số đầy đủ. Chọn 20
vì đủ để thấy một alert trải khắp ứng dụng hay chỉ ở một chỗ, mà không kéo hàng trăm URL
gần giống nhau vào prompt.

`file_or_url` giữ URL của instance đầu tiên. `_was_forwarded_by_dast_gateway()` vẫn lọc ở
mức instance, **trước** khi gộp.

### 4.3 Đánh đổi phải ghi vào số liệu

"Một finding" của DAST sau thay đổi này **không cùng hạt** với "một finding" của OpenGrep.
`metrics.json` phải nói rõ (§7.6), nếu không `findings_total` thành con số gây hiểu nhầm.

---

## 5. Đối chiếu SAST ↔ DAST

### 5.1 Cầu nối

Finding SAST là `SqlInjectionLesson5a.java:47`; endpoint DAST là
`/WebGoat/SqlInjection/attack5a`. Cầu nối là **annotation route Spring trong chính file
chứa finding**. WebGoat là Spring MVC, nên class chứa dòng bị OpenGrep bắt gần như luôn
khai `@GetMapping` / `@PostMapping` / `@RequestMapping` với path cụ thể.

Trích annotation là thao tác **tất định, đọc file, không hỏi LLM** — cùng loại với
`extract_source_window`. Vì tất định nên kết quả đủ tin để ghi đè lời khai của Agent (§6).

### 5.2 Module

`src/project_sentinel/analysis/correlation.py`:

- `extract_route(source_path: Path) -> str | None` — ghép `@RequestMapping` mức class với
  mapping mức method.
- `correlate(findings, endpoints, *, project_root) -> list[dict]` — gắn khối
  `runtime_evidence` vào mỗi finding **tĩnh**. Finding ZAP không nhận khối này: nó đã *là*
  bằng chứng runtime.

| `strength` | Nghĩa |
| :--- | :--- |
| `reachable_and_alerted` | Route có thật, ZAP chạm được, **và** có alert ZAP trên chính URL đó |
| `reachable` | Route có thật và ZAP chạm được |
| `route_known_not_reached` | Trích được route nhưng ZAP không tới |
| `no_route` | Không trích được route |

### 5.3 Nguồn bản đồ endpoint

Bản của Codex hiện **không sinh file endpoint riêng** — chỉ có `zap-findings.json`. Nhưng
`artifacts/dast/gateway-access.log` đã có sẵn mọi request ZAP thật sự gửi, ở tầng hạ tầng.

**Quyết định: đọc bản đồ endpoint từ chính access log đó**, không thêm hook ZAP. Ba lý do:
nó là bằng chứng hạ tầng chứ không phải lời khai của công cụ; nó đã được `scan-zap.sh` ghi
lại và kiểm rò key; và nó không cần đụng vào ZAP.

Thêm `parse_gateway_access_log(path) -> dict` trong `correlation.py`, trả cùng hình dạng
`{"endpoints": [{"method", "url", "params"}]}`.

---

## 6. `reachability` do Python đo

### 6.1 Thay đổi

Hiện `reachability` là trường **Agent tự khai**. Vì không chứng minh được, luật
`confirmed_requires_proof` trong `calibration.py` hạ cấp gần như mọi kết luận.

> `reachability` thôi là trường Agent khai. Python tính nó từ correlation và **ghi đè** giá
> trị Agent đưa ra.

Chữ ký mới: `calibrate_record(record, *, measured_reachability: str | None = None)` —
keyword-only, mặc định `None`, nên mọi lời gọi cũ giữ nguyên hành vi. Luật mới ghi vết bằng
`Calibration.rules` giá trị `"reachability_measured"`.

Ánh xạ: `reachable` hoặc `reachable_and_alerted` → `proven`; `route_known_not_reached` →
`not_proven`; `no_route` → `None` (không đo được thì không khai, giữ nguyên lời Agent).

### 6.2 Sửa một bất biến đã ghi thành văn

Docstring đầu `calibration.py` viết: *"Chỉ hạ, không bao giờ nâng."* Phép đo có thể **nâng**
`reachability`. Không sửa docstring thì contract của module thành lời nói dối.

Phát biểu mới, phải viết vào chính file đó:

- **Chỉ hạ dựa trên văn xuôi của Agent.** Mọi luật đọc output của Agent chỉ được hạ cấp.
- **Trường đo được thì lấy số đo, cả khi số đo cao hơn.** Đây không phải nâng kết luận của
  Agent — đây là thay một lời khai bằng một phép đo. Cùng lý do khối `calibration` do Agent
  tự sinh bị bỏ đi.

### 6.3 Giới hạn phải nói trước

Đo được **reachability**, **không** đo được `attacker_control`. Muốn `attacker_control:
proven` thì cần alert từ **active scan** — thứ cố ý không làm (§9). Nên verdict **không**
nhảy lên `confirmed`; nó chỉ thoát khỏi cảnh mọi thứ đều bị hạ cấp.

---

## 7. Nối DAST vào luồng chín bước

### 7.1 Hiện trạng

DAST là lane riêng: `make dast` → `make scan-all` → `artifacts/normalized/all-findings.json`.
Nó **không** nằm trong `python -m project_sentinel.cli run`.

### 7.2 Cách làm

Gộp vào bước `scan`. **Số bước vẫn là chín**; `STEP_NAMES` không đổi.

- `RunContext` thêm `dast_command: list[str]`, mặc định `scripts/scan-zap.sh` nếu file tồn
  tại và executable, ghi đè bằng `SENTINEL_DAST_COMMAND`. Rỗng nghĩa là bỏ qua.
- `step_scan` chạy SAST trước (vẫn bắt buộc thành công), rồi DAST. DAST hỏng hoặc không có
  Docker thì ghi `detail={"dast": "skipped", "dast_reason": …}` cộng một dòng `warn`,
  **không kéo cả bước fail**. SAST là xương sống; máy dev không Docker vẫn phải chạy được.
- `step_normalize` gọi `merge_files()` đã có sẵn để trộn `zap-findings.json` vào
  `findings.json`, rồi gọi `correlate()` ở cuối bước.

Tái dùng `merge_findings.merge_files` thay vì viết hàm trộn mới: nó đã có kiểm trùng ID và
giữ provenance nguồn, và đã có test.

### 7.3 Hai hình dạng trường phải hoà giải

`zap_normalizer` dùng `cwe: list[str]` (`["CWE-89"]`) và `owasp: []`, trong khi
`normalizer.py` của OpenGrep dùng giá trị vô hướng từ metadata. Sau khi trộn, `findings.json`
sẽ chứa **hai hình dạng cho cùng một trường**. Bước analyze và provenance validator phải
chấp nhận cả hai, hoặc normalize về một dạng lúc trộn. **Quyết định: chuẩn hoá về list ở
lúc trộn**, vì list là dạng tổng quát hơn và ZAP đã dùng nó.

Tương tự, `zap_normalizer` đặt `line: 0` còn OpenGrep đặt số dòng thật hoặc `None`. Điều
phối bằng `line > 0` chứ không bằng `line is not None`.

### 7.4 Bằng chứng cho finding DAST

`evidence.extract_source_window` cần file+line; finding ZAP không có. Thêm nhánh điều phối
`evidence_for_finding(finding, *, project_root, target_root)`, **không sửa nhánh cũ**:

| Finding | Bằng chứng |
| :--- | :--- |
| có `file` và `line > 0` | `extract_source_window()` — y nguyên như hiện nay |
| `tool == "zap"` | khối URL/method/param từ chính alert, kèm `instances_total` |

### 7.5 Provenance cho vị trí URL

`schemas/security-analysis-record.schema.json` hiện định nghĩa `locations.items` với
`"required": ["file","line"]` và `"additionalProperties": false` — một vị trí URL **không
diễn đạt được**. Phải mở thành `oneOf` hai hình dạng: `{file, line}` **hoặc**
`{url, method?, param?}`.

Validator nhận thêm nhánh URL, **giữ nguyên kỷ luật cũ**: Agent chỉ được nhắc tới URL có
thật trong input findings.

### 7.6 Số liệu

`collect_metrics` thêm:

- `findings_by_tool: {"opengrep": n, "zap": m}`
- `dast: {endpoints_discovered, alerts_total, instances_total}`
- Phân bố `strength` của correlation

Giữ `findings_total` nguyên nghĩa cũ để không phá test đang có.

---

## 8. Kiểm chứng

[`AGENTS.md`](../../../AGENTS.md) §2.2: không mock, và test không tới được dependency thì
**fail chứ không skip**.

| Test | Khẳng định điều gì |
| :--- | :--- |
| Session thật sự có tác dụng | Bản đồ endpoint phải chứa URL **ngoài** danh sách `permitAll`. Bằng 0 nghĩa là session hỏng và toàn bộ giá trị DAST biến mất trong im lặng |
| `/logout` bị chặn | Request tới `/WebGoat/logout` qua lane DAST trả 403 |
| Gateway không rò session | `JSESSIONID` không xuất hiện trong report, access log hay bất kỳ artifact nào — mở rộng đúng cách `scan-zap.sh` đang kiểm key DAST |
| Chính sách lane không hồi quy | `test_dast_gateway_config.py` hiện có vẫn xanh nguyên, không sửa một assertion nào |
| Gộp alert | Một `pluginid` cho ra đúng một finding, `instances` ≤ 20, `instances_total` là số thật |
| Correlation | Trên file WebGoat **có thật**, không phải ví dụ bịa |
| Calibration | `measured_reachability` ghi đè cả hai chiều; `confirmed` vẫn bị hạ khi thiếu `attacker_control` |

Fixture là output ZAP **thật đã ghi lại**, không phải JSON viết tay.

---

## 9. Ngoài phạm vi (cố ý không làm)

| Việc | Vì sao |
| :--- | :--- |
| Active scan | 15–40+ phút, kết quả dao động, làm bẩn trạng thái WebGoat, khó đưa vào CI |
| Cho ZAP tự giữ credential | Phá đúng hai cơ chế làm lane DAST an toàn (§3.1) |
| Cho probe của Agent mang session | Bán kính thiệt hại lớn nhất từ trước tới nay; cần vòng thiết kế riêng |
| Sinh ứng viên allowlist từ endpoint DAST | Probe của Agent vẫn ẩn danh, nên ứng viên dùng được gần như chỉ còn `/registration` và `/actuator/*` — không đáng làm cho tới khi giải quyết câu trên |
| Tự động sinh allowlist Nginx | Phá tính độc lập của hai lớp allowlist |

---

## 10. Thứ tự thực thi

```text
Task 1   Xác minh busybox wget trích được Set-Cookie; chốt cách lấy session
   │
Task 2   16-acquire-dast-session.envsh + proxy_set_header Cookie + chặn /logout
   │
Task 3   Chạy thật, ghi fixture MỚI từ scan CÓ session
   │
Task 4   Gộp finding theo loại alert  ← bắt buộc trước khi số URL nổ
   │
Task 5   parse_gateway_access_log + extract_route + correlate
   │
Task 6   calibrate_record(measured_reachability=…) + sửa docstring bất biến
   │
Task 7   dast_command + step_scan + step_normalize (merge_files + correlate)
   │
Task 8   schema oneOf + validator URL + evidence_for_finding
   │
Task 9   metrics + tài liệu
```

Task 4 phải xong **trước** khi bất kỳ thứ gì đọc `zap-findings.json` ở quy mô có session,
nếu không mọi bước sau làm việc trên một file đã nổ.
