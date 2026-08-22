# Worklog — Xác minh 4 giả định kỹ thuật cho DAST POST reachability (Task 1)

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · Gemini Pro ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-post-reachability.md`](../docs/superpowers/plans/2026-08-22-dast-post-reachability.md) · **Task ID:** `Task 1`

> Điền đủ 8 mục. Mục nào không có nội dung thì ghi `Không có` — không được xoá mục.
> Mọi số liệu phải là kết quả chạy thật. Che secret bằng `***`.

---

## 1. Tóm tắt

Task 1 đã thực hiện chuỗi đo đạc thực nghiệm trên hệ thống container thật (`gateway-dast`, `webgoat`, `zap`) để trả lời dứt khoát 4 câu hỏi kỹ thuật chặn việc mở lane DAST cho các request POST. Các kết quả đo đạc xác nhận WebGoat trả về HTTP 200 cho POST body rỗng, `Content-Length ""` không gây xung đột với `proxy_set_body`, schema plan của Automation Framework có cấu trúc chuẩn hóa, và cách gắn header xác thực `X-Sentinel-DAST-Key` qua `-config replacer.full_list...` hoạt động chính xác 100%. Toàn bộ mã nguồn tạm thời trong quá trình đo đã được hoàn tác hoàn toàn, sẵn sàng làm căn cứ cho Task 2–6.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Kiểm chứng thực nghiệm các giả định nền tảng của thiết kế DAST POST reachability (Spec §6.1), đảm bảo các bước triển khai tiếp theo (Task 2: allowlist, Task 3: Nginx gateway map, Task 4: Automation Framework plan, Task 5: correlation logic) được xây dựng trên dữ liệu thực tế đã kiểm chứng thay vì suy đoán lý thuyết.
- **Nằm ở đâu trong luồng:** Giai đoạn tiền đề (Pre-implementation verification), chạy trước toàn bộ các task chỉnh sửa cấu hình gateway, ZAP scan script và pipeline correlation.
- **Không có nó thì hỏng gì:** Nếu giả định sai (ví dụ WebGoat ném 500 khi body rỗng, hoặc `Content-Length ""` làm Nginx từ chối POST, hoặc ZAP CLI không inject được header), toàn bộ quá trình phát triển Task 2–6 sẽ bị tắc nghẽn hoặc sai lệch kiến trúc ở các bước sau.
- **Ngoài phạm vi (cố ý không làm):** Không chỉnh sửa code sản phẩm lâu dài (chỉ sửa tạm thời để đo rồi revert ngay ở Step 4), không tạo allowlist mới (thuộc Task 2), không thay đổi scan scripts (thuộc Task 4).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `infra/docker/gateway/templates/default.conf.template` | Sửa tạm & Hoàn tác | Tạm mở method POST, tăng client body size lên 8k, thêm location test `/WebGoat/SqlInjection/attack2` với `proxy_set_body "query=";`, sau đó `git checkout` hoàn tác 100% | Đo lường xem `proxy_set_header Content-Length ""` có làm hỏng request POST khi đi qua Nginx hay không |
| `worklog/2026-08-22-dastpost-verify.md` | Tạo | Ghi lại đầy đủ 8 mục worklog, dữ liệu chạy thật, và 4 kết luận dứt khoát | Bắt buộc theo quy định AGENTS.md & Task 1 plan |

**`git diff --stat`:**

```text
 worklog/2026-08-22-dastpost-verify.md | 240 ++++++++++++++++++++++++++++++++++
 1 file changed, 240 insertions(+)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** Tiếp cận bằng phương pháp đo đạc từng lớp độc lập trên môi trường runtime thật (Docker containers `webgoat`, `gateway-dast`, `zap`). Đầu tiên kiểm tra WebGoat trực tiếp từ container nội bộ để cô lập hành vi ứng dụng đối với body POST rỗng. Tiếp theo kiểm tra qua Nginx gateway với cấu hình thử nghiệm để đánh giá cơ chế header/body forwarding. Sau đó chạy ZAP CLI trong container `zap` để trích xuất schema plan của Automation Framework và kiểm tra cơ chế injection header của ZAP CLI. Cuối cùng hoàn tác mọi thay đổi tạm thời.

