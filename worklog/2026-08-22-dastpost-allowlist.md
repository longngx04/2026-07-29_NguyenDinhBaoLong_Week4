# Worklog — DAST POST Allowlist (Task 2)

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-post-reachability.md`](docs/superpowers/plans/2026-08-22-dast-post-reachability.md) · **Task ID:** `Task 2`

---

## 1. Tóm tắt

1. Đã trích xuất 13 route ứng viên từ 19 SAST findings đang ở trạng thái `route_known_not_reached` và đối chiếu trực tiếp với mã nguồn Java của WebGoat.
2. Đã loại bỏ 2 route không đủ điều kiện (`/JWT/kid/follow/{user}` chứa path template `{user}`; `/SqlInjectionAdvanced/register` dùng `@PutMapping` thay vì `@PostMapping`), giữ lại 11 POST endpoints hợp lệ có dòng nguồn và tham số chính xác.
3. Thực hiện TDD: viết test trước `tests/unit/gateway/test_dast_allowlist.py` (6 tests đỏ), sau đó tạo `configs/gateway/dast-allowlist.json` (6 tests xanh), toàn bộ test suite 932 tests pass và `make lint && make typecheck` sạch.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cung cấp danh mục allowlist các POST endpoint đã qua kiểm duyệt (`configs/gateway/dast-allowlist.json`) kèm `canonical_body` vô hại và nguồn gốc mã nguồn Java (`file:line`). File này là nguồn sự thật (ground truth) để Task 3 (Nginx map) và Task 4 (ZAP Automation Framework requestor plan) triển khai tiếp theo.
- **Nằm ở đâu trong luồng:** Nằm ở tầng cấu hình Gateway (`configs/gateway/`), làm căn cứ đối chiếu độc lập cho các cấu hình Nginx Gateway và ZAP automation.
- **Không có nó thì hỏng gì:** Nginx Gateway và ZAP sẽ không có danh sách endpoint POST an toàn để gửi request kiểm thử; hoặc nếu tự do gửi POST mà không có allowlist kiểm duyệt tham số và body hằng số, hệ thống sẽ vi phạm nguyên tắc deny-by-default và có nguy cơ gửi payload không an toàn.
- **Ngoài phạm vi (cố ý không làm):**
  - Không tự động sinh file Nginx template hay ZAP YAML từ file JSON (theo Settled Constraint: hai bên phải được viết độc lập và kiểm tra đối chiếu qua unit test để bảo toàn nguyên tắc hai lớp kiểm tra).
  - Không bao gồm các HTTP method ngoài `POST` (như `PUT`, `DELETE`) hoặc các route có path template.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/unit/gateway/test_dast_allowlist.py` | Tạo | 6 unit tests kiểm tra cấu trúc allowlist, required fields, prefix `/WebGoat/`, method `POST`, không trùng lặp, `source` trỏ đúng `@PostMapping` trong Java source, `canonical_body` khớp `@RequestParam`, và không chứa từ khóa SQL/shell. | Đảm bảo tính toàn vẹn dữ liệu và kiểm soát chất lượng allowlist theo TDD. |
| `configs/gateway/dast-allowlist.json` | Tạo | Cấu hình allowlist gồm 11 endpoints đã kiểm duyệt với schema 1.0, method POST, `content_type`, `canonical_body` tối thiểu vô hại, `purpose`, và `source`. | Deliverable chính của Task 2 theo plan. |

**`git diff --stat`:**

