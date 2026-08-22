# Worklog — Sửa lỗi sau review nhánh DAST (feat/zap-dast)

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Review Fixes`

---

## 1. Tóm tắt

Đã xử lý trọn vẹn 4 vấn đề được chỉ ra trong đợt review sau khi hoàn thành 9 task DAST:
1. **Fix 1:** Bổ sung `tool`, `instances` (danh sách URL/method/param) và `instances_total` vào dataclass `NormalizedFinding` và phương thức `from_dict()`. Trong `packet_builder.py`, loại bỏ heuristic đoán tool dựa trên chuỗi `://` và dùng trực tiếp `f.tool`. Thêm unit test đi qua `NormalizedFinding.from_dict` để đảm bảo finding ZAP luôn trích xuất được bằng chứng hợp lệ.
2. **Fix 2:** Khôi phục thứ tự trích xuất bằng chứng cho SAST trong `packet_builder.py` bằng cách sắp xếp danh sách `findings_to_process` theo `(location.file, location.line, id)` trước khi lặp. Thêm unit test xác nhận thứ tự `source_evidence` của SAST trùng khớp hoàn toàn với thứ tự duyệt `group.locations` cũ (bảo toàn hành vi AGENTS.md §2.1).
3. **Fix 3:** Cập nhật `FindingGroup.to_packet_group_dict()`, `pipeline.py`, `SecurityAnalysisRecord.to_dict()`/`from_dict()` và template giao diện `analysis.html` để phát và hiển thị đúng định dạng `{"url": ...}` đối với các finding DAST. Thêm test end-to-end xác nhận chu trình: group ZAP $\rightarrow$ packet mang location URL $\rightarrow$ Agent trả location URL $\rightarrow$ `validate_provenance` kiểm tra hai chiều thành công.
4. **Fix 4:** Xử lý lỗi fail-open trong `_extract_measured_reachability` (tại `pipeline.py`), loại bỏ nhánh `not source_ids or` và trả về `None` khi `source_finding_ids` rỗng.
5. **Ghi nhận số liệu đo đạc:** Ghi lại số liệu đối chiếu correlation thực tế trên 23 finding SAST WebGoat: `{'no_route': 4, 'route_known_not_reached': 19}` (0 `reachable`) vào `docs/limitations.md`. Làm rõ nguyên nhân do spider ZAP Baseline không chạy JavaScript để kích hoạt các request AJAX nạp bài học của WebGoat.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Sửa chữa các khiếm khuyết trong luồng dữ liệu của bước phân tích (`analysis`) và kiểm chứng (`provenance`), đảm bảo finding ZAP có đầy đủ bằng chứng trong prompt, không bị từ chối oan do sai lệch kiểu location URL, và bảo toàn 100% tính tất định của luồng SAST cũ.
- **Nằm ở đâu trong luồng:** Tại module dữ liệu `models.py`, bộ dựng gói phân tích `packet_builder.py`, engine gom nhóm `grouping.py`, bộ điều phối `pipeline.py`, và tài liệu `docs/limitations.md`.
- **Không có nó thì hỏng gì:**
  - Finding ZAP đi vào LLM prompt với `content=""` và ghi nhận `input_limitations` lỗi do thiếu instances.
  - Vị trí URL trả về từ LLM bị `validate_provenance` từ chối là "Invented URL location" vì input packet phát `{"file", "line"}` thay vì `{"url"}`.
  - Thứ tự source evidence trong prompt của SAST bị xáo trộn qua các lần chạy.
  - `_extract_measured_reachability` có nguy cơ fail-open khi `source_finding_ids` rỗng.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/models.py` | Sửa | Thêm `tool`, `instances`, `instances_total` vào `NormalizedFinding`; hỗ trợ `url` trong `SecurityAnalysisRecord` | Đồng bộ dữ liệu finding & record |
| `src/project_sentinel/analysis/evidence.py` | Sửa | Hỗ trợ đọc cả key `url` và `uri` trong `_dast_evidence` | Tương thích dữ liệu instance |
| `src/project_sentinel/analysis/packet_builder.py` | Sửa | Dùng `f.tool` trực tiếp; sắp xếp `findings_to_process` theo `(file, line, id)` | Bảo toàn thứ tự SAST và loại bỏ heuristic |
| `src/project_sentinel/analysis/grouping.py` | Sửa | `to_packet_group_dict` phát `{"url": ...}` khi finding là ZAP hoặc URL | Khớp schema location URL |
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Dựng `input_locations` dạng `{"url": ...}` cho ZAP; trả `None` khi `source_ids` rỗng | Hậu kiểm provenance và chặn fail-open |
| `src/project_sentinel/web/templates/analysis.html` | Sửa | Render `loc.url` hoặc `loc.file:loc.line` | Hiển thị giao diện đúng định dạng |
| `docs/limitations.md` | Sửa | Bổ sung số liệu correlation thực tế và hạn chế AJAX của WebGoat | Trung thực về giới hạn đo được |
| `tests/unit/analysis/test_dast_evidence.py` | Sửa | Thêm test kiểm tra `NormalizedFinding.from_dict` cung cấp bằng chứng ZAP | Kiểm thử Fix 1 |
| `tests/unit/analysis/test_packet_builder.py` | Sửa | Thêm test kiểm tra thứ tự bằng chứng SAST khớp `group.locations` cũ | Kiểm thử Fix 2 |
| `tests/unit/analysis/test_url_locations.py` | Sửa | Thêm test end-to-end chu trình URL location từ packet đến provenance | Kiểm thử Fix 3 |
| `tests/unit/analysis/test_calibration_measured.py` | Sửa | Thêm unit test kiểm tra `_extract_measured_reachability` fail-closed | Kiểm thử Fix 4 |

---

## 4. Làm như thế nào

1. **Fix 1:** Khai báo rõ các trường trong `NormalizedFinding` và đọc trong `from_dict`. Trong `packet_builder.py`, kiểm tra `f.tool` (hoặc `getattr(f, "tool", "")`) để phân luồng thay vì regex chuỗi `://`.
2. **Fix 2:** Trước vòng lặp trích xuất bằng chứng trong `packet_builder.py`, gọi `findings_to_process.sort(key=...)` với khóa sắp xếp `(file, line, id)`. Nhờ đó, tập hợp các cửa sổ mã nguồn `(path, start_line, end_line)` luôn được duyệt theo thứ tự tăng dần của vị trí tập tin và dòng.
3. **Fix 3:** Nhận diện finding ZAP qua `f.tool == "zap"` hoặc `loc.file.startswith("http")`, phát mảng `locations` chứa dictionary `{"url": loc.file}`. Phía `pipeline.py` xây dựng `input_locations` theo cùng quy tắc để `validate_provenance` so khớp đối xứng hai chiều.
4. **Fix 4:** Kiểm tra `if not source_ids: return None` ở đầu hàm `_extract_measured_reachability`, chỉ duyệt `f_id in source_ids`.

