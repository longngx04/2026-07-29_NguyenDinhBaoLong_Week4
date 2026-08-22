# Worklog — Sửa lỗi sau review đợt 2 nhánh DAST (feat/zap-dast)

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Review Fixes Round 2`

---

## 1. Tóm tắt

Đã xử lý 2 vấn đề theo yêu cầu review đợt 2:
1. **Fix A:** Loại bỏ cờ `is_zap` cấp nhóm tại `FindingGroup.to_packet_group_dict` và `pipeline.py` (`_validate_response`). Kiểm tra định dạng vị trí trực tiếp trên từng `location` (`loc.file.startswith("http://") or loc.file.startswith("https://")`). Nhờ đó, trong một nhóm hỗn hợp chứa cả finding SAST và DAST, các finding SAST vẫn giữ nguyên `{"file": ..., "line": ...}` và không bị ép thành URL mất số dòng. Thêm test kiểm tra nhóm hỗn hợp.
2. **Fix B:** Tách biểu thức lambda sort key dài hơn 200 ký tự trong `packet_builder.py` thành hàm module-level `_evidence_sort_key(f)` rõ ràng, có docstring đầy đủ, xử lý tách bạch cả dạng object có `.location` và dạng dict. Giữ nguyên 100% tính tất định của thứ tự bằng chứng.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đảm bảo tính chính xác của schema vị trí khi gom nhóm finding hỗn hợp (hybrid SAST + DAST) và tăng cường chất lượng, tính dễ đọc của mã nguồn trong engine dựng gói phân tích.
- **Nằm ở đâu trong luồng:** Tại module `grouping.py`, `packet_builder.py`, `pipeline.py`, và test suite `test_url_locations.py`.
- **Không có nó thì hỏng gì:** Khi gom nhóm lai chứa cả SAST và DAST, các location file Java của SAST bị ép thành `{"url": "benchmarks/..."}` và mất trường `line`, vi phạm schema provenance và làm sai lệch ngữ cảnh source window.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/grouping.py` | Sửa | Xoá `is_zap` cấp nhóm, chỉ kiểm tra prefix URL trên từng location | Không ép sai định dạng SAST |
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Xoá `is_zap` cấp nhóm trong bước dựng `input_locations` | Đồng bộ provenance với grouping |
| `src/project_sentinel/analysis/packet_builder.py` | Tái cấu trúc | Tách hàm `_evidence_sort_key(f)` có docstring | Dọn dẹp dòng code quá dài |
| `tests/unit/analysis/test_url_locations.py` | Sửa | Thêm `test_mixed_sast_and_zap_group_preserves_both_location_types` | Khẳng định nhóm hỗn hợp giữ cả 2 kiểu location |

---

## 4. Làm như thế nào

1. **Fix A:** Trong cả `FindingGroup.to_packet_group_dict` và `_validate_response`, duyệt `for loc in ...` và kiểm tra `if loc.file.startswith("http://") or loc.file.startswith("https://"): {"url": loc.file}` else `{"file": loc.file, "line": loc.line}`.
2. **Fix B:** Khai báo hàm `_evidence_sort_key(f)` ở module level, kiểm tra tường minh `hasattr(f, "location")` và `isinstance(f, dict)` để trích xuất `(file, line, id)`.
3. **Kiểm thử:** Thêm test tạo `FindingGroup` chứa 1 finding opengrep (dòng 47 file Java) và 1 finding zap (URL login), kiểm tra output packet chứa đúng 2 location riêng biệt theo 2 định dạng khác nhau.

---

## 5. Output là gì

- 2 commit riêng biệt:
  - `80abc8e`: `fix(analysis): bỏ cờ is_zap cấp nhóm và kiểm tra url theo từng location`
  - `aaaf37e`: `refactor(analysis): tách hàm _evidence_sort_key rõ ràng và có docstring`
- **Output kiểm thử:**

```text
============================== 908 passed, 38 deselected, 1 warning in 16.14s ==============================
All checks passed!
Success: no issues found in 78 source files
```

---

## 6. Vì sao chọn cách implement này

- **Kiểm tra theo từng location:** Vị trí là thuộc tính của từng finding cụ thể, không phải của toàn nhóm. Việc kiểm tra theo prefix URL trên từng `loc.file` tự nhiên và chính xác hơn cờ nhóm toàn cục.
- **Hàm `_evidence_sort_key` tường minh:** Viết tách các nhánh `if/else` giúp code dễ đọc, dễ debug và tránh các lỗi runtime khi gặp dữ liệu finding dạng dict hoặc object.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_url_locations.py -v` | 0 | 6 passed (thêm 1 test cho mixed group) |
| `.venv/bin/python -m pytest tests/unit/analysis/test_packet_builder.py -v` | 0 | 3 passed |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **908 passed**, 38 deselected |

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Logic nhận diện URL đang dựa vào `startswith("http://")` hoặc `startswith("https://")`. Với toàn bộ các URL DAST từ Gateway/ZAP thì điều này luôn đúng. Tuy nhiên nếu trong tương lai có thêm giao thức khác (e.g. `ws://`, `wss://`), cần cập nhật thêm prefix hoặc dùng `urllib.parse.urlsplit`.
- **Việc còn nợ:** Không còn task nào tồn đọng.
