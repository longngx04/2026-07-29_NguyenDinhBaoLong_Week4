# Worklog — Sửa lỗi chuẩn hoá dấu nháy lồng nhau trong `_normalize_reason`

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Task:** `Fix _normalize_reason nested quotes in tuple representations`

---

## 1. Tóm tắt

Đã khắc phục lỗi trong hàm `_normalize_reason` tại `src/project_sentinel/analysis/pipeline.py` khi xử lý các chuỗi lỗi có chứa biểu diễn tuple/dấu nháy lồng nhau (ví dụ: `Invented location '('A.java', 47)'`).
- **Nguyên nhân:** Regex đơn `['\"][^'\"]*['\"]` khớp tách rời `'('` và `', 47)'`, chừa lại tên file `A.java` ở giữa, làm các lỗi cùng loại bị chia tách thành nhiều khoá đếm riêng biệt trong `invalid_reasons`.
- **Giải pháp:** Bổ sung bước chuẩn hoá số trước (`_NUMBER_RE.sub("<num>", ...)`), sau đó nhận diện và thay thế cụm biểu diễn tuple/dấu ngoặc lồng (`_TUPLE_QUOTED_RE.sub("'<val>'", ...)`), cuối cùng mới chuẩn hoá các chuỗi trích dẫn đơn (`_QUOTED_RE.sub("'<val>'", ...)`).
- **Kiểm chứng:** Viết test kiểm tra trường hợp dấu nháy lồng nhau (test đỏ trước khi sửa, xanh sau khi sửa) và đảm bảo toàn bộ 915 tests offline cùng lint/typecheck đều đạt chuẩn.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đảm bảo tính nhất quán và chính xác của bảng thống kê chẩn đoán lỗi `invalid_reasons` trong `analysis-summary.json`.
- **Nằm ở đâu trong luồng:** Tại module `src/project_sentinel/analysis/pipeline.py` (hàm helper `_normalize_reason`).
- **Không có nó thì hỏng gì:** Các thông báo lỗi provenance liên quan đến vị trí mã nguồn (`Invented location (...)` hoặc `Dropped location (...)`) không thể gom nhóm theo loại lỗi mà bị phân mảnh theo từng tên file và số dòng cụ thể.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Thêm `_TUPLE_QUOTED_RE` và cập nhật thứ tự chuẩn hoá trong `_normalize_reason` | Khắc phục lỗi tách chuỗi nháy lồng nhau |
| `tests/unit/analysis/test_invalid_output_diagnostics.py` | Sửa | Thêm test case `test_invalid_reasons_normalizes_nested_quotes` | Kiểm chứng đỏ trước / xanh sau |

---

## 4. Làm như thế nào

1. Định nghĩa regex nhận diện cụm tuple/dấu ngoặc:
   ```python
   _TUPLE_QUOTED_RE = re.compile(r"'\([^)]*\)'|\([^)]*\)")
   _QUOTED_RE = re.compile(r"(['\"][^'\"]*['\"])")
   _NUMBER_RE = re.compile(r"\b\d+\b")
   ```
2. Trong hàm `_normalize_reason(reason: str) -> str`:
   - Bước 1: Thay thế các con số bằng placeholder `<num>`.
   - Bước 2: Thay thế các cụm biểu diễn tuple/ngoặc chứa nháy lồng bằng `'<val>'`.
   - Bước 3: Thay thế các chuỗi trong dấu nháy kép hoặc nháy đơn còn lại bằng `'<val>'`.
3. Kiểm tra với cả hai trường hợp:
   - Nested location quotes: `location '('A.java', 47)'` và `location '('B.java', 912)'` $\rightarrow$ đều cho ra `location '<val>'`.
   - Regular objective quotes: `payload_kind 'special_chars' ... 'POST /x'` và `payload_kind 'wrong_type' ... 'POST /y'` $\rightarrow$ đều cho ra `payload_kind '<val>' ... '<val>'`.

---

## 5. Output là gì

- Commit riêng biệt bằng tiếng Anh:
  `fix(analysis): normalize nested quotes in tuple representations for diagnostic reasons`
- Kết quả test:
```text
tests/unit/analysis/test_invalid_output_diagnostics.py::test_invalid_reasons_normalizes_nested_quotes PASSED
915 passed, 38 deselected, 1 warning in 15.71s
```

---

## 6. Vì sao chọn cách implement này

- **Chuẩn hoá theo thứ tự đa tầng (Multi-stage Normalization):** Việc xử lý số $\rightarrow$ tuple/ngoặc $\rightarrow$ quotes đơn lẻ giúp giải quyết triệt để vấn đề định dạng `str(tuple)` của Python mà không làm ảnh hưởng đến các thông báo lỗi dạng chuỗi đơn chuẩn khác (schema, unsafe, objective).
- **Không thay đổi điều kiện nghiệp vụ khác:** Giữ nguyên 100% logic retry và validation trong `pipeline.py`.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_invalid_output_diagnostics.py -v` | 0 | 5 passed (thêm 1 test cho nested quotes) |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **915 passed**, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |

---

## 8. Cần người review kỹ ở đâu

- **Khả năng bao phủ các định dạng tuple khác:** Hiện tại `_TUPLE_QUOTED_RE` khớp các cụm dạng `'\([^)]*\)'` và `\([^)]*\)`. Nếu validator trong tương lai sinh các cấu trúc lồng phức tạp hơn (ví dụ dict lồng trong tuple hoặc list lồng), regex có thể cần mở rộng để bao quát thêm `\{[^}]*\}` và `\[[^\]]*\]`.
