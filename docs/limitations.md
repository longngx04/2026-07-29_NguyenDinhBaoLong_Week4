# Hạn chế và rủi ro bảo mật còn tồn tại

## Rủi ro bảo mật còn tồn tại

**WebGoat là ứng dụng cố ý chứa lỗ hổng.** Nó chỉ được phép chạy trong mạng nội
bộ của Docker Compose. `docker-compose.yml` không khai báo `ports` cho nó; chỉ
lane Agent của Gateway bind cổng loopback `127.0.0.1:9080`, còn lane DAST là nội bộ. Sửa cấu hình
mạng để mở WebGoat ra `0.0.0.0` là đưa một ứng dụng có lỗ hổng đã biết lên mạng.
Có test khoá bất biến này (`tests/unit/infra/test_compose_invariants.py`).

**Bộ phát hiện prompt injection dựa trên mẫu.** Nó bắt được các dạng phổ biến đã
liệt kê, nhưng không phải là hàng rào đầy đủ — kỹ thuật diễn đạt lại hoặc mã hoá
đều có thể vượt qua. Lớp phòng thủ thật sự nằm ở chỗ khác: đầu ra của agent bị
kẹp bởi allowlist, và mọi request rủi ro cần con người bấm duyệt. Bộ phát hiện là
lớp thứ hai, không phải lớp duy nhất.

**Bộ che dữ liệu nhạy cảm dựa trên biểu thức chính quy.** Nó bắt email, số điện
thoại, JWT, khoá API, mật khẩu và một số dạng số định danh. Dữ liệu nhạy cảm ở
định dạng lạ có thể lọt. Bộ che đặt ở hai nút thắt cổ chai — mọi prompt gửi tới
LLM và mọi lệnh ghi log — nên không có đường vòng, nhưng độ phủ vẫn giới hạn ở
các mẫu đã biết.

**Khoá Gateway nằm trong biến môi trường.** Không có hệ thống quản lý bí mật.
Với môi trường thử nghiệm thì chấp nhận được; đưa lên production thì không.

**Chưa kiểm chứng độc lập đầu ra của LLM.** Có kiểm tra schema và kiểm tra nguồn
gốc chống bịa finding ID, vị trí, CWE và OWASP, nhưng phần giải thích bằng văn
xuôi thì không có cách xác minh tự động.

## Hạn chế chức năng

- Một agent duy nhất; không có multi-agent, không MCP/A2A.
- Tìm kiếm kho tri thức bằng từ khoá, không phải semantic search hay RAG.
- Ứng dụng đích cố định là WebGoat; không trỏ được vào repo tuỳ ý. Đây là quyết
  định có chủ ý: cho người dùng chỉ vào mã nguồn bất kỳ sẽ mở ra bề mặt chạy mã
  tuỳ ý ngay trong một công cụ bảo mật.
- Chỉ hỗ trợ GET và POST, với đúng bốn loại payload lành tính. Không có payload
  khai thác thật.
- DAST chỉ chạy baseline (spider + passive scan), không active scan. Nó chứng
  minh được một endpoint tồn tại và chạm tới được, nhưng không chứng minh được
  kẻ tấn công kiểm soát được dữ liệu tới sink. `confirmed` vì thế vẫn ngoài tầm.
- Phiên WebGoat do Gateway giữ và dùng chung cho cả lần quét. Một phiên duy
  nhất không phát hiện được lỗ hổng phụ thuộc nhiều tài khoản (IDOR giữa hai
  người dùng).
- Đối chiếu SAST ↔ DAST dựa trên annotation route của Spring. Endpoint đăng ký
  theo cách khác (cấu hình động, router tuỳ biến) sẽ nhận `no_route`.
  Trên dữ liệu thực tế của 23 finding SAST WebGoat, kết quả đối chiếu đo được là
  `{'no_route': 4, 'reachable': 17, 'route_known_not_reached': 2}`.
  17 finding SAST đạt `reachable` nhờ lane DAST Automation Framework gửi request POST
  chính tắc theo allowlist đã review. 2 finding còn lại ở `route_known_not_reached` là do
  path template động hoặc endpoint chưa đưa vào allowlist.