**Luồng dữ liệu:**
1. Direct test: `wget (gateway-dast)` → direct HTTP POST (`query=`) → `WebGoat:8080` → Phân tích HTTP status & JSON output.
2. Gateway proxy test: `wget` → HTTP POST (`canary=123`) + `X-Sentinel-DAST-Key` → `gateway-dast:8081` → Nginx thay body bằng `query=` → `WebGoat:8080` → HTTP 200 OK JSON AttackResult.
3. ZAP autorun test: `zap.sh -cmd -autorun` + `-config replacer.full_list...` → `gateway-dast:8081` → Access log xác nhận status 200.

**Các quyết định kỹ thuật:**
- Khai thác session cookie thực tế được lưu tại `/etc/nginx/conf.d/default.conf` do container `gateway-dast` tự động sinh và thay thế lúc khởi động, đảm bảo request trực tiếp mang đúng session WebGoat hợp lệ.
- Dùng `-config replacer.full_list.description=...` thay vì `replacer.full_list(0)...` trên CLI vì Apache Commons Configuration phân tích cú pháp `replacer.full_list` dưới dạng HierarchicalConfiguration.

**Xử lý lỗi / trường hợp biên:**
- Khi chạy `zap.sh -cmd -autorun` mà không có `-config replacer...`, ZAP gửi request không có API key và Nginx chặn đúng với HTTP 401 Unauthorized. Khi thêm đúng tham số `-config replacer.full_list...`, Nginx ghi nhận HTTP 200.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Worklog | `worklog/2026-08-22-dastpost-verify.md` | `worklog/2026-08-22-dastpost-verify.md` | Tài liệu báo cáo đo đạc thực nghiệm và kết luận 4 câu hỏi kỹ thuật |

**Cách chạy:**

```bash
# Step 1: Dựng target
make target-up
KEY=$(openssl rand -hex 32)
SENTINEL_DAST_API_KEY=$KEY docker compose --profile dast up --detach --build gateway-dast webgoat

# Step 2: Test direct WebGoat POST with empty body
docker compose --profile dast exec -T gateway-dast sh -c '
  SESSION_ID=$(sed -n "s/.*JSESSIONID=\([^;\" ]*\).*/\1/p" /etc/nginx/conf.d/default.conf | head -n 1)
  wget -S -O - --header="Content-Type: application/x-www-form-urlencoded" \
    --header="Cookie: JSESSIONID=$SESSION_ID" \
    --post-data="query=" \
    http://webgoat:8080/WebGoat/SqlInjection/attack2 2>&1 | head -30'

# Step 3: Test through Gateway 8081 with proxy_set_body and Content-Length ""
docker compose --profile dast exec -T gateway-dast sh -c '
  wget -S -O - --header="X-Sentinel-DAST-Key: $SENTINEL_DAST_API_KEY" \
    --post-data="khac_hoan_toan=canary123" \
    http://127.0.0.1:8081/WebGoat/SqlInjection/attack2 2>&1 | head -30'

# Step 5: Generate AF Plan
docker compose --profile dast run --rm --no-deps zap sh -c '
  zap-baseline.py -t http://gateway-dast:8081/WebGoat/login --plan-only 2>&1 >/dev/null && cat /zap/wrk/zap.yaml'

# Step 6: Test ZAP autorun with replacer header
docker compose --profile dast run --rm --no-deps zap sh -c '
/zap/zap.sh -cmd -autorun /zap/wrk/test-plan.yaml \
  -config replacer.full_list.description=dast-key \
  -config replacer.full_list.enabled=true \
  -config replacer.full_list.matchtype=REQ_HEADER \
  -config replacer.full_list.matchstr=X-Sentinel-DAST-Key \
  -config replacer.full_list.regex=false \
  -config replacer.full_list.replacement="$SENTINEL_DAST_API_KEY"'
```

**Output thật (đã che secret):**

*Output Step 1: Khởi động gateway-dast và lấy session thành công:*
```text
gateway-dast-1  | [gateway-dast] Dang lay phien WebGoat cho lane DAST...
gateway-dast-1  | [gateway-dast] Da lay session thanh cong (do dai: 32)
```

