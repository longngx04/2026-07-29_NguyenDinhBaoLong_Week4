# Báo cáo bảo mật — lần chạy `20260821T131547Z`

## Tổng quan

- Trạng thái: **REJECTED**
- Cảnh báo thô: **23**
- Nhóm sau phân tích: **18**
- Mức nghiêm trọng: {'medium': 9, 'high': 9}
- Kết luận của Agent: {'likely': 14, 'needs_review': 3, 'confirmed': 1}
- Người phê duyệt: (không có bước phê duyệt)
> **Phân tích KHÔNG trọn vẹn (`PARTIAL`).** 5 nhóm hợp lệ không sinh được record: `group-39188bb86d`, `group-e46b371f0d`, `group-f260266d28`, `group-77bf8cb561`, `group-c5e03ea132`. Những finding trong các nhóm đó KHÔNG có mặt trong báo cáo này.
> Hệ thống đã hạ mức hoặc hạ kết luận của **5** phát hiện vì bằng chứng không đủ. Chi tiết ở từng mục bên dưới.
- Lời gọi LLM: 30 (5 phản hồi không hợp lệ)

## Phát hiện

### Command Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/dummy/insecure/framework/VulnerableTaskHolder.java:69
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức readObject thực hiện deserialize dữ liệu từ đầu vào không đáng tin cậy. Biến taskAction được đọc từ luồng deserialize và dùng trực tiếp trong Runtime.exec() mà không được kiểm tra kỹ lưỡng, chỉ giới hạn bằng chuỗi bắt đầu và độ dài. Điều này có thể dẫn đến thực thi lệnh hệ thống nếu attacker kiểm soát được nội dung serialized.
- Khắc phục: Tránh sử dụng Runtime.exec với dữ liệu không đáng tin cậy; Sử dụng ProcessBuilder với danh sách tham số rõ ràng thay vì chuỗi lệnh; Áp dụng allowlist cho các lệnh được phép thực thi; Xem xét loại bỏ chức năng thực thi lệnh từ serialized object
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/lessons/LessonConnectionInvocationHandler.java:31
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 31 thực hiện nối chuỗi tên người dùng vào truy vấn SQL SET SCHEMA mà không sử dụng truy vấn tham số hóa. Nếu tên người dùng chứa ký tự đặc biệt, có thể dẫn đến thay đổi hành vi truy vấn.
- Khắc phục: Sử dụng truy vấn tham số hóa hoặc kiểm tra tên schema trước khi sử dụng; Giới hạn ký tự trong username để tránh ký tự đặc biệt
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/users/UserService.java:57
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 57 thực thi một câu lệnh SQL động bằng cách nối trực tiếp tên người dùng vào câu lệnh CREATE SCHEMA. Đây là hành vi nguy hiểm vì nếu tên người dùng chứa ký tự đặc biệt hoặc được kiểm soát bởi kẻ tấn công, có thể dẫn đến thay đổi cấu trúc cơ sở dữ liệu. Tuy nhiên, trong ngữ cảnh này, tên người dùng được tạo từ phương thức `addUser`, vốn được gọi khi thêm người dùng mới, nên cần xác minh thêm về mức độ kiểm soát đầu vào.
- Khắc phục: Sử dụng tên người dùng đã được làm sạch (sanitized) hoặc ánh xạ sang định danh an toàn trước khi dùng trong SQL; Tránh nối trực tiếp dữ liệu người dùng vào câu lệnh SQL, kể cả trong lệnh DDL; Áp dụng allowlist cho tên người dùng: chỉ cho phép chữ cái, số và dấu gạch dưới
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### Insecure Deserialization — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/InsecureDeserializationTask.java:45
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực hiện deserialization không an toàn bằng cách sử dụng ObjectInputStream.readObject() trên dữ liệu được mã hóa Base64 từ tham số 'token' do người dùng cung cấp. Nếu dữ liệu này không được xác thực, kẻ tấn công có thể gửi một chuỗi byte được tạo sẵn (gadget chain) để thực thi mã từ xa hoặc gây ra các hành vi không mong muốn.
- Khắc phục: Sử dụng cơ chế xác thực chữ ký số để đảm bảo dữ liệu deserialization đến từ nguồn tin cậy; Thay thế ObjectInputStream bằng các cơ chế serialization an toàn hơn như JSON hoặc XML với schema xác định; Áp dụng white-listing cho các lớp được phép deserialization; Cập nhật và sử dụng các thư viện như Apache Commons IO với kiểm soát nghiêm ngặt hơn đối với deserialization

