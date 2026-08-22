# Thiết kế: chứng minh reachability cho endpoint POST của WebGoat

**Ngày:** 2026-08-22 · **Trạng thái:** thiết kế đã duyệt, chưa implement
**Branch:** `feat/zap-dast`
**Xây trên:** [`2026-08-22-dast-zap-design.md`](2026-08-22-dast-zap-design.md) và lane
Gateway DAST đã chạy trong production từ PR #46.

---

## 1. Vấn đề đo được

Sau khi DAST vào production, đối chiếu SAST ↔ DAST trên dữ liệu thật cho:

```
no_route: 4    route_known_not_reached: 19    reachable: 0
```

`reachability` do Python đo vì thế **chỉ biết hạ cấp**, không bao giờ nâng — đúng phần
giá trị mà cả tầng đo tồn tại để tạo ra.

### 1.1 Nguyên nhân không phải cái ai cũng nghĩ

Giả thuyết ban đầu là spider của ZAP Baseline không chạy JavaScript nên không tới được
bài học WebGoat. Điều đó **đúng nhưng không phải nguyên nhân chính**.

Nguyên nhân thật: **19 finding đó đều trỏ vào endpoint `@PostMapping`**, còn lane DAST là
GET/HEAD-only.

```java
@PostMapping("/SqlInjection/attack2")        SqlInjectionLesson2.java:40
@PostMapping("/SqlInjection/attack5")        SqlInjectionLesson5.java:53
@PostMapping("/InsecureDeserialization/task") InsecureDeserializationTask.java:32
```

```nginx
if ($request_method !~ ^(GET|HEAD)$) { return 405; }
```

Hệ quả: **AJAX spider không giải quyết được việc này.** Trình duyệt submit form bằng POST
→ Gateway trả 405 → không tới WebGoat. Và `parse_gateway_access_log` bỏ mọi status ≥ 400
nên chúng cũng không được tính là chạm tới được — đúng như thiết kế.

Cách rẻ hơn — nạp thẳng 13 route mà `correlation.extract_route` đã trích tất định từ
annotation Java — cũng hỏng vì cùng lý do: GET tới một `@PostMapping` thì WebGoat trả 405.

**Khoảng cách thật nằm ở chính sách GET/HEAD-only của lane, không nằm ở spider.**

---

## 2. Ranh giới tin cậy

Lane DAST có năm lớp. Bốn lớp giữ nguyên, một lớp đổi.

| Lớp | Sau thay đổi |
| :--- | :--- |
| Credential riêng `SENTINEL_DAST_API_KEY` | **Giữ** |
| `proxy_pass_request_headers off` | **Giữ** |
| `proxy_pass_request_body off` | **Giữ** |
| Chỉ nội bộ, không bind cổng host | **Giữ** |
| `request_method !~ ^(GET\|HEAD)$ → 405` | **Đổi** — POST được phép, chỉ với path có trong `dast-allowlist.json` |

Phát biểu bất biến mới:

> Nội dung WebGoat nhận được từ lane DAST **do lane quyết định hoàn toàn**. ZAP không ảnh
> hưởng được method, path, header hay body. Path phải có trong allowlist; body là hằng số
> đã review gắn với chính path đó.

Đây là quyết định tin cậy **hẹp hơn** lane probe của Agent: lane probe còn để caller *chọn*
template qua header `X-Sentinel-Template`; lane DAST thì ZAP không chọn được gì cả — nó chỉ
nêu một path, và nếu path đó có trong allowlist thì lane tự dựng toàn bộ request.

### 2.1 Cái giá phải trả, nói thẳng

`if ($content_length) { return 413; }` và `client_max_body_size 1` hiện chặn mọi body ngay
từ đầu. ZAP sẽ gửi body form, nên nginx phải **đọc rồi vứt** nó. Lane vì thế chấp nhận body
tới một giới hạn — đề xuất **8k**, dư cho form của ZAP và xa dưới mức đáng lo.

