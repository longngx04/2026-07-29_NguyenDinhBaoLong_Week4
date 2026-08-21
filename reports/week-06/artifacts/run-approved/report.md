# Báo cáo bảo mật — lần chạy `20260821T130658Z`

## Tổng quan

- Trạng thái: **DONE**
- Cảnh báo thô: **23**
- Nhóm sau phân tích: **21**
- Mức nghiêm trọng: {'medium': 11, 'high': 10}
- Kết luận của Agent: {'likely': 13, 'confirmed': 5, 'needs_review': 3}
- Người phê duyệt: cli-operator
> **Phân tích KHÔNG trọn vẹn (`PARTIAL`).** 2 nhóm hợp lệ không sinh được record: `group-e46b371f0d`, `group-beea6607a4`. Những finding trong các nhóm đó KHÔNG có mặt trong báo cáo này.
> Hệ thống đã hạ mức hoặc hạ kết luận của **3** phát hiện vì bằng chứng không đủ. Chi tiết ở từng mục bên dưới.
- Lời gọi LLM: 28 (2 phản hồi không hợp lệ)

## Phát hiện

### Command Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/dummy/insecure/framework/VulnerableTaskHolder.java:69
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức readObject thực thi lệnh hệ thống thông qua Runtime.exec với chuỗi taskAction được đọc từ dữ liệu serialized. Dù có kiểm tra.startsWith và độ dài, việc nối chuỗi lệnh mà không tách tham số rõ ràng vẫn có thể dẫn đến thực thi lệnh tùy ý nếu attacker lách được điều kiện.
- Khắc phục: Sử dụng ProcessBuilder với danh sách tham số rõ ràng thay vì chuỗi lệnh; Áp dụng danh sách trắng (allowlist) cho các lệnh được phép thực thi; Tránh thực thi lệnh hệ thống với dữ liệu do người dùng kiểm soát
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/lessons/LessonConnectionInvocationHandler.java:31
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 31 thực hiện nối chuỗi trực tiếp giữa chuỗi cố định và tên người dùng để thiết lập schema trong cơ sở dữ liệu. Vì tên người dùng có thể do người dùng kiểm soát, việc này có thể dẫn đến SQL injection nếu không được kiểm tra hoặc lọc ký tự đặc biệt.
- Khắc phục: Sử dụng cơ chế thiết lập schema an toàn do hệ quản trị CSDL cung cấp thay vì nối chuỗi; Lọc hoặc kiểm tra tên người dùng để đảm bảo chỉ chứa ký tự hợp lệ cho tên schema

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/users/UserService.java:57
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lệnh SQL tại dòng 57 sử dụng nối chuỗi trực tiếp với tên người dùng để tạo câu lệnh CREATE SCHEMA. Nếu tên người dùng không được kiểm tra hoặc làm sạch, kẻ tấn công có thể chèn ký tự đặc biệt để thay đổi hành vi của câu lệnh SQL, dẫn đến SQL injection.
- Khắc phục: Sử dụng truy vấn tham số hóa hoặc API an toàn để xây dựng tên schema; Xác thực và lọc tên người dùng chỉ cho phép các ký tự chữ và số; Giới hạn đặc quyền của tài khoản cơ sở dữ liệu để ngăn thực thi lệnh nguy hiểm

### Deserialization không an toàn — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/InsecureDeserializationTask.java:45
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực hiện deserialize đối tượng từ chuỗi Base64 do người dùng cung cấp thông qua tham số 'token', sử dụng ObjectInputStream.readObject() mà không có cơ chế xác thực hoặc lọc đối tượng. Đây là hành vi đặc trưng của lỗ hổng deserialization không an toàn, có thể dẫn đến thực thi mã từ xa nếu kẻ tấn công cung cấp payload gadget chain phù hợp.
- Khắc phục: Sử dụng ObjectInputFilter để giới hạn các lớp được phép deserialize; Thay thế serialization bằng định dạng an toàn hơn như JSON với schema rõ ràng; Xác thực tính toàn vẹn của dữ liệu trước khi deserialize, ví dụ bằng chữ ký số

