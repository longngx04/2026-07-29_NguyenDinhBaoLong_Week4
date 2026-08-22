# Worklog — Đọc bản đồ endpoint và đối chiếu SAST ↔ DAST

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 5`

---

## 1. Tóm tắt

Đã xây dựng module `analysis/correlation.py` để trích xuất bản đồ endpoint runtime từ Nginx access log (`parse_gateway_access_log`), phân tích route Spring controller tĩnh từ mã nguồn Java (`extract_route`), và đối chiếu finding SAST với endpoint DAST (`correlate`). Cơ chế gán khối `runtime_evidence` xác định độ mạnh runtime (`strength`) theo 4 mức tất định mà không phụ thuộc vào LLM. Toàn bộ 15/15 unit test mới pass 100%, bảo toàn 883 test suite offline.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Làm cầu nối giữa finding tĩnh của SAST (vị trí file code Java) và quan sát động của DAST (URL đã được Gateway proxy tới WebGoat).
- **Nằm ở đâu trong luồng:** Nằm tại `src/project_sentinel/analysis/correlation.py`, được gọi sau khi nạp finding tĩnh và trước khi hiệu chỉnh reachability.
- **Không có nó thì hỏng gì:** Khẳng định reachability của SAST chỉ dựa vào phán đoán có thể bịa (hallucination) của LLM thay vì bằng chứng đo đạc thực tế từ hạ tầng mạng.
- **Ngoài phạm vi (cố ý không làm):** Chưa gắn `measured_reachability` vào pipeline calibration (nội dung của Task 6).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/correlation.py` | Tạo | Thư viện parse access log, trích xuất route annotation, đối chiếu SAST $\leftrightarrow$ DAST | Module cốt lõi của Task 5 |
| `tests/unit/analysis/test_correlation.py` | Tạo | 15 unit test cho parser log, lọc 403, trích xuất route, phân loại strength, immutability | Bộ kiểm chứng TDD đầy đủ |

**`git diff --stat`:**

```text
 src/project_sentinel/analysis/correlation.py | 158 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 tests/unit/analysis/test_correlation.py      | 111 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 269 insertions(+)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Đối chiếu tất định bằng cách đọc dữ liệu hạ tầng (access log của Nginx) và phân tích tĩnh file mã nguồn tương ứng với `file_or_url` trong finding SAST.
Tìm các annotation `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping` để ghép thành đường dẫn route đầy đủ.

**Luồng dữ liệu:**
`gateway-access-authenticated.log` $\rightarrow$ `parse_gateway_access_log` (lọc các request status $< 400$) $\rightarrow$ `endpoints` $\rightarrow$ `correlate(findings, endpoints, project_root)` $\rightarrow$ `runtime_evidence` gắn vào mỗi finding SAST.

**Thang đo độ mạnh runtime (`STRENGTHS`):**
1. `no_route`: File nguồn không chứa route annotation (ví dụ class POJO/helper).
2. `route_known_not_reached`: File khai báo route nhưng ZAP chưa spider chạm tới.
3. `reachable`: Route đã được ZAP truy cập thành công qua Gateway.
4. `reachable_and_alerted`: Route đã được truy cập và ZAP đồng thời phát hiện alert trên chính URL đó.

**Các quyết định kỹ thuật:**
- Bằng chứng endpoint lấy từ access log Nginx ở tầng hạ tầng, không lấy từ biến đếm ZAP.
- Không gắn block `runtime_evidence` vào các finding có `tool="zap"` vì bản thân finding DAST đã là bằng chứng runtime.
- Không mutate input list (`correlate` trả về danh sách finding mới).

**Xử lý lỗi / trường hợp biên:**
- Log file không tồn tại $\rightarrow$ trả về `{"endpoints": []}` an toàn.
- File code Java vượt quá 512KB hoặc không đọc được $\rightarrow$ bỏ qua và trả về `None`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Module | `correlation` | `src/project_sentinel/analysis/correlation.py` | Module đối chiếu runtime |
| Hàm | `parse_gateway_access_log` | `(path: str \| Path) -> dict[str, Any]` | Parse access log Nginx |
| Hàm | `extract_route` | `(source_path: str \| Path) -> str \| None` | Trích xuất route Spring |
| Hàm | `correlate` | `(findings, endpoints, *, project_root) -> list[dict]` | Đối chiếu finding |

**Cách chạy:**

```bash
.venv/bin/python -c "
from project_sentinel.analysis.correlation import parse_gateway_access_log
m = parse_gateway_access_log('tests/fixtures/dast/gateway-access-authenticated.log')
print('endpoint:', len(m['endpoints']))
for e in m['endpoints'][:10]: print(' ', e['method'], e['path'], e['params'])
"
```

**Output thật:**

```text
endpoint: 17
  GET / []
  GET /WebGoat/WebWolf []
  GET /WebGoat/actuator/health []
  GET /WebGoat/css/animate.css []
  GET /WebGoat/css/coderay.css []
  GET /WebGoat/css/font-awesome.min.css []
  GET /WebGoat/css/img/enlang.svg []
  GET /WebGoat/css/img/favicon.ico []
  GET /WebGoat/css/img/frlang.svg []
  GET /WebGoat/css/img/wolf.svg []
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Phân tích cú pháp Spring MVC annotation kết hợp parse Nginx access log thật.

**Lý do:**
- Hoàn toàn tất định, chạy ngoại tuyến nhanh, không tiêu tốn token LLM và không có nguy cơ bịa đặt thông tin.
- Dữ liệu access log của Nginx là bằng chứng hạ tầng khách quan, loại trừ hoàn toàn các request bị Gateway chặn hoặc drop.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Dùng LLM để suy luận route | Linh hoạt với nhiều cú pháp | Không tất định, tốn chi phí token, có thể hallucinate route không có thật |
| Đọc URL trực tiếp từ ZAP spider | Đơn giản | Bỏ sót các request probe ngoài ZAP và không phản ánh chính xác ranh giới mà Gateway đã thực sự chuyển tiếp |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_correlation.py -v` | 0 | 15 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 883 passed, 38 deselected |
| `make lint && make typecheck` | 0 | Sạch 100%, 0 errors |

**Bất biến đã giữ:**
- Không mock/stub; test chạy với file thật và fixture thật.
- Input list không bị biến đổi (immutability).
- STRENGTHS sắp xếp từ yếu đến mạnh (`no_route` $\rightarrow$ `reachable_and_alerted`).

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Regex `_CLASS_MAPPING` và `_METHOD_MAPPING` chỉ bắt các annotation Spring chuẩn; các controller viết dạng DSL hoặc custom router sẽ rơi về `no_route`.
- **Giả định đã đặt:** Toàn bộ lesson WebGoat dùng annotation Spring MVC chuẩn `@RequestMapping` / `@PostMapping` / `@GetMapping`.
- **Việc còn nợ:** Task 6: Tích hợp `measured_reachability` vào `calibration.py`.
