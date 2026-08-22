# Worklog — Xác minh busybox wget trích được Set-Cookie

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 1`

---

## 1. Tóm tắt

Đã thực nghiệm xác minh khả năng trích xuất `Set-Cookie` (chứa `JSESSIONID`) từ WebGoat bằng busybox `wget` có sẵn trong container Alpine của Nginx Gateway. Kết quả cho thấy `wget -S` kết hợp trích xuất dòng `Set-Cookie` đầu tiên lấy được session hợp lệ và truy cập thành công trang authenticated `/WebGoat/start.mvc` (HTTP 200). Quyết định: sử dụng trực tiếp busybox `wget`, không cần cài thêm `curl` vào image Gateway.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Khảo sát và đưa ra quyết định kỹ thuật chính xác cho cơ chế bootstrap session DAST ở entrypoint của Nginx Gateway (`16-acquire-dast-session.envsh`).
- **Nằm ở đâu trong luồng:** Bước tiền đề trước khi triển khai Task 2 (Gateway giữ session DAST).
- **Không có nó thì hỏng gì:** Nếu giả định sai về `wget` trong image `nginx:1.27-alpine`, Gateway DAST sẽ không lấy được session hoặc phải cài thêm package không cần thiết làm phình image và tăng bề mặt tấn công.
- **Ngoài phạm vi (cố ý không làm):** Không chỉnh sửa code Gateway hay Dockerfile trong task này (được thực hiện ở Task 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `worklog/2026-08-22-dast-verify-session-bootstrap.md` | Tạo | Ghi lại kết quả thực nghiệm lệnh wget, trích xuất cookie và quyết định kỹ thuật | Báo cáo bắt buộc của Task 1 |

**`git diff --stat`:**

```text
 0 files changed
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Chạy lệnh bên trong container `gateway` (image `nginx:1.27-alpine`) trên cùng mạng Docker với `webgoat:8080`.
Gửi request `POST /WebGoat/register.mvc` bằng `wget -S` và phân tích luồng header trả về.

**Luồng dữ liệu:**
`POST /WebGoat/register.mvc` $\rightarrow$ `HTTP 302 Found` (kèm `Set-Cookie: JSESSIONID=...`) $\rightarrow$ Trích xuất `JSESSIONID` từ header đầu tiên bằng `sed` $\rightarrow$ Thử nghiệm `GET /WebGoat/start.mvc` với header `Cookie: JSESSIONID=...` $\rightarrow$ `HTTP 200 OK` (nội dung trang WebGoat thật).

**Các quyết định kỹ thuật:**
- **Quyết định wget vs curl:** Dùng busybox `wget` có sẵn trong `nginx:1.27-alpine`. Không cần cài thêm `curl`.
- **Xử lý redirect:** Do busybox `wget` tự động đi theo 302 mà không gửi kèm Cookie ở hop sau, việc gọi register sinh ra chuỗi redirect lặp. Tuy nhiên, `Set-Cookie` của hop đầu tiên chứa đúng session hợp lệ, do đó chỉ cần lấy dòng `Set-Cookie` đầu tiên (`head -n 1`).

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Thực nghiệm | Bootstrap session lệnh wget | Terminal command | Lệnh trích xuất JSESSIONID và xác thực với WebGoat |

**Cách chạy lệnh kiểm chứng:**

```bash
docker compose --profile target run --rm --no-deps --entrypoint sh gateway -c '
  RAW=$(wget -S -O /dev/null --post-data="username=sentinel-probe10&password=sent1nel&matchingPassword=sent1nel&agree=agree" http://webgoat:8080/WebGoat/register.mvc 2>&1)
  COOKIE=$(echo "$RAW" | grep -i "Set-Cookie:.*JSESSIONID=" | head -n 1 | sed -n "s/.*JSESSIONID=\([^;]*\).*/\1/p" | tr -d "\r\n")
  echo "Extracted: $COOKIE"
  wget -S -O - --header="Cookie: JSESSIONID=$COOKIE" http://webgoat:8080/WebGoat/start.mvc 2>&1 | head -n 25
'
```

**Output thật (đã che secret):**

```text
Extracted: ***
Connecting to webgoat:8080 (172.18.0.2:8080)
  HTTP/1.1 200 
  Content-Type: text/html;charset=UTF-8
  Content-Language: en-US
  Transfer-Encoding: chunked
  Date: Sat, 22 Aug 2026 03:39:05 GMT
  Connection: close
  
writing to stdout
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Expires" CONTENT="-1"/>
    <meta http-equiv="Pragma" CONTENT="no-cache"/>
    <meta http-equiv="Cache-Control" CONTENT="no-cache"/>
    <meta http-equiv="Cache-Control" CONTENT="no-store"/>

    <!--  CSS -->
    <link rel="shortcut icon" href="/WebGoat/css/img/favicon.ico" type="image/x-icon"/>

    <link rel="stylesheet" type="text/css" href="/WebGoat/css/main.css"/>
    <link rel="stylesheet" type="text/css" href="/WebGoat/plugins/bootstrap/css/bootstrap.min.css"/>
    <link rel="stylesheet" type="text/css" href="/WebGoat/css/font-awesome.min.css"/>
    <link rel="stylesheet" type="text/css" href="/WebGoat/css/animate.css"/>
    <link rel="stylesheet" type="text/css" href="/WebGoat/css/coderay.css"/>
```

**Mốc so sánh bề mặt quét ẩn danh (Step 4):**
- Số lượng URL quét ẩn danh trước đây (`worklog/2026-08-22-zap-dast-through-gateway.md`): **19 URL**.
- Mục tiêu Task 3 khi có phiên đăng nhập: Số URL spider được phải lớn hơn 19 đáng kể.

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Sử dụng busybox `wget` với `grep -i "Set-Cookie:.*JSESSIONID=" | head -n 1`.

**Lý do:**
- `nginx:1.27-alpine` đã có sẵn busybox `wget`, không cần chạy `apk add curl` làm tăng kích thước Docker image và phụ thuộc mạng ngoài lúc build.
- Lệnh chạy ổn định và trích xuất đúng `JSESSIONID` 32 ký tự hex.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Cài `curl` vào Dockerfile Gateway | `curl -s -c cookie.txt` quản lý cookie jar tự động | Tăng kích thước image và phụ thuộc mạng ngoài không cần thiết khi `wget` hoàn toàn đáp ứng được |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `docker compose --profile target run ... (wget register & start.mvc)` | 0 | HTTP 200 OK, trả về dashboard WebGoat |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 852 passed, 38 deselected |

**Bất biến đã giữ:**
- Không sửa code sản phẩm ngoài phạm vi Task 1.
- Không in giá trị JSESSIONID thật ra log/worklog (`***`).
- Mốc nền 852 tests passed được bảo toàn.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có (lệnh thực nghiệm đã chạy thành công 100% trong container thật).
- **Giả định đã đặt:** WebGoat giữ nguyên username/password đăng ký mặc định (`sentinel-probe*` / `sent1nel`).
- **Việc còn nợ:** Triển khai script `16-acquire-dast-session.envsh` trong Task 2.
