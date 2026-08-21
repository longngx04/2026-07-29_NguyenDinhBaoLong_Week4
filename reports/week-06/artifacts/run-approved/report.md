# Báo cáo bảo mật — lần chạy `20260821T083837Z`

## Tổng quan

- Trạng thái: **DONE**
- Cảnh báo thô: **23**
- Nhóm sau phân tích: **21**
- Mức nghiêm trọng: {'high': 13, 'medium': 8}
- Kết luận của Agent: {'likely': 7, 'confirmed': 10, 'needs_review': 4}
- Người phê duyệt: cli-operator
> Hệ thống đã hạ mức hoặc hạ kết luận của **3** phát hiện vì bằng chứng không đủ. Chi tiết ở từng mục bên dưới.
- Lời gọi LLM: 21 (0 phản hồi không hợp lệ)

## Phát hiện

### Command Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/dummy/insecure/framework/VulnerableTaskHolder.java:69
- Kết luận: `likely` (attacker_control: `proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 69 gọi Runtime.getRuntime().exec(taskAction), trong đó taskAction là một trường được khôi phục từ quá trình deserialization. Biến này đến từ dữ liệu đầu vào qua stream.readObject(), và nếu không được kiểm soát chặt chẽ, có thể bị khai thác để thực thi lệnh hệ thống. Tuy nhiên, có điều kiện kiểm tra rằng taskAction phải bắt đầu bằng 'sleep' hoặc 'ping' và độ dài dưới 22 ký tự, làm giảm khả năng khai thác nhưng không loại bỏ hoàn toàn rủi ro.
- Khắc phục: Tránh sử dụng Runtime.exec với dữ liệu do người dùng kiểm soát; Sử dụng ProcessBuilder với danh sách tham số rõ ràng thay vì chuỗi lệnh; Áp dụng allowlist cho các lệnh được phép thực thi; Không deserialize dữ liệu từ nguồn không tin cậy

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/lessons/LessonConnectionInvocationHandler.java:31
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 31 thực hiện nối chuỗi trực tiếp giữa hằng số và kết quả của user.getUsername() vào câu lệnh SQL. Nếu username chứa ký tự đặc biệt như nháy kép hoặc dấu chấm phẩy, có thể dẫn đến thay đổi hành vi truy vấn. Đây là mẫu mã điển hình của SQL Injection nếu dữ liệu đầu vào không được kiểm soát.
- Khắc phục: Sử dụng truy vấn tham số hóa hoặc stored procedure; Lọc và kiểm tra tính hợp lệ của username trước khi sử dụng trong SET SCHEMA; Tránh nối chuỗi trực tiếp trong truy vấn SQL khi có dữ liệu người dùng
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/container/users/UserService.java:57
- Kết luận: `likely` (attacker_control: `proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Lệnh SQL tại dòng 57 được xây dựng bằng cách nối trực tiếp tên người dùng vào chuỗi truy vấn. Nếu tên người dùng đến từ đầu vào người dùng mà không được kiểm tra, kẻ tấn công có thể chèn ký tự đặc biệt để thay đổi cấu trúc lệnh SQL, dẫn đến SQL Injection.
- Khắc phục: Sử dụng câu lệnh tham số hóa hoặc API an toàn hơn để tạo schema; Kiểm tra và làm sạch tên người dùng, chỉ cho phép các ký tự an toàn; Giới hạn đặc quyền của tài khoản cơ sở dữ liệu để ngăn tạo schema tùy ý

### Potential unsafe deserialization — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/InsecureDeserializationTask.java:45
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Ứng dụng thực hiện deserialize dữ liệu nhị phân từ tham số 'token' do người dùng cung cấp thông qua ObjectInputStream.readObject() mà không xác thực nguồn gốc hay kiểm tra tính toàn vẹn. Đây là lỗ hổng deserialization không an toàn, có thể bị khai thác để thực thi mã từ xa (RCE) nếu attacker cung cấp một gadget chain hợp lệ.
- Khắc phục: Sử dụng cơ chế xác thực chữ ký số (digital signature) để đảm bảo dữ liệu serialized không bị thay đổi.; Thay thế ObjectInputStream bằng các cơ chế serialization an toàn hơn như JSON hoặc XML với kiểm tra schema.; Áp dụng ValidatingObjectInputStream để kiểm tra loại đối tượng được deserialize.; Cập nhật và sử dụng các thư viện như Apache Commons IO hoặc Jackson với cấu hình an toàn.

### Insecure Deserialization — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/deserialization/SerializationHelper.java:23
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Phương thức `fromString` thực hiện deserialization trên chuỗi Base64 do người gọi cung cấp mà không xác thực hoặc kiểm soát nội dung. Việc sử dụng `ObjectInputStream.readObject()` có thể dẫn đến thực thi mã từ xa nếu attacker cung cấp một chuỗi serialized chứa gadget chain. Đây là hành vi nguy hiểm đặc trưng của CWE-502.
- Khắc phục: Sử dụng cơ chế deserialization an toàn như `ObjectInputFilter` để giới hạn các lớp được phép deserialize; Thay thế bằng định dạng dữ liệu an toàn hơn như JSON với ánh xạ rõ ràng sang các lớp cụ thể; Xác thực và ký dữ liệu serialized để đảm bảo tính toàn vẹn
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/jwt/claimmisuse/JWTHeaderKIDEndpoint.java:73
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Tại dòng 73, truy vấn SQL được xây dựng bằng cách nối trực tiếp giá trị `kid` từ header JWT vào chuỗi truy vấn. Vì `kid` đến từ người dùng (qua token) và không được kiểm tra hay lọc, điều này tạo điều kiện cho SQL Injection nếu attacker cung cấp giá trị `kid` độc hại.
- Khắc phục: Sử dụng prepared statement thay vì nối chuỗi SQL; Validate và giới hạn giá trị `kid` chỉ cho phép ký tự an toàn; Không tin tưởng bất kỳ trường nào trong JWT header nếu chưa được xác thực

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionChallenge.java:57
- Kết luận: `likely` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: medium
- Giải thích: Dòng 57 thực hiện nối trực tiếp tham số 'username' vào chuỗi truy vấn SQL thông qua phép cộng chuỗi, tạo điều kiện cho SQL injection nếu đầu vào không được kiểm soát đúng cách. Đây là mẫu phổ biến của CWE-89.
- Khắc phục: Sử dụng PreparedStatement thay vì Statement để truy vấn kiểm tra người dùng; Thay thế việc nối chuỗi bằng tham số hóa: SELECT userid FROM sql_challenge_users WHERE userid = ?

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionLesson6a.java:72
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra tại dòng 72 khi tham số `accountName` (xuất phát từ `@RequestParam userid_6a`) được nối trực tiếp vào chuỗi truy vấn SQL mà không được kiểm tra, lọc hay tham số hóa. Điều này cho phép kẻ tấn công chèn mã SQL độc hại bằng cách điều khiển giá trị của tham số.
- Khắc phục: Sử dụng prepared statement với tham số hóa thay vì nối chuỗi SQL; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu; Kiểm tra và lọc đầu vào nghiêm ngặt, không dựa vào việc phát hiện từ khóa như UNION; Không trả về thông tin truy vấn chi tiết trong phản hồi lỗi

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionLesson6b.java:49
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `proven`)
- Độ tin cậy: low
- Giải thích: Dòng 49 gọi `statement.executeQuery(query)` với `query` là một chuỗi hằng, không có sự nối dữ liệu từ tham số người dùng. Biến `userid_6b` không được dùng trong `getPassword()`. Do đó, không có lỗ hổng SQL Injection tại sink này.
- Khắc phục: Sử dụng truy vấn tham số hóa (parameterized queries) nếu cần truy vấn theo giá trị người dùng.; Không nối chuỗi trực tiếp vào truy vấn SQL.

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:56
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra tại dòng 56, nơi tham số 'action' từ người dùng được nối trực tiếp vào chuỗi truy vấn SQL mà không được kiểm tra hay lọc. Điều này cho phép kẻ tấn công chèn các ký tự đặc biệt như dấu phẩy đơn để thay đổi logic truy vấn, có thể dẫn đến truy cập dữ liệu trái phép.
- Khắc phục: Sử dụng PreparedStatement thay vì nối chuỗi để xây dựng truy vấn; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu; Thực hiện kiểm tra và lọc đầu vào nghiêm ngặt

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java:100
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng 100 nằm trong phương thức tableExists, nơi thực hiện truy vấn SQL cố định 'SELECT * FROM access_log'. Đây là một truy vấn tĩnh, không có sự nối chuỗi với dữ liệu người dùng. Không có bằng chứng cho thấy dữ liệu do người dùng kiểm soát được đưa vào câu lệnh SQL tại vị trí này.
- Khắc phục: Sử dụng truy vấn tham số hóa ngay cả với truy vấn cố định nếu có khả năng tên bảng hoặc cấu trúc CSDL thay đổi theo đầu vào.; Ghi log lỗi chi tiết thay vì trả về thông điệp lỗi CSDL cho người dùng để tránh tiết lộ thông tin.

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson2.java:49
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Tham số 'query' từ request được truyền trực tiếp vào phương thức executeQuery của đối tượng Statement tại dòng 49, cho phép kẻ tấn công thực thi câu lệnh SQL tùy ý. Đây là lỗ hổng SQL Injection rõ ràng.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi vào truy vấn; Áp dụng nguyên tắc đặc quyền tối thiểu cho kết nối cơ sở dữ liệu; Xác thực và lọc đầu vào nghiêm ngặt nếu vẫn cần chấp nhận truy vấn động

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:47, benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson3.java:49
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Tham số 'query' từ request được truyền trực tiếp vào statement.executeUpdate(query) tại dòng 47 mà không được kiểm tra, lọc hay sử dụng truy vấn tham số hóa, cho phép kẻ tấn công thực thi câu lệnh SQL tùy ý.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi vào câu lệnh SQL; Giới hạn quyền của tài khoản cơ sở dữ liệu mà ứng dụng sử dụng; Xác thực và lọc đầu vào từ người dùng trước khi sử dụng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson4.java:46, benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson4.java:48
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Tham số 'query' từ request được truyền trực tiếp vào phương thức 'statement.executeUpdate(query)' mà không được kiểm tra, lọc hoặc tham số hóa. Điều này cho phép kẻ tấn công thực thi các truy vấn SQL tùy ý, dẫn đến lỗ hổng SQL Injection.
- Khắc phục: Sử dụng prepared statement với tham số hóa thay vì nối chuỗi vào truy vấn SQL; Áp dụng nguyên tắc đặc quyền tối thiểu cho kết nối cơ sở dữ liệu; Xác thực và lọc đầu vào người dùng nghiêm ngặt trước khi sử dụng

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson5.java:65
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra tại phương thức `injectableQuery` khi tham số `query` từ người dùng được truyền trực tiếp vào `statement.executeQuery(query)` mà không được tham số hóa hay kiểm tra. Điều này cho phép kẻ tấn công thực thi truy vấn SQL tùy ý.
- Khắc phục: Sử dụng prepared statement với tham số hóa thay vì nối chuỗi vào truy vấn SQL; Áp dụng nguyên tắc least privilege cho kết nối cơ sở dữ liệu; Xác thực và lọc đầu vào người dùng theo danh sách cho phép (allowlist)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson5a.java:52
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra tại dòng 52, nơi tham số `accountName` được nối trực tiếp vào chuỗi truy vấn SQL mà không được kiểm tra hay tham số hóa. Biến `accountName` bắt nguồn từ các tham số người dùng (`account`, `operator`, `injection`) được gộp lại trong phương thức `completed`, do đó hoàn toàn do người dùng kiểm soát. Điều này cho phép kẻ tấn công thay đổi logic truy vấn, ví dụ bằng cách chèn `' OR '1'='1` để lấy dữ liệu bất hợp pháp.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL.; Áp dụng nguyên tắc đặc quyền tối thiểu cho tài khoản cơ sở dữ liệu của ứng dụng.; Kiểm tra và xác thực tất cả dữ liệu đầu vào từ người dùng.

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson8.java:62
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Lỗ hổng SQL Injection xảy ra tại dòng 62 khi hai tham số người dùng (name, auth_tan) được nối trực tiếp vào chuỗi truy vấn SQL mà không được kiểm tra hay tham số hóa. Điều này cho phép kẻ tấn công thay đổi logic truy vấn bằng cách chèn ký tự đặc biệt như dấu phẩy đơn.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi SQL; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu; Kiểm tra và lọc đầu vào người dùng

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson8.java:142
- Kết luận: `likely` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: medium
- Giải thích: Lời gọi `statement.executeUpdate(logQuery)` tại dòng 142 sử dụng một chuỗi được xây dựng bằng cách nối dữ liệu từ tham số `action` vào truy vấn SQL. Đây là hành vi nguy hiểm nếu `action` đến từ người dùng. Tuy nhiên, bằng chứng hiện tại không cho thấy `action` có đến từ một endpoint hay tham số request nào hay không.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL.; Áp dụng nguyên tắc least privilege cho kết nối cơ sở dữ liệu.; Kiểm tra và xác thực đầu vào `action` trước khi sử dụng.
- Hệ thống hiệu chỉnh: mức `high` → `medium` (luật: attacker_control_not_proven)

