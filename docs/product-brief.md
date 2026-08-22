# Project Sentinel — Bản mô tả sản phẩm

## Vấn đề

Một lần quét SAST trên codebase cỡ vừa sinh ra hàng trăm cảnh báo. Phần lớn là
trùng lặp hoặc dương tính giả, và mỗi cảnh báo chỉ là một dòng mã cùng tên luật.
Kỹ sư bảo mật mất phần lớn thời gian để **phân loại**, chứ không phải để sửa.
Việc xác minh một cảnh báo có thật hay không lại đòi gửi request tới ứng dụng —
một thao tác rủi ro nếu không có rào chắn.

## Người sử dụng

Kỹ sư bảo mật ứng dụng và kỹ sư DevSecOps trong đội sản phẩm, những người phải
đọc kết quả quét sau mỗi lần CI chạy và quyết định cảnh báo nào đáng xử lý.

## Giá trị

Sentinel nhóm các cảnh báo trùng nhau, giải thích từng lỗ hổng bằng ngôn ngữ dễ
hiểu **kèm trích dẫn bằng chứng từ chính công cụ quét**, và đề xuất một request
kiểm chứng an toàn. Đề xuất đó không tự chạy: nó bị kẹp bởi allowlist endpoint và
phải được con người bấm duyệt. Response trả về bị lọc prompt injection và che dữ
liệu nhạy cảm trước khi quay lại agent.

Điểm khác biệt không nằm ở việc dùng LLM, mà ở chỗ **đầu ra của LLM được coi là
dữ liệu không đáng tin và bị chặn bởi các lớp kiểm tra tất định**.

## Phạm vi

Phạm vi hiện tại là một môi trường thử nghiệm chạy bằng Docker Compose, với
OWASP WebGoat làm ứng dụng đích cố định. Hệ thống chạy một công cụ SAST
(OpenGrep), một công cụ DAST (OWASP ZAP Baseline) quét qua một lane Gateway nội
bộ riêng, một AI Agent phân tích cả hai nguồn finding, và một API Gateway kiểm
soát mọi request kiểm thử. Kho tri thức gồm 20 tài liệu về OWASP Top 10 và các
lỗ hổng web phổ biến, tìm kiếm bằng từ khoá.

## Hạn chế

Xem [`limitations.md`](limitations.md) để biết đầy đủ. Tóm tắt: một agent duy
nhất, không multi-agent; tìm kiếm bằng từ khoá chứ không phải semantic search;
target cố định, không trỏ được vào repo tuỳ ý; bộ đánh giá chỉ sáu ca; chỉ hỗ
trợ GET và POST với bốn loại payload lành tính.

## Hướng phát triển

Theo thứ tự giá trị giảm dần: mở rộng bộ đánh giá lên vài chục ca để đo được độ
chính xác một cách có ý nghĩa; cho ZAP chạy AJAX spider để chạm được các bài học
WebGoat nạp bằng JavaScript, vì bản Baseline hiện tại chỉ thấy phần vỏ tĩnh; thay
tìm kiếm từ khoá bằng semantic search để kho tri thức mở rộng được; và cho phép
cấu hình nhiều ứng dụng đích thay vì cố định một.

DAST bằng OWASP ZAP trước đây nằm trong danh sách này và đã hoàn thành.