Rủi ro thu hẹp thành *"nginx xử lý một body rồi bỏ"*, **không** phải *"WebGoat nhận body
đó"*. Cơ chế bảo đảm điều này là `proxy_set_body`, và nó **đã được chứng minh trong chính
repo**: `tests/integration/test_gateway_policy_enforcement.py::test_a_body_of_the_canonical_length_is_still_rewritten`
khẳng định Gateway vứt body của caller kể cả khi độ dài khớp.

### 2.2 Test đang khoá lane phải được sửa

`tests/unit/gateway/test_dast_gateway_config.py::test_dast_listener_only_forwards_read_only_methods`
khẳng định `$request_method !~ ^(GET|HEAD)$`. Chính sách đó **là** thứ đang thay đổi, một
cách có chủ ý và có thiết kế.

Test đó phải được **viết lại để khoá chính sách mới**, không phải nới ra cho qua. Chính sách
mới chặt hơn ở hai điểm mà test mới phải khẳng định: path phải có trong allowlist, và body
là hằng số của lane chứ không phải của caller.

---

## 3. Cơ chế

### 3.1 File allowlist riêng

`configs/gateway/dast-allowlist.json`:

```json
{
  "schema_version": "1.0",
  "endpoints": [
    {
      "path": "/WebGoat/SqlInjection/attack2",
      "method": "POST",
      "canonical_body": "query=",
      "content_type": "application/x-www-form-urlencoded",
      "purpose": "Chứng minh endpoint sống. Body rỗng làm executeQuery ném exception, WebGoat bắt lại và trả 200 — không câu SQL nào chạy.",
      "source": "benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson2.java:40-42"
    }
  ]
}
```

Tách khỏi `endpoint-allowlist.json` vì đó là hai quyết định tin cậy khác hẳn nhau: Agent có
người duyệt từng request, còn ZAP chạy tự động hàng trăm request. Trộn chúng nghĩa là một
chỉnh sửa cho bên này lặng lẽ đổi bề mặt của bên kia.

### 3.2 Cổng method trong nginx

```nginx
# Body chính tắc theo PATH. Rỗng nghĩa là path đó KHÔNG được POST.
map $uri $sentinel_dast_post_body {
    default "";
    "/WebGoat/SqlInjection/attack2" "query=";
}

# POST chỉ hợp lệ khi path có body chính tắc. GET/HEAD luôn hợp lệ.
map "$request_method:$sentinel_dast_post_body" $sentinel_dast_method_ok {
    default 0;
    "~^GET:"     1;
    "~^HEAD:"    1;
    "~^POST:.+"  1;
}
```

Rồi `if ($sentinel_dast_method_ok = 0) { return 405; }`.

Một POST tới path không có trong map rơi vào `default 0` → 405. **Deny-by-default nằm trong
chính cấu trúc map**, không phải trong một danh sách phủ định phải nhớ cập nhật. "Path không
có body chính tắc" và "path không được POST" trở thành cùng một điều, nên không thể quên
đồng bộ hai danh sách.

### 3.3 Giữ tính độc lập hai allowlist

**Không sinh nginx từ JSON.** Người viết cả hai bên, và một test đối chiếu chúng không lệch
— đúng khuôn `test_gateway_config_matches_registry.py` đang làm cho lane probe. Script sinh
cả hai từ một nguồn sẽ biến hai lớp kiểm thành một lớp.

### 3.4 Chưa kiểm chứng

Lane hiện có `proxy_set_header Content-Length "";`. Với `proxy_set_body`, nginx phải tự tính
lại Content-Length cho body mới. Dòng đó có thể làm hỏng POST. **Task đầu của plan phải thử
thật rồi mới viết tiếp.**

### 3.5 Danh sách endpoint không chốt ở spec này

Spec định nghĩa *hình dạng* và *quy trình*, không định nghĩa danh sách. Tham số khác nhau ở
từng endpoint — đã đọc thấy `query`, `userid_6a`, `userid_6b`, `action_string`,
`name`+`auth_tan`, `field1`, `editor` — nên không có body dùng chung.