### SQL Injection — `high`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:65
- Kết luận: `confirmed` (attacker_control: `proven`, reachability: `proven`)
- Độ tin cậy: high
- Giải thích: Dòng 65 tạo một chuỗi truy vấn SQL bằng cách nối trực tiếp hai tham số người dùng (name và auth_tan) vào câu lệnh SQL. Điều này cho phép kẻ tấn công chèn mã SQL độc hại thông qua các tham số này, dẫn đến lỗ hổng SQL Injection.
- Khắc phục: Sử dụng truy vấn tham số hóa (Prepared Statements) thay vì nối chuỗi để xây dựng truy vấn SQL.; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu của ứng dụng.; Xác thực và lọc đầu vào người dùng trước khi sử dụng trong truy vấn.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:94
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng 94 gọi `statement.executeQuery(query)` trong phương thức `getEmployeesDataOrderBySalaryDesc`, nơi `query` là một chuỗi hằng: "SELECT * FROM employees ORDER BY salary DESC". Không có dấu hiệu nào cho thấy truy vấn này được xây dựng từ dữ liệu người dùng. Tất cả các truy vấn trong lớp đều sử dụng chuỗi cố định, không có tham số động hay nối chuỗi.
- Khắc phục: Sử dụng truy vấn tham số hóa (PreparedStatement) thay vì Statement nếu cần truyền dữ liệu động vào truy vấn.; Kiểm tra và xác thực tất cả dữ liệu đầu vào trước khi sử dụng trong bất kỳ ngữ cảnh nào.