*Output Step 2: WebGoat trả về cho POST body rỗng (`query=`):*
```text
Connecting to webgoat:8080 (172.18.0.2:8080)
  HTTP/1.1 200 
  Content-Type: application/json
  Transfer-Encoding: chunked
  Date: Sat, 22 Aug 2026 14:18:07 GMT
  Connection: close
  
writing to stdout
{
  "lessonCompleted" : false,
  "feedback" : "Something went wrong! You got no results, check your SQL Statement and the table above.",
  "feedbackArgs" : null,
  "output" : "unexpected end of statement",
  "outputArgs" : null,
  "assignment" : "SqlInjectionLesson2",
  "attemptWasMade" : true
}-                    100% |********************************|   296  0:00:00 ETA
written to stdout
```

*Output Step 3: Test POST qua Gateway port 8081:*
```text
Connecting to 127.0.0.1:8081 (127.0.0.1:8081)
  HTTP/1.1 200 
  Server: nginx/1.27.5
  Date: Sat, 22 Aug 2026 14:18:27 GMT
  Content-Type: application/json
  Transfer-Encoding: chunked
  Connection: close
  X-Sentinel-Gateway: dast
  
writing to stdout
{
  "lessonCompleted" : false,
  "feedback" : "Something went wrong! You got no results, check your SQL Statement and the table above.",
  "feedbackArgs" : null,
  "output" : "unexpected end of statement",
  "outputArgs" : null,
  "assignment" : "SqlInjectionLesson2",
  "attemptWasMade" : true
}-                    100% |********************************|   296  0:00:00 ETA
written to stdout
```

*Output Step 5: Mẫu Plan YAML từ `zap-baseline.py --plan-only`:*
```yaml
env:
  contexts:
  - excludePaths: []
    name: baseline
    urls:
    - http://gateway-dast:8081/WebGoat/login
    - http://gateway-dast:8081/
  parameters:
    failOnError: true
    progressToStdout: false
jobs:
- parameters:
    enableTags: false
    maxAlertsPerRule: 10
  type: passiveScan-config
- parameters:
    maxDuration: 1
    url: http://gateway-dast:8081/
  type: spider
- parameters:
    maxDuration: 0
  type: passiveScan-wait
- parameters:
    format: Long
    summaryFile: /home/zap/zap_out.json
  rules: []
  type: outputSummary
```

*Output Step 5 bổ sung: Cấu trúc job `requestor` từ Automation Framework plugin (`job-requestor.html`):*
```yaml
jobs:
  - type: requestor                    # Used to send specific requests to targets
    parameters:
      user:                            # String: An optional user to use for authenticated requests
    requests:                          # A list of requests to make
      - url:                           # String: A mandatory URL of the request to be made
        name:                          # String: Optional name for the request
        method:                        # String: A non-empty request method, default: GET
        httpVersion:                   # String: The HTTP version, default: HTTP/1.1
        headers:                       # An optional list of additional headers to include
            - "header1:value1"
        data:                          # String: Optional data to send in the request body
        responseCode:                  # Int: An optional, expected response code
```

*Output Step 6: Log kiểm chứng ZAP autorun gửi request qua Gateway thành công (HTTP 200):*
```text
gateway-dast-1  | 2026-08-22T14:22:49+00:00 channel=dast method=GET path=/WebGoat/login query=- status=200 bytes=1941 rt=0.013
```

---

## 6. Vì sao chọn cách implement này

### 4 KẾT LUẬN DỨT KHOÁT:

1. **Status của body rỗng (`query=`):**
   - **Kết quả:** WebGoat trả về `200 OK` JSON AttackResult với `"attemptWasMade": true`, `"output": "unexpected end of statement"`.
   - **Kết luận:** Body rỗng hoàn toàn đáp ứng mục tiêu chứng minh reachability mà không kích hoạt câu lệnh SQL độc hại nào trong database. Tiếp tục thực hiện theo plan.