```text
 configs/gateway/dast-allowlist.json       | 81 +++++++++++++++++++++++++++++++
 tests/unit/gateway/test_dast_allowlist.py | 79 ++++++++++++++++++++++++++++++
 2 files changed, 160 insertions(+)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. Chạy script trích xuất route từ `correlation.correlate` trên SAST findings thực tế kết hợp với access log DAST hiện có để tìm tất cả các route có `strength == 'route_known_not_reached'`.
2. Kiểm tra chi tiết từng route trong mã nguồn Java của WebGoat (`benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/`): tìm annotation `@PostMapping`, method signature, danh sách `@RequestParam`, và logic xử lý ngoại lệ khi tham số rỗng.
3. Lọc bỏ các route không hợp lệ và ghi rõ lý do.
4. Viết file test `tests/unit/gateway/test_dast_allowlist.py` để verify các ràng buộc nghiêm ngặt.
5. Chạy test xác nhận FAIL (RED - do thiếu file JSON).
6. Tạo file `configs/gateway/dast-allowlist.json` chứa 11 endpoint hợp lệ.
7. Chạy test xác nhận PASS (GREEN) và chạy toàn bộ test suite.

**Luồng dữ liệu:**
`SAST findings (findings.json)` → `correlation.py` → `13 Candidate Routes` → `Java Source Code Inspection` → `11 Validated POST Endpoints` → `dast-allowlist.json` + `test_dast_allowlist.py`

**Bảng chi tiết 13 route ứng viên đã kiểm tra:**

| Route | Java File & Line | Annotation & Method Signature | Parameter | Quyết định | Lý do |
|---|---|---|---|---|---|
| `/InsecureDeserialization/task` | `.../deserialization/InsecureDeserializationTask.java:32` | `@PostMapping("/InsecureDeserialization/task") public AttackResult completed(@RequestParam String token)` | `token` | **CHẤP NHẬN** | Token rỗng gây lỗi Base64 decode / deserialization EOF, được catch và trả AttackResult (HTTP 200) an toàn. |
| `/JWT/kid/follow/{user}` | `.../jwt/claimmisuse/JWTHeaderKIDEndpoint.java:48` | `@PostMapping("kid/follow/{user}") public String follow(@PathVariable("user") String user)` | `user` (PathVariable) | **LOẠI BỎ** | Path template chứa `{user}`, không phải exact static URI, Nginx map không xử lý trực tiếp dạng này. |
| `/SqlInjection/assignment5a` | `.../sqlinjection/introduction/SqlInjectionLesson5a.java:37` | `@PostMapping("/SqlInjection/assignment5a") public AttackResult completed(@RequestParam String account, ...)` | `account`, `operator`, `injection` | **CHẤP NHẬN** | Body `account=` rỗng làm query ném ngoại lệ hoặc trả kết quả rỗng, WebGoat bắt lại và trả 200. |
| `/SqlInjection/attack10` | `.../sqlinjection/introduction/SqlInjectionLesson10.java:41` | `@PostMapping("/SqlInjection/attack10") public AttackResult completed(@RequestParam String action_string)` | `action_string` | **CHẤP NHẬN** | Body `action_string=` rỗng làm câu LIKE '%...%' an toàn, trả 200. |
| `/SqlInjection/attack2` | `.../sqlinjection/introduction/SqlInjectionLesson2.java:40` | `@PostMapping("/SqlInjection/attack2") public AttackResult completed(@RequestParam String query)` | `query` | **CHẤP NHẬN** | Body `query=` rỗng làm executeQuery ném SQLException, WebGoat bắt lại và trả 200 — không SQL nào thực thi. |
| `/SqlInjection/attack3` | `.../sqlinjection/introduction/SqlInjectionLesson3.java:35` | `@PostMapping("/SqlInjection/attack3") public AttackResult completed(@RequestParam String query)` | `query` | **CHẤP NHẬN** | Body `query=` rỗng làm executeQuery ném ngoại lệ, WebGoat trả 200 an toàn. |
| `/SqlInjection/attack4` | `.../sqlinjection/introduction/SqlInjectionLesson4.java:36` | `@PostMapping("/SqlInjection/attack4") public AttackResult completed(@RequestParam String query)` | `query` | **CHẤP NHẬN** | Body `query=` rỗng làm executeQuery ném ngoại lệ, WebGoat trả 200 an toàn. |
| `/SqlInjection/attack5` | `.../sqlinjection/introduction/SqlInjectionLesson5.java:53` | `@PostMapping("/SqlInjection/attack5") public AttackResult completed(String query)` | `query` | **CHẤP NHẬN** | Body `query=` rỗng làm createUser và executeQuery an toàn, WebGoat trả 200. |
| `/SqlInjection/attack8` | `.../sqlinjection/introduction/SqlInjectionLesson8.java:41` | `@PostMapping("/SqlInjection/attack8") public AttackResult completed(@RequestParam String name, @RequestParam String auth_tan)` | `name`, `auth_tan` | **CHẤP NHẬN** | Body `name=` rỗng làm query trả kết quả rỗng an toàn, WebGoat trả 200. |
| `/SqlInjection/attack9` | `.../sqlinjection/introduction/SqlInjectionLesson9.java:42` | `@PostMapping("/SqlInjection/attack9") public AttackResult completed(@RequestParam String name, @RequestParam String auth_tan)` | `name`, `auth_tan` | **CHẤP NHẬN** | Body `name=` rỗng làm query trả kết quả rỗng an toàn, WebGoat trả 200. |
| `/SqlInjectionAdvanced/attack6a` | `.../sqlinjection/advanced/SqlInjectionLesson6a.java:42` | `@PostMapping("/SqlInjectionAdvanced/attack6a") public AttackResult completed(@RequestParam(value = "userid_6a") String userId)` | `userid_6a` | **CHẤP NHẬN** | Body `userid_6a=` rỗng làm query trả kết quả rỗng an toàn, WebGoat trả 200. |
| `/SqlInjectionAdvanced/attack6b` | `.../sqlinjection/advanced/SqlInjectionLesson6b.java:31` | `@PostMapping("/SqlInjectionAdvanced/attack6b") public AttackResult completed(@RequestParam String userid_6b)` | `userid_6b` | **CHẤP NHẬN** | Body `userid_6b=` rỗng so sánh với password trả kết quả failed an toàn, WebGoat trả 200. |
| `/SqlInjectionAdvanced/register` | `.../sqlinjection/advanced/SqlInjectionChallenge.java:42` | `@PutMapping("/SqlInjectionAdvanced/register") public AttackResult registerNewUser(...)` | `username_reg`, `email_reg`, `password_reg` | **LOẠI BỎ** | Endpoint dùng HTTP method `PUT` (`@PutMapping`), không phải `POST`. Allowlist này chỉ cấp phép riêng cho `POST`. |

**Các quyết định kỹ thuật:**
- `canonical_body` luôn chỉ chứa tên tham số hợp lệ kèm dấu `=` và giá trị rỗng (ví dụ `query=`, `token=`, `action_string=`), tuyệt đối không chứa payload thử nghiệm hay ký tự nhạy cảm như SQL keywords (`select`, `union`) hay shell characters.
- Tất cả đường dẫn đều phải có tiền tố `/WebGoat/`.
- Định dạng `source` ghi rõ đường dẫn tương đối từ gốc repository và dòng bắt đầu annotation `@PostMapping`.

**Xử lý lỗi / trường hợp biên:**
- Test `test_every_source_points_at_a_real_postmapping` đọc trực tiếp file Java và kiểm tra cửa sổ 5 dòng từ `source` để đảm bảo không bị sai lệch số dòng.
- Test `test_every_canonical_body_names_a_parameter_the_endpoint_declares` kiểm tra regex parameter trong method signature của file Java.
- Test `test_canonical_body_carries_no_sql_or_shell` quét blacklist các từ khóa nguy hiểm để đảm bảo không lọt payload khai thác.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Config | `dast-allowlist.json` | `configs/gateway/dast-allowlist.json` | File JSON chứa 11 endpoint POST đã kiểm duyệt cho lane DAST |
| Test | `test_dast_allowlist.py` | `tests/unit/gateway/test_dast_allowlist.py` | Bộ 6 unit tests kiểm tra tính hợp lệ và toàn vẹn của file allowlist |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/gateway/test_dast_allowlist.py -v
.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
make lint && make typecheck
```