Mỗi mục phải: đọc `@RequestParam` thật, chọn body **làm ít nhất có thể**, trích dẫn dòng
nguồn, và được người duyệt. Plan có một task riêng cho việc này. Chốt danh sách bây giờ là
đoán tham số của 13 endpoint khi mới đọc 8.

---

## 4. Ai gửi POST — và vì sao không phải AJAX spider

Mở POST ở lane **không tự làm ZAP gửi POST**. Spider tĩnh chưa từng khám phá ra
`/SqlInjection/attack2` vì nó nằm sau JavaScript.

**Giải pháp: ZAP Automation Framework `requestor` job.** Đã xác nhận có trong plugin
`automation-beta-0.60.0.zap` của image đã pin.

Thêm một bước ZAP **thứ hai** chạy `requestor`, gửi đúng các POST đã allowlist tới
`gateway-dast:8081`. Baseline hiện tại **giữ nguyên không đụng tới**, kể cả cờ `--autooff`
vốn có lý do đã ghi trong `test_zap_scan_script.py` (*"ZAP 2.17 Automation Framework ignores
-I exit semantics"*). Hai lần gọi ZAP, mỗi lần một việc, không lần nào phá lần kia.

### 4.1 Vì sao bỏ AJAX spider

Khoảng cách đo được là 19 finding trỏ vào 13 route **đã biết chính xác**. Đây là bài toán
*chạm tới route đã biết*, không phải bài toán *khám phá*. AJAX spider giải bài toán khám
phá, với giá là: một trình duyệt (Firefox có sẵn trong image nhưng
`Sandbox: CanCreateUserNamespace() clone() failure: EPERM` dưới profile Docker mặc định),
thời gian crawl, và một trận nổ finding.

Hướng `requestor` khớp với kiến trúc hơn: **tập request được khai báo và review trước, không
do công cụ tự khám phá lúc chạy** — đúng nguyên tắc mà cả hai allowlist đang phục vụ.

AJAX spider vẫn có giá trị cho một mục tiêu **khác**: mở rộng bề mặt quan sát để tìm endpoint
mà SAST không biết. Đó là việc riêng, không thuộc spec này.

### 4.2 Một cách rẻ hơn đã bị loại bỏ

Cho lane dùng `proxy_method` biến GET thành POST chính tắc. **Loại.** Access log sẽ ghi
`method=GET` trong khi WebGoat nhận POST — bằng chứng nói dối. Với hệ thống lấy access log
làm bằng chứng hạ tầng thì đó là điều không đánh đổi được.

### 4.3 Hạ nguồn gần như không phải sửa gì

| Thành phần | Sửa? |
| :--- | :--- |
| `parse_gateway_access_log` | **Không** — đã ghi method, đã bỏ status ≥ 400 |
| `_route_matches` | **Không** — so theo path, `/WebGoat/SqlInjection/attack2` khớp route `/SqlInjection/attack2` |
| `correlate` | **Không** — 19 finding tự chuyển sang `reachable` |
| `calibration` | **Không** — `measured_reachability = "proven"` chảy qua đường đã dựng |
| Số finding | Vài request, không nổ |

Toàn bộ hạ tầng đo reachability đã dựng và đã kiểm chứng từ đợt trước; thứ còn thiếu đúng là
**traffic chạm tới đúng chỗ**.

---

## 5. Một lỗ hổng phát hiện khi rà, sửa trong đợt này

`correlation.py:54` dùng `if status >= 400: continue`. Nghĩa là **302 được tính là chạm tới
được**. Một endpoint sau auth trả 302 về `/login` là *không* chạm tới được, nhưng hiện nó
vẫn ghi thành `reachable`.

Session do Gateway giữ khiến điều đó ít xảy ra, nhưng đây là bằng chứng đếm sai theo hướng
**lạc quan** — kiểu sai tệ nhất cho một công cụ đo độ phủ. Siết thành **chỉ 2xx**.

---

## 6. Kiểm chứng

### 6.1 Phải đo bằng chạy thật, không suy luận

| Câu hỏi | Vì sao không đoán được |
| :--- | :--- |
| `proxy_set_header Content-Length "";` có làm hỏng POST không | Với `proxy_set_body` nginx phải tự tính lại độ dài |
| WebGoat trả **200** hay 500 cho `query=` rỗng | Thiết kế dựa trên "exception bị bắt, trả AttackResult" |
| `requestor` job có đi qua Gateway đúng không | Phải thấy dòng `method=POST` trong access log |
| Body ZAP có thật sự bị vứt không | Bất biến quan trọng nhất — phải chứng minh, không tin |

### 6.2 Test bắt buộc

- **Canary body.** ZAP POST một body chứa chuỗi nhận dạng riêng tới path đã allowlist.
  Khẳng định WebGoat nhận đúng body chính tắc, và chuỗi canary **không xuất hiện ở bất kỳ
  đâu** trong response, report hay log. Bản sao của
  `test_a_reviewed_template_does_not_licence_an_unreviewed_body` — test đã bắt được một
  bypass thật ở vòng review 82/100.
- **POST tới path chưa allowlist → 405.** Deny-by-default ở tầng hạ tầng.
- **GET/HEAD không hồi quy.** Mọi hành vi lane cũ giữ nguyên.
- **Hai bên không lệch.** `dast-allowlist.json` và map nginx phải khớp.
- **Mỗi `source` trỏ tới dòng có thật.** Test đọc file Java, khẳng định dòng được trích tồn
  tại và chứa `@PostMapping` tương ứng.
- **Chỉ 2xx mới là reachable.** Ca 302 phải **không** được tính.

---

## 7. Rủi ro còn tồn tại

1. **Mỗi mục allowlist là một request thật vào ứng dụng có lỗ hổng.** Cổng bảo vệ duy nhất
   là người đọc `@RequestParam` rồi chọn body làm ít nhất có thể. Không cơ chế nào cứu được
   một mục review ẩu.
2. **Body chính tắc gắn với một phiên bản WebGoat.** Nâng `webgoat:v2025.3` lên bản khác có
   thể đổi tên tham số; lúc đó POST vẫn 200 nhưng vô nghĩa. Test trích dẫn dòng nguồn bắt
   được nếu file đổi, **không** bắt được nếu chỉ tên tham số đổi.
3. **Reachability không phải khai thác.** Sau đợt này 19 finding thành `reachable`, nhưng
   `attacker_control` vẫn `not_proven` — nên `confirmed` vẫn ngoài tầm với. Phải nói rõ
   trong `limitations.md` để không ai đọc số mới thành "đã chứng minh lỗ hổng".

---

## 8. Ngoài phạm vi (cố ý không làm)

| Việc | Vì sao |
| :--- | :--- |
| AJAX spider | Giải bài toán khám phá, không phải bài toán này (§4.1) |
| Active scan | Payload khai thác thật; lane này tồn tại để ngăn đúng điều đó |
| Cho ZAP chọn body | Phá bất biến §2 |
| Sinh danh sách POST từ finding SAST lúc chạy | Để công cụ tự nới bề mặt tấn công của chính nó |
| Sinh map nginx từ JSON | Phá tính độc lập của hai lớp allowlist (§3.3) |

---

## 9. Thứ tự thực thi

```text
Task 1  Xác minh Content-Length + proxy_set_body, và WebGoat trả gì cho body rỗng
   │    (chưa viết code sản phẩm — chỉ trả lời câu hỏi và ghi worklog)
Task 2  Đọc @RequestParam của từng endpoint, dựng dast-allowlist.json, người duyệt
Task 3  Map nginx + cổng method, viết lại test khoá chính sách
Task 4  requestor job + lần gọi ZAP thứ hai trong scan-zap.sh
Task 5  Siết reachable về chỉ 2xx
Task 6  Chạy thật, đo lại phân bố strength, cập nhật tài liệu
```

Task 1 chặn mọi task sau: nếu `Content-Length ""` làm hỏng POST hoặc WebGoat không trả 2xx
cho body rỗng thì thiết kế body chính tắc phải đổi trước khi viết bất cứ gì.