### Insecure Deserialization — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/SerializationHelper.java:23
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức fromString thực hiện deserialize một đối tượng từ chuỗi Base64 mà không xác thực hoặc kiểm soát nội dung. Đây là điểm nguy hiểm vì nếu kẻ tấn công cung cấp một chuỗi serialized độc hại, có thể kích hoạt chuỗi gadget dẫn đến thực thi mã từ xa (RCE).
- Khắc phục: Sử dụng cơ chế xác thực hoặc ký dữ liệu serialized trước khi deserialize; Thay thế bằng định dạng dữ liệu an toàn như JSON với kiểm tra kiểu nghiêm ngặt; Sử dụng thư viện an toàn như Jackson hoặc Gson thay vì Java Serialization; Triển khai kiểm tra white-list cho các lớp được phép deserialize
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/jwt/claimmisuse/JWTHeaderKIDEndpoint.java:73
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lệnh SQL được xây dựng bằng cách nối trực tiếp giá trị từ `header.get("kid")` vào chuỗi truy vấn. Vì `kid` đến từ header của JWT do người dùng cung cấp, nó có thể bị kiểm soát bởi kẻ tấn công nếu họ tạo token hợp lệ. Việc sử dụng `Statement.executeQuery` với chuỗi nối làm tăng nguy cơ SQL injection.
- Khắc phục: Sử dụng prepared statement với tham số hóa thay vì nối chuỗi SQL; Giới hạn kích thước và ký tự hợp lệ cho trường `kid`; Xác thực và làm sạch tất cả các claim từ JWT trước khi sử dụng

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionChallenge.java:57
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Ứng dụng xây dựng truy vấn SQL bằng cách nối trực tiếp tham số `username` từ request vào chuỗi truy vấn. Điều này có thể cho phép kẻ tấn công chèn mã SQL độc hại nếu đầu vào không được kiểm tra đầy đủ.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi vào truy vấn SQL; Áp dụng kiểm tra và làm sạch đầu vào nghiêm ngặt cho tất cả tham số từ người dùng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionLesson6a.java:72
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lỗ hổng SQL Injection xảy ra khi tham số người dùng được nối trực tiếp vào chuỗi truy vấn SQL mà không được xử lý an toàn. Dòng 72 tạo truy vấn bằng cách nối trực tiếp `accountName` vào câu lệnh SELECT, cho phép kẻ tấn công chèn thêm mệnh đề SQL nếu không được kiểm soát.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi.; Áp dụng kiểm tra và làm sạch đầu vào nghiêm ngặt hơn, không chỉ dựa vào kiểm tra UNION.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:56
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra khi tham số người dùng 'action' được nối trực tiếp vào chuỗi truy vấn SQL mà không được kiểm tra hay tham số hóa. Điều này cho phép kẻ tấn công ti внjection mã SQL độc hại thông qua tham số 'action_string' trong yêu cầu POST.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu; Triển khai kiểm tra và lọc đầu vào nghiêm ngặt; Ghi log và giám sát các truy vấn bất thường

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:100
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Phương thức tableExists thực hiện một truy vấn SQL cố định để kiểm tra sự tồn tại của bảng access_log. Truy vấn là một chuỗi tĩnh, không có sự nối chuỗi với dữ liệu do người dùng cung cấp. Do đó, không có nguy cơ SQL Injection tại điểm này.
- Khắc phục: Sử dụng truy vấn tham số hóa hoặc PreparedStatement ngay cả với truy vấn đơn giản để đảm bảo an toàn nhất quán.; Kiểm tra và xác minh rằng không có luồng nào cho phép điều khiển kết nối hoặc ngữ cảnh thực thi từ đầu vào người dùng.
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: severity_ceiling_for_disposition)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson2.java:49
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng nhận tham số 'query' từ request HTTP POST và truyền trực tiếp vào phương thức executeQuery của đối tượng Statement, cho phép kẻ tấn công thực thi truy vấn SQL tùy ý. Đây là lỗ hổng SQL Injection do không sử dụng PreparedStatement hoặc tham số hóa truy vấn.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi truy vấn; Giới hạn quyền của tài khoản cơ sở dữ liệu mà ứng dụng sử dụng; Thực hiện xác thực và lọc đầu vào nghiêm ngặt đối với tham số 'query'

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:47
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực thi truy vấn SQL động bằng cách nối trực tiếp chuỗi từ tham số request vào câu lệnh SQL thông qua statement.executeUpdate(query). Điều này cho phép kẻ tấn công tiêm mã SQL độc hại nếu không có biện pháp bảo vệ nào khác.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi SQL; Áp dụng nguyên tắc đặc quyền tối thiểu cho kết nối cơ sở dữ liệu; Giới hạn loại truy vấn mà người dùng có thể thực thi; Xác thực và lọc đầu vào theo danh sách cho phép (allowlist)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:49
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Tham số 'query' từ request được truyền trực tiếp vào phương thức executeUpdate mà không được xử lý hoặc tham số hóa, tạo điều kiện cho tấn công SQL injection nếu đầu vào không được kiểm tra.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn; Giới hạn quyền của tài khoản cơ sở dữ liệu để ngăn thực thi lệnh DDL/DML không mong muốn; Xác thực và lọc đầu vào người dùng trước khi sử dụng trong truy vấn

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson4.java:46
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực thi trực tiếp chuỗi truy vấn SQL do người dùng cung cấp thông qua tham số 'query' mà không kiểm tra hay lọc đầu vào, dẫn đến nguy cơ SQL Injection.
- Khắc phục: Sử dụng PreparedStatement thay vì Statement để ngăn chặn SQL Injection; Áp dụng kiểm tra và lọc đầu vào nghiêm ngặt cho tất cả các tham số người dùng; Triển khai nguyên tắc đặc quyền tối thiểu cho kết nối cơ sở dữ liệu

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson4.java:48
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Ứng dụng thực thi một truy vấn SQL động được cung cấp trực tiếp từ tham số `query` của người dùng mà không được kiểm tra hay tham số hóa. Điều này tạo điều kiện cho tấn công SQL injection nếu đầu vào không được xử lý đúng cách.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi vào truy vấn SQL; Giới hạn quyền của kết nối cơ sở dữ liệu để ngăn thực thi lệnh không mong muốn; Xác thực và lọc đầu vào người dùng theo danh sách cho phép (allowlist)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson5a.java:52
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra khi chuỗi truy vấn được xây dựng bằng cách nối trực tiếp dữ liệu do người dùng cung cấp vào câu lệnh SQL. Trong đoạn mã, biến accountName (được tạo từ các tham số request) được nối trực tiếp vào chuỗi truy vấn mà không được kiểm tra hay tham số hóa, cho phép kẻ tấn công thay đổi logic truy vấn.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu; Kiểm tra và lọc đầu vào theo danh sách cho phép (allowlist)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson8.java:62
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Ứng dụng xây dựng truy vấn SQL bằng cách nối trực tiếp hai tham số từ request (name và auth_tan) vào chuỗi truy vấn. Việc này tạo điều kiện cho tấn công SQL Injection nếu đầu vào không được kiểm tra hoặc lọc.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi; Áp dụng kiểm tra và làm sạch đầu vào nghiêm ngặt; Giới hạn quyền truy cập cơ sở dữ liệu của ứng dụng theo nguyên tắc tối thiểu

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson8.java:142
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Đoạn mã xây dựng truy vấn SQL bằng cách nối trực tiếp giá trị từ tham số 'action' vào chuỗi truy vấn. Đây là hành vi nguy hiểm và có thể dẫn đến SQL Injection nếu 'action' chứa dữ liệu do người dùng cung cấp. Mặc dù có thực hiện thay thế ký tự nháy đơn, việc này không đủ để ngăn chặn các kỹ thuật khai thác nâng cao.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu; Kiểm tra và xác thực đầu vào trước khi sử dụng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:65
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra khi dữ liệu người dùng được nối trực tiếp vào câu lệnh SQL mà không được kiểm tra hoặc tham số hóa. Trong đoạn mã này, hai tham số `name` và `auth_tan` từ request được ghép nối trực tiếp vào chuỗi truy vấn, cho phép kẻ tấn công thay đổi logic truy vấn bằng cách cung cấp đầu vào độc hại.
- Khắc phục: Sử dụng truy vấn tham số hóa (Prepared Statements) thay vì nối chuỗi; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu; Kiểm tra và làm sạch đầu vào theo danh sách cho phép (allowlist) nếu cần thiết; Ghi log và giám sát các truy vấn bất thường

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:94
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Tất cả các câu lệnh SQL được thực thi thông qua `executeQuery` đều sử dụng chuỗi truy vấn cố định, không có sự nối ghép với bất kỳ biến nào đến từ đầu vào người dùng. Các giá trị như '3SL99A' là hằng số được viết cứng trong mã nguồn.
- Khắc phục: Sử dụng prepared statements với tham số hóa nếu cần xử lý đầu vào động trong truy vấn SQL.; Giữ nguyên việc sử dụng truy vấn tĩnh nếu logic ứng dụng không yêu cầu điều kiện động.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:117
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng 117 gọi statement.executeQuery(query) với một chuỗi truy vấn được định nghĩa cứng, không có dữ liệu từ người dùng được nối vào. Do đó, không có lỗ hổng SQL Injection rõ ràng tại vị trí này.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa truy vấn nếu cần đưa dữ liệu người dùng vào truy vấn SQL.; Tránh nối chuỗi trực tiếp vào truy vấn SQL.

## Kiểm chứng

- Agent đề xuất: `GET /WebGoat/login`
- Kết quả qua Gateway: HTTP **200** trong 6.85ms
- Finding được nhắm tới: `analysis-0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d` (opengrep-002)
- **Kết luận kiểm chứng: `inconclusive`** — Endpoint `/WebGoat/login` không nằm trong bằng chứng của finding `analysis-0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d`, nên mã trạng thái trả về không nói gì về lỗ hổng đó.

## Sự kiện bảo mật

- `approval`: 1