### SQL Injection — `medium`

- Vị trí: benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson9.java:117
- Kết luận: `needs_review` (attacker_control: `not_proven`, reachability: `not_proven`)
- Độ tin cậy: low
- Giải thích: Dòng 117 gọi `statement.executeQuery(query)` với một truy vấn SQL được tạo dưới dạng chuỗi hằng, không nối với dữ liệu người dùng. Tất cả các truy vấn trong đoạn mã đều là hằng số, không có dấu hiệu của việc nối tham số hoặc biến có thể kiểm soát bởi người dùng.
- Khắc phục: Sử dụng PreparedStatement với tham số hóa thay vì nối chuỗi để xây dựng truy vấn SQL.; Áp dụng nguyên tắc least privilege cho tài khoản cơ sở dữ liệu dùng trong ứng dụng.

## Kiểm chứng

- Agent đề xuất: `GET /WebGoat/login`
- Kết quả qua Gateway: HTTP **200** trong 6.96ms
- Finding được nhắm tới: `analysis-9a3d7f2e-4b1c-4d8e-9f2a-1b3c4d5e6f7a` (opengrep-002)
- **Kết luận kiểm chứng: `inconclusive`** — Endpoint `/WebGoat/login` không nằm trong bằng chứng của finding `analysis-9a3d7f2e-4b1c-4d8e-9f2a-1b3c4d5e6f7a`, nên mã trạng thái trả về không nói gì về lỗ hổng đó.

## Sự kiện bảo mật

- `approval`: 1
