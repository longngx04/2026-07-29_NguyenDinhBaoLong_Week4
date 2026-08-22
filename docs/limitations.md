# Hạn chế và rủi ro bảo mật còn tồn tại

## Rủi ro bảo mật còn tồn tại

**WebGoat là ứng dụng cố ý chứa lỗ hổng.** Nó chỉ được phép chạy trong mạng nội
bộ của Docker Compose. `docker-compose.yml` không khai báo `ports` cho nó, và
Gateway là thành phần duy nhất bind cổng loopback `127.0.0.1:9080`. Sửa cấu hình
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
- Bộ đánh giá chỉ sáu ca — đủ để bắt hồi quy, chưa đủ để công bố số liệu độ
  chính xác. Độ chính xác có sự dao động giữa các lần chạy mô hình và khoảng đo được
  thực tế cần được đối chiếu thận trọng. Chúng tôi tránh over-claim về độ chính xác
  tuyệt đối của mô hình khi chưa có tập mẫu thử nghiệm quy mô lớn.
- Chỉ chạy được một lần quét tại một thời điểm; không có hàng đợi công việc.
