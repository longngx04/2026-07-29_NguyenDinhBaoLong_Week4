# Worklog — Gộp finding ZAP theo loại alert và cắt danh sách instance

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 4`

---

## 1. Tóm tắt

Đã cập nhật `normalize_zap_report` trong `zap_normalizer.py` để gộp toàn bộ các instance của cùng một mã alert `pluginid` thành một finding chuẩn duy nhất. Mỗi finding lưu danh sách `instances` (giới hạn tối đa `max_instances=20`) và số lượng instance thực tế `instances_total`, đồng thời giữ nguyên các trường top-level (`http_method`, `parameter`, `file_or_url`) từ instance đầu tiên. Kết quả: 41 instance từ lần quét authenticated được gộp gọn thành 14 finding, 11/11 unit tests pass 100% và tổng 868 tests offline đều xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Ngăn chặn bùng nổ số lượng finding khi quét DAST có session trên ứng dụng WebGoat (do WebGoat cấu hình tắt toàn bộ security header trên mọi URL dẫn tới hàng trăm URL cùng dính chung 1 alert cấu hình).
- **Nằm ở đâu trong luồng:** Tại bước chuẩn hoá `ingestion/zap_normalizer.py`, xử lý raw JSON từ ZAP trước khi đưa vào merge hoặc phân tích LLM.
- **Không có nó thì hỏng gì:** File `findings.json` sẽ phình to hàng trăm finding lặp lại gây lãng phí token LLM nghiêm trọng và làm loãng các lỗ hổng thật.
- **Ngoài phạm vi (cố ý không làm):** Chưa triển khai module đối chiếu route SAST $\leftrightarrow$ DAST (nội dung Task 5).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/ingestion/zap_normalizer.py` | Sửa | Triển khai gom nhóm theo `plugin_id`, thêm `instances` (cap 20), `instances_total` | Logic cốt lõi của Task 4 |
| `tests/unit/ingestion/test_zap_normalizer.py` | Sửa | Thêm 6 unit test kiểm tra gom nhóm, capping, cấu hình cap, lọc Gateway per instance | Kiểm chứng TDD tính đúng đắn của logic gộp |

**`git diff --stat`:**

```text
 src/project_sentinel/ingestion/zap_normalizer.py | 103 ++++++++++++++++-------
 tests/unit/ingestion/test_zap_normalizer.py      |  83 ++++++++++++++++++
 2 files changed, 154 insertions(+), 32 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Thay vì sinh một finding cho mỗi instance URL tìm thấy, ta gom toàn bộ instance hợp lệ (đã qua bộ lọc `_was_forwarded_by_dast_gateway`) vào một bucket theo `plugin_id`.
Sau đó tạo một finding đại diện cho mỗi `plugin_id`, kèm mảng `instances` chứa tối đa 20 URL đầu tiên và trường `instances_total` lưu tổng số URL bị ảnh hưởng.

**Luồng dữ liệu:**
Raw ZAP report $\rightarrow$ Lọc từng instance qua `_was_forwarded_by_dast_gateway` $\rightarrow$ Gom nhóm theo `plugin_id` $\rightarrow$ Cắt lát `collected[:max_instances]` $\rightarrow$ Trả về danh sách finding gộp.

**Các quyết định kỹ thuật:**
- `DEFAULT_MAX_INSTANCES = 20`: Đủ bằng chứng đại diện cho người đọc và LLM mà không làm tràn prompt context window.
- Giữ nguyên các trường top-level `http_method` và `parameter` từ instance đầu tiên để đảm bảo tính tương thích ngược 100% với các test và consumer hiện tại.
- Lọc Gateway boundary *trước* khi đưa vào danh sách instance của nhóm, loại bỏ triệt để các phản hồi 401/403 do Gateway tạo ra.

**Xử lý lỗi / trường hợp biên:**
- Báo lỗi `ValueError` nếu report thiếu `site` array hoặc site thiếu `alerts`.
- Bỏ qua an toàn các mục alert không có instance hợp lệ sau khi lọc.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `normalize_zap_report` | `normalize_zap_report(raw: dict[str, Any], *, max_instances: int = DEFAULT_MAX_INSTANCES) -> list[dict[str, Any]]` | Hàm chuẩn hoá gộp alert ZAP |
| Test | Nhóm test gom alert | `tests/unit/ingestion/test_zap_normalizer.py` | 6 unit test cho chức năng gom nhóm |

**Cách chạy:**

```bash
.venv/bin/python -c "
import json
from project_sentinel.ingestion.zap_normalizer import normalize_zap_report
raw = json.load(open('tests/fixtures/dast/zap-alerts-authenticated.json'))
f = normalize_zap_report(raw)
print('finding:', len(f), '| instance tong:', sum(x['instances_total'] for x in f))
for item in f[:5]:
    print(' ', item['rule_id'], item['severity'], item['instances_total'], item['title'][:40])
"
```

**Output thật:**

```text
finding: 14 | instance tong: 41
  10009 low 1 In Page Banner Information Leak
  10020 medium 4 Missing Anti-clickjacking Header
  10021 low 4 X-Content-Type-Options Header Missing
  10024 info 1 Information Disclosure - Sensitive Infor
  10027 info 2 Information Disclosure - Suspicious Comm
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Gom nhóm theo `plugin_id`, trích xuất instance đại diện và lưu mảng `instances` có capping.

**Lý do:**
- Phù hợp với đặc thù quét DAST: một lỗi cấu hình header sẽ kích hoạt trên mọi endpoint, tạo ra số lượng alert tỉ lệ thuận với số URL spider được.
- Đảm bảo token LLM ở bước `analyze` không bị lãng phí cho hàng chục bản sao cùng một lỗi.

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Giữ nguyên 1 finding / 1 instance | Đơn giản, không cần sửa logic | Làm bùng nổ số lượng finding (hàng trăm findings), gây lãng phí token và làm chậm pipeline |
| Gom nhóm nhưng bỏ hoàn toàn danh sách URL | Tiết kiệm dung lượng tối đa | Mất bằng chứng cụ thể về các endpoint bị ảnh hưởng, gây khó khăn cho việc đối chiếu ở Task 5 |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/ingestion/test_zap_normalizer.py -v` | 0 | 11 passed (5 cũ + 6 mới) |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 868 passed, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |

**Bất biến đã giữ:**
- Không sửa bất kỳ test cũ nào trong `test_zap_normalizer.py`.
- `http_method` và `parameter` vẫn hiện diện ở top-level của mỗi finding.
- Lọc Gateway chạy per-instance trước khi gom nhóm.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có (11 unit tests và bộ test 868 cases đã bao phủ toàn diện).
- **Giả định đã đặt:** Mặc định `max_instances=20` là đủ cho phân tích mà không vượt giới hạn token.
- **Việc còn nợ:** Chuyển sang Task 5: xây dựng `analysis/correlation.py` để đối chiếu SAST $\leftrightarrow$ DAST.