---

## 5. Output là gì

- Toàn bộ 4 commit riêng biệt:
  - `4037a41`: `fix(analysis): nạp instances và tool vào NormalizedFinding để cấp bằng chứng ZAP`
  - `351e060`: `fix(analysis): đảm bảo thứ tự bằng chứng SAST không đổi khi build packet`
  - `ec98b1f`: `fix(analysis): phát location dạng URL cho ZAP findings và validate provenance hai chiều`
  - `28de169`: `fix(analysis): trả None trong _extract_measured_reachability khi source_finding_ids rỗng`
- **Output kiểm thử:**

```text
============================== 908 passed, 38 deselected, 1 warning in 16.28s ==============================
All checks passed!
Success: no issues found in 78 source files
```

---

## 6. Vì sao chọn cách implement này

- **Dùng dataclass field tường minh:** Đảm bảo `NormalizedFinding` là typed model hoàn chỉnh, không phụ thuộc vào `getattr` dự phòng, giúp typechecker và linter bắt được lỗi từ sớm.
- **Sắp xếp tại `packet_builder`:** Đảm bảo tính bất biến (immutability) của `group.findings` trong khi vẫn tạo ra danh sách evidence item có thứ tự hoàn toàn tất định.
- **Sử dụng `SimpleNamespace` trong unit test:** Tuân thủ triệt để quy tắc D9 và test `test_no_doubles.py`, không tạo bất kỳ class test double nào mang tên `Dummy*` hay `Mock*`.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_dast_evidence.py -v` | 0 | 4 passed |
| `.venv/bin/python -m pytest tests/unit/analysis/test_packet_builder.py -v` | 0 | 3 passed |
| `.venv/bin/python -m pytest tests/unit/analysis/test_url_locations.py -v` | 0 | 5 passed |
| `.venv/bin/python -m pytest tests/unit/analysis/test_calibration_measured.py -v` | 0 | 9 passed |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |
| `.venv/bin/python -m pytest tests/unit/infra/test_docs_complete.py tests/test_docs_are_honest.py -v` | 0 | 35 passed |
| `.venv/bin/python -m pytest tests/test_no_doubles.py -v` | 0 | 2 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **908 passed**, 38 deselected (tăng từ 903) |

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:**
  1. Việc nhận diện finding DAST để phát location dạng `{"url": ...}` đang kiểm tra `f.tool == "zap"` hoặc URL bắt đầu bằng `http://`/`https://`. Nếu sau này có scanner DAST khác không đặt prefix `http` (hoặc đặt scheme khác), cần cập nhật thêm logic chuẩn hóa tại tầng ingestion.
  2. Số liệu correlation `{'no_route': 4, 'route_known_not_reached': 19}` phản ánh đúng việc spider ZAP Baseline không thực thi JavaScript để nạp các bài học AJAX của WebGoat. Đây là quyết định thiết kế đã được ghi nhận trong `docs/limitations.md`.
- **Việc còn nợ:** Không còn task nào tồn đọng trên branch `feat/zap-dast`.