- Lane DAST gửi được POST tới một danh sách endpoint đã review trong
  `configs/gateway/dast-allowlist.json`. Body là hằng số do Gateway quyết định,
  không phải do ZAP chọn — ZAP chỉ nêu path. Mỗi mục trong danh sách đó là một
  request thật vào một ứng dụng cố ý có lỗ hổng, và cổng bảo vệ duy nhất là
  người đọc `@RequestParam` rồi chọn body làm ít nhất có thể.
- Body chính tắc gắn với `webgoat:v2025.3`. Nâng WebGoat lên bản khác có thể đổi
  tên tham số; lúc đó POST vẫn trả 2xx nhưng không còn chứng minh điều gì. Test
  trích dẫn dòng nguồn bắt được nếu file đổi, **không** bắt được nếu chỉ tên
  tham số đổi.
- `reachable` nghĩa là endpoint tồn tại và chạm tới được, **không** nghĩa là lỗ
  hổng đã được chứng minh. `attacker_control` vẫn `not_proven`, nên `confirmed`
  vẫn ngoài tầm với.
- Bản đồ endpoint đọc từ Nginx access log, mà log ghi `path=$uri` — path đã
  chuẩn hoá. Tham số lấy từ `query=$args`, nên tham số gửi trong body (được thay
  bằng body chính tắc của lane tại Gateway) không nằm trong URL query.

- Bộ đánh giá có **11 ca** — đủ để bắt hồi quy, chưa đủ để công bố số liệu độ
  chính xác. Chúng tôi tránh over-claim về độ chính xác tuyệt đối của mô hình khi
  chưa có tập mẫu thử nghiệm quy mô lớn.
- **`make eval` cho 10/11, không phải 11/11.** Ca `01-sql-injection` yêu cầu
  severity `high`, còn model lúc trả `high` lúc trả `medium` cho cùng một input —
  đã quan sát ở ba lần chạy liên tiếp. Đây là dao động của model, không phải hồi
  quy của hệ thống, và nó chính là lý do năm ca thêm vào sau này nhắm vào bảo đảm
  tất định (ví dụ "record không được chứa payload khai thác") thay vì phán đoán
  của model.
- Một phần nhóm finding không bao giờ ra được record. Phản hồi của model bị
  loại vì vi phạm schema, provenance hoặc lọc nội dung không an toàn, và sau một
  lần thử lại vẫn hỏng thì cả nhóm bị bỏ. Lần chạy `20260822T094343Z` đo được
  **33/37 nhóm** ra record; 4 nhóm còn lại biến mất. `analysis-summary.json` ghi
  chúng trong `missing_group_keys` và nêu lý do trong `unresolved_group_reasons`,
  và `completeness` của lần chạy đó là `PARTIAL` chứ không phải `COMPLETE`.
- Bước `analyze` chiếm gần như toàn bộ thời gian một lần chạy: 369 s trên tổng
  hơn 400 s ở lần đo trên, với 44 lời gọi LLM cho 37 nhóm. Đây là giới hạn thông
  lượng, không phải giới hạn đúng/sai.
- **Override thủ công của người vận hành chỉ dùng được với POST.**
  `cli run --probe-method GET --probe-path /WebGoat/login` bị từ chối với lý do
  `payload_kind 'empty_value' chưa được review cho 'GET /WebGoat/login'`, và
  không request nào được gửi. Nguyên nhân: `--probe-payload-kind` mặc định
  `empty_value`, trong khi lane probe chặn cả body lẫn query string trên GET nên
  không template GET nào nhận payload. Bản thân `GET /WebGoat/login` **trơn** thì
  Gateway trả 200 — chỉ là CLI không có cách khai "không payload".
- **Bảy test live của lane DAST không chạy trong CI.** CI chạy 84 test tĩnh liên
  quan DAST (chính sách lane, allowlist, requestor plan, normalizer, correlation),
  nhưng bảy test cần container thật — gồm test canary chứng minh ZAP không gửi
  được body tới WebGoat — chỉ chạy khi gõ `make dast-test` bằng tay.
- Chỉ chạy được một lần quét tại một thời điểm; không có hàng đợi công việc.