### Insecure Deserialization — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/SerializationHelper.java:23
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức fromString thực hiện deserialization bằng ObjectInputStream.readObject() trên dữ liệu được giải mã từ Base64 mà không xác thực loại đối tượng. Nếu chuỗi đầu vào đến từ người dùng, kẻ tấn công có thể gửi payload serialized độc hại để khai thác gadget chain, dẫn đến thực thi mã từ xa.
- Khắc phục: Sử dụng cơ chế xác thực trước khi deserialization, ví dụ kiểm tra chữ ký hoặc token; Thay thế bằng serialization an toàn hơn như JSON với schema rõ ràng; Nếu bắt buộc dùng Java serialization, áp dụng danh sách trắng lớp được phép deserialization
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/jwt/claimmisuse/JWTHeaderKIDEndpoint.java:73
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 73 thực hiện truy vấn SQL bằng cách nối trực tiếp giá trị từ `header.get("kid")` vào chuỗi truy vấn. Biến `kid` bắt nguồn từ header của JWT do người dùng cung cấp qua tham số `token`. Việc này tạo điều kiện cho SQL injection nếu không được kiểm soát.
- Khắc phục: Sử dụng truy vấn tham số hóa hoặc PreparedStatement thay vì nối chuỗi; Giới hạn giá trị kid bằng danh sách cho phép (allowlist); Xác thực và làm sạch giá trị kid trước khi sử dụng trong truy vấn

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionChallenge.java:57
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Truy vấn SQL tại dòng 57 được xây dựng bằng cách nối trực tiếp giá trị `username` từ tham số request vào chuỗi truy vấn. Điều này tạo điều kiện cho tấn công SQL Injection nếu đầu vào không được kiểm tra hoặc lọc kỹ.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi vào truy vấn SQL; Áp dụng kiểm tra và làm sạch đầu vào nghiêm ngặt cho tất cả tham số người dùng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:56
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lệnh SQL được xây dựng bằng cách nối trực tiếp tham số `action` vào chuỗi truy vấn mà không sử dụng truy vấn tham số hóa. Điều này tạo điều kiện cho tấn công SQL injection nếu đầu vào không được kiểm tra và lọc kỹ.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL; Áp dụng kiểm tra và làm sạch dữ liệu đầu vào nghiêm ngặt; Giới hạn quyền truy cập cơ sở dữ liệu theo nguyên tắc tối thiểu

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:100
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng mã tại vị trí báo lỗi (dòng 100) không nằm trong đoạn mã được cung cấp. Đoạn mã hiện tại chỉ bao gồm xử lý ngoại lệ và phương thức kiểm tra sự tồn tại của bảng 'access_log' bằng truy vấn tĩnh. Không có bằng chứng cho thấy dữ liệu người dùng được nối trực tiếp vào truy vấn SQL.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu của ứng dụng; Kiểm tra và xác thực tất cả dữ liệu đầu vào trước khi sử dụng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson2.java:49
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực thi truy vấn SQL với chuỗi do người dùng cung cấp thông qua tham số 'query' mà không sử dụng truy vấn tham số hóa hay bộ lọc đầu vào, dẫn đến nguy cơ SQL Injection.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi trong truy vấn SQL; Giới hạn quyền của tài khoản cơ sở dữ liệu mà ứng dụng sử dụng; Xác thực và làm sạch đầu vào theo danh sách cho phép (allowlist) nếu cho phép truy vấn tùy chỉnh

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:47
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Câu lệnh SQL được thực thi bằng statement.executeUpdate(query), trong đó query là tham số đầu vào từ người dùng mà không được kiểm tra hay xử lý. Điều này tạo điều kiện cho tấn công SQL Injection nếu đầu vào không được kiểm soát.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL; Áp dụng kiểm tra và lọc đầu vào nghiêm ngặt đối với tất cả các tham số từ người dùng; Giới hạn quyền truy cập cơ sở dữ liệu của ứng dụng theo nguyên tắc tối thiểu

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:49
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lệnh SQL được thực thi bằng phương thức executeUpdate với chuỗi truy vấn là tham số đầu vào từ người dùng mà không được tham số hóa. Đây là dấu hiệu điển hình của lỗ hổng SQL injection.
- Khắc phục: Sử dụng PreparedStatement thay vì Statement để thực thi truy vấn; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu; Xác thực và lọc đầu vào từ người dùng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson4.java:48
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Ứng dụng thực thi truy vấn SQL động bằng cách nối trực tiếp tham số từ request vào câu lệnh SQL thông qua Statement.executeUpdate(). Điều này tạo điều kiện cho tấn công SQL Injection nếu đầu vào không được kiểm tra hoặc lọc kỹ.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi SQL; Giới hạn quyền của tài khoản cơ sở dữ liệu mà ứng dụng sử dụng; Xác thực và lọc đầu vào theo danh sách cho phép (allowlist) nếu cần chấp nhận truy vấn động

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson5.java:65
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Lời gọi executeQuery sử dụng chuỗi truy vấn được truyền trực tiếp từ tham số 'query' mà không được tham số hóa. Điều này tạo điều kiện cho tấn công SQL Injection nếu dữ liệu đầu vào không được kiểm tra hoặc lọc.
- Khắc phục: Sử dụng truy vấn tham số hóa (Prepared Statements) thay vì nối chuỗi.; Giới hạn quyền truy cập cơ sở dữ liệu cho tài khoản ứng dụng.; Xác thực và làm sạch tất cả dữ liệu đầu vào từ người dùng.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson8.java:142
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức `log` xây dựng truy vấn SQL bằng cách nối chuỗi trực tiếp giá trị từ tham số `action` vào câu lệnh INSERT. Đây là mẫu hành vi dễ bị khai thác SQL injection nếu `action` đến từ người dùng mà không được kiểm tra kỹ.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu; Kiểm tra và làm sạch đầu vào trước khi sử dụng
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:65
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng xây dựng truy vấn SQL bằng cách nối trực tiếp các tham số từ request (name, auth_tan) vào chuỗi truy vấn. Việc này cho phép kẻ tấn công chèn cú pháp SQL độc hại thông qua các tham số, dẫn đến SQL Injection.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi.; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu.; Kiểm tra và làm sạch tất cả dữ liệu đầu vào.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:94
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Tất cả các truy vấn SQL trong mã đều là chuỗi hằng, không có sự nối dữ liệu từ người dùng. Các phương thức như getJohnSalary, getSumSalariesOfOtherEmployees, và getMaxSalary đều sử dụng truy vấn cố định. Không có bằng chứng cho thấy dữ liệu người dùng được đưa vào các truy vấn này.
- Khắc phục: Sử dụng PreparedStatement với tham số thay vì nối chuỗi để ngăn SQL Injection, ngay cả khi hiện tại dữ liệu không đến từ người dùng.; Xác minh rằng tất cả các truy vấn động đều được xử lý an toàn, ngay cả trong mã ví dụ hay bài học.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:117
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng 117 gọi statement.executeQuery(query) với một truy vấn SQL được xây dựng từ chuỗi tĩnh, không có dữ liệu người dùng được nối vào. Không có bằng chứng cho thấy biến query tại điểm này được điều khiển bởi người dùng.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL.; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu của ứng dụng.

## Kiểm chứng

- Agent đề xuất: `GET /WebGoat/login`
- Bị chặn: Người vận hành đã từ chối request này.
- **Kết luận kiểm chứng: `inconclusive`** — Không có bằng chứng từ ứng dụng: Người vận hành đã từ chối request này..

## Sự kiện bảo mật

- `approval`: 1