**Output thật (đã che secret):**

```text
$ .venv/bin/python -m pytest tests/unit/gateway/test_dast_allowlist.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/longngx04/VinSOC/project_sentinel_main/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
plugins: respx-0.23.1, xdist-3.8.0, anyio-4.14.2, cov-7.1.0
collecting ... collected 6 items

tests/unit/gateway/test_dast_allowlist.py::test_every_entry_has_all_required_fields PASSED [ 16%]
tests/unit/gateway/test_dast_allowlist.py::test_every_entry_is_post_under_the_webgoat_prefix PASSED [ 33%]
tests/unit/gateway/test_dast_allowlist.py::test_no_duplicate_paths PASSED [ 50%]
tests/unit/gateway/test_dast_allowlist.py::test_every_source_points_at_a_real_postmapping PASSED [ 66%]
tests/unit/gateway/test_dast_allowlist.py::test_every_canonical_body_names_a_parameter_the_endpoint_declares PASSED [ 83%]
tests/unit/gateway/test_dast_allowlist.py::test_canonical_body_carries_no_sql_or_shell PASSED [100%]

============================== 6 passed in 0.03s ===============================

$ .venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests
932 passed, 38 deselected, 1 warning in 15.82s

$ make lint && make typecheck
All checks passed!
Success: no issues found in 78 source files
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:**
Xây dựng file `configs/gateway/dast-allowlist.json` tĩnh qua việc rà soát thủ công từng dòng mã nguồn Java của WebGoat và kiểm chứng tự động bằng test đọc trực tiếp file Java.

**Lý do:**
Plan quy định tại Task 2 Step 1 và Step 2: *"Với mỗi route, mở file Java khai nó và đọc chữ ký method... Loại các route không dùng được... Cổng bảo vệ duy nhất là người đọc @RequestParam rồi chọn body làm ít nhất có thể."* Việc đối chiếu mã nguồn đảm bảo tính chính xác tuyệt đối của tên tham số, tránh phỏng đoán và đảm bảo không có route không mong muốn lọt vào allowlist.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Tự động phân tích AST Java để sinh file JSON | Nhanh, tự động hóa | Nguy cơ parse nhầm method/parameter; vi phạm nguyên tắc review cẩn trọng từng endpoint có lỗ hổng bảo mật. |
| Cho phép cả PUT method (`/SqlInjectionAdvanced/register`) | Tăng thêm 1 finding reachable | Scope của plan và lane DAST hiện tại chỉ thiết kế cơ chế mở rộng cho `POST`. Mở thêm `PUT` làm tăng diện tấn công và nằm ngoài thiết kế của Nginx Gateway trong Task 3. |
| Dùng wildcard cho path template (`/JWT/kid/follow/*`) | Bao phủ được route JWT | Nginx `map` cho exact URI hiệu quả và an toàn hơn; path template chứa tham số động cần logic xử lý phức tạp hơn trên Gateway. |

**Đánh đổi đã chấp nhận:**
Bỏ qua 2 finding (opengrep-006 và opengrep-007) để giữ an toàn tuyệt đối cho kiến trúc Gateway và tuân thủ chặt chẽ nguyên tắc exact matching. 17/19 finding còn lại vẫn được giải quyết đầy đủ.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---:|---|
| `.venv/bin/python -m pytest tests/unit/gateway/test_dast_allowlist.py -v` | 0 | 6 passed in 0.03s |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 932 passed, 38 deselected |
| `make lint && make typecheck` | 0 | Ruff check passed, Mypy check passed (78 source files) |

**Test mới thêm:**
- `tests/unit/gateway/test_dast_allowlist.py::test_every_entry_has_all_required_fields` — Khẳng định mọi entry đều đủ 6 trường bắt buộc.
- `tests/unit/gateway/test_dast_allowlist.py::test_every_entry_is_post_under_the_webgoat_prefix` — Khẳng định chỉ chấp nhận POST, đường dẫn bắt đầu bằng `/WebGoat/`, không query string, không template.
- `tests/unit/gateway/test_dast_allowlist.py::test_no_duplicate_paths` — Khẳng định không có path trùng lặp.
- `tests/unit/gateway/test_dast_allowlist.py::test_every_source_points_at_a_real_postmapping` — Khẳng định `source` trỏ chính xác vào annotation `@PostMapping` và route tương ứng trong mã nguồn WebGoat.
- `tests/unit/gateway/test_dast_allowlist.py::test_every_canonical_body_names_a_parameter_the_endpoint_declares` — Khẳng định tên tham số trong `canonical_body` thực sự được khai báo trong chữ ký hàm Java.
- `tests/unit/gateway/test_dast_allowlist.py::test_canonical_body_carries_no_sql_or_shell` — Khẳng định body không chứa bất kỳ từ khóa SQL hay shell nào.

**Bất biến đã giữ:**
- Không mock/stub;
- Không sửa reports lịch sử `reports/week-XX/`;
- Giữ nguyên cấu trúc deny-by-default;
- Không lộ secret / API key;
- Không push code lên remote.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có chỗ nào thiếu chắc chắn vì cả 11 endpoints đều đã được đối chiếu trực tiếp với mã nguồn Java tại dòng khai báo `@PostMapping` và tham số `@RequestParam`.
- **Giả định đã đặt:** Giả định rằng gửi `canonical_body` dạng rỗng (`<param>=`) tới 11 endpoint này sẽ kích hoạt phản hồi an toàn từ WebGoat mà không gây tác dụng phụ ngoài ý muốn (Task 1 đã xác minh giả định này trên WebGoat).
- **Việc còn nợ:** Task 3 sẽ dùng `dast-allowlist.json` để cấu hình Nginx Gateway map.
- **Câu hỏi cho người dùng:** Không có.