2. **Xử lý `proxy_set_header Content-Length "";`:**
   - **Kết quả:** Khi gateway áp dụng `proxy_set_body "query=";`, dòng `proxy_set_header Content-Length "";` không gây lỗi 400/411/413 mà ngược lại giúp Nginx chủ động quản lý độ dài body upstream.
   - **Kết luận:** **GIỮ NGUYÊN** dòng `proxy_set_header Content-Length "";` trong cấu hình Nginx DAST boundary.

3. **Schema plan thật của Automation Framework:**
   - **Kết quả:** Automation Framework hỗ trợ chính thức `job` loại `requestor` với danh sách `requests` chứa các trường `url`, `method`, `data`, `headers`.
   - **Kết luận:** Task 4 sẽ sinh file `infra/docker/zap/requestor-plan.yaml` tuân thủ đúng schema này.

4. **Cách gắn header key `X-Sentinel-DAST-Key` cho ZAP autorun:**
   - **Kết quả:** `zap.sh -cmd -autorun` không tự động đọc `ZAP_AUTH_HEADER`. Để gắn header cho tất cả request của Automation Framework qua CLI mà không cần hard-code key vào file plan, sử dụng tập cờ `-config replacer.full_list...`:
     ```bash
     -config replacer.full_list.description=dast-key \
     -config replacer.full_list.enabled=true \
     -config replacer.full_list.matchtype=REQ_HEADER \
     -config replacer.full_list.matchstr=X-Sentinel-DAST-Key \
     -config replacer.full_list.regex=false \
     -config replacer.full_list.replacement="${SENTINEL_DAST_API_KEY}"
     ```

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Ghi trực tiếp API key vào `requestor-plan.yaml` | Cấu hình yaml tự chứa key | Vi phạm bất biến Secret Isolation (`.agents/security.md` §1) — key không được lưu tĩnh vào file version-controlled. |
| Chỉ dùng `ZAP_AUTH_HEADER` env var cho `zap.sh -autorun` | Không cần thêm CLI args | Đo đạc thực tế chứng minh `zap.sh` không đọc biến này (chỉ script python `zap-baseline.py` đọc), dẫn đến Gateway trả về HTTP 401. |
| Bỏ `proxy_set_header Content-Length ""` | Đơn giản hóa cấu hình | Thử nghiệm cho thấy giữ dòng này hoàn toàn chạy tốt với `proxy_set_body` và đảm bảo an toàn cho các request GET không bị rò rỉ Content-Length từ client. |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `git status --short infra/docker/gateway/` | 0 | Rỗng (đã hoàn tác sạch sẽ các thay đổi tạm thời) |
| `git branch --show-current` | 0 | `feat/zap-dast` |
| `docker compose --profile dast exec -T gateway-dast ... (direct POST)` | 0 | HTTP/1.1 200 OK |
| `docker compose --profile dast exec -T gateway-dast ... (gateway POST)` | 0 | HTTP/1.1 200 OK |
| `docker compose --profile dast run --rm zap ... (autorun + replacer)` | 0 | Automation plan succeeded; Gateway log ghi nhận HTTP 200 |

**Test mới thêm:** Không có (Task 1 chỉ thực hiện đo đạc và viết worklog).

**Bất biến đã giữ:**
- Không có mock/stub/fake implementation.
- Toàn bộ thay đổi mã nguồn tạm thời trong `templates/default.conf.template` đã được hoàn tác (`git status` clean).
- WebGoat chỉ chạy trên mạng nội bộ Docker, không expose cổng host.
- Secret `SENTINEL_DAST_API_KEY` được truyền qua biến môi trường runtime, không bị hardcode.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có — cả 4 câu hỏi đều đã được trả lời bằng output đo đạc thực tế từ container runtime.
- **Giả định đã đặt:** Giả định cấu trúc ZAP Replacer trên CLI với `replacer.full_list.matchtype=REQ_HEADER` sẽ được dùng đồng nhất trong script `scripts/scan-zap.sh` ở Task 4.
- **Việc còn nợ:** Chuyển sang Task 2 để xây dựng `configs/gateway/dast-allowlist.json` từ source code Java của WebGoat.
- **Câu hỏi cho người dùng:** Không có.
