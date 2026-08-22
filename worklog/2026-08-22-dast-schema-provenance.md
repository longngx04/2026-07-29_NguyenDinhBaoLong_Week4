# Worklog — Schema, provenance và bằng chứng cho finding URL

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 8`

---

## 1. Tóm tắt

Đã mở rộng JSON Schema `security-analysis-record.schema.json` để trường `locations[]` chấp nhận cả hai định dạng: vị trí mã nguồn `{file, line}` và vị trí động `{url, method?, param?}` bằng nhánh `oneOf`. Cập nhật hàm `validate_provenance` trong `validators.py` để kiểm tra toàn vẹn hai chiều cho cả location file lẫn URL. Bổ sung `evidence_for_finding` vào `evidence.py` và tích hợp vào `packet_builder.py` để trích xuất bằng chứng động từ chính ZAP alert. Toàn bộ 7/7 unit tests mới pass 100%, 178 analysis tests pass, 901 offline tests xanh và validation 21 analysis records lịch sử thành công 100%.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Chuẩn hoá hợp đồng dữ liệu cho các phát hiện DAST (vốn không có file và line trong mã nguồn mà chỉ có URL và HTTP method/param), đồng thời áp dụng cơ chế xác thực provenance chống hallucination của LLM đối với các URL này.
- **Nằm ở đâu trong luồng:** Tại schema validation `schemas/security-analysis-record.schema.json`, module xác thực `analysis/validators.py`, và module trích xuất bằng chứng `analysis/evidence.py` / `analysis/packet_builder.py`.
- **Không có nó thì hỏng gì:** LLM khi phân tích finding DAST sẽ bị Schema Validator hoặc Provenance Validator từ chối vì không có cặp `file`/`line`, hoặc LLM có thể tự bịa (hallucinate) ra URL không có trong input mà không bị bắt.
- **Ngoài phạm vi (cố ý không làm):** Chưa chạy benchmark nghiệm thu tổng thể và tạo báo cáo metrics DAST (nội dung Task 9).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `schemas/security-analysis-record.schema.json` | Sửa | Cập nhật `locations.items` thành `oneOf` hỗ trợ `{file, line}` hoặc `{url, method?, param?}` | Hợp đồng schema cho finding DAST |
| `src/project_sentinel/analysis/validators.py` | Sửa | Kiểm tra provenance cho cả `file_locs` lẫn `url_locs` theo hai chiều (không bịa, không bỏ rơi) | Ngăn ngừa hallucination URL |
| `src/project_sentinel/analysis/evidence.py` | Sửa | Thêm `_dast_evidence` và `evidence_for_finding`, cho phép `start_line >= 0` | Trích xuất snippet bằng chứng DAST |
| `src/project_sentinel/analysis/packet_builder.py` | Sửa | Sử dụng `evidence_for_finding` cho từng finding trong group | Gói bằng chứng DAST vào LLM prompt packet |
| `tests/unit/analysis/test_url_locations.py` | Tạo | 4 unit test kiểm tra schema `oneOf` và provenance URL | Bộ kiểm chứng TDD URL |
| `tests/unit/analysis/test_dast_evidence.py` | Tạo | 3 unit test kiểm tra routing bằng chứng tĩnh vs DAST | Bộ kiểm chứng TDD evidence |

**`git diff --stat`:**

```text
 schemas/security-analysis-record.schema.json     | 47 +++++++++++++-----
 src/project_sentinel/analysis/evidence.py        | 57 +++++++++++++++++++++-
 src/project_sentinel/analysis/packet_builder.py  | 68 +++++++++++++++++++------
 src/project_sentinel/analysis/validators.py      | 16 +++++-
 tests/unit/analysis/test_dast_evidence.py       | 38 +++++++++++++++
 tests/unit/analysis/test_url_locations.py        | 52 ++++++++++++++++++++
 6 files changed, 246 insertions(+), 32 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
- Schema: Dùng `oneOf` ở cấp item của mảng `locations`, đảm bảo mỗi item phải thoả mãn đầy đủ thuộc tính bắt buộc của một trong hai nhánh (`{file, line}` hoặc `{url}`).
- Provenance Validator: Tách tập hợp location đầu vào và đầu ra thành `input_file_locs` / `input_urls` và `rec_file_locs` / `rec_urls`. Kiểm tra hiệu số hai chiều: mọi URL trong output phải nằm trong input, và ngược lại không được bỏ sót URL nào của input group.
- Evidence Router: Hàm `evidence_for_finding` kiểm tra nếu finding có `line > 0` và không phải URL thì đi qua hàm `extract_source_window` cũ (bảo toàn 100% logic cho SAST). Nếu finding là ZAP hoặc URL, hàm sinh `SourceEvidence` tổng hợp tên alert, tổng số instance bị ảnh hưởng và danh sách method/URL/param.

**Luồng dữ liệu:**
`FindingGroup` $\rightarrow$ `packet_builder.py` $\rightarrow$ `evidence_for_finding` $\rightarrow$ `AnalysisPacket` $\rightarrow$ LLM $\rightarrow$ `validate_record_schema` $\rightarrow$ `validate_provenance` (kiểm tra cả file và url) $\rightarrow$ `calibrate_record`.

**Xử lý lỗi / trường hợp biên:**
- Finding DAST không có instance $\rightarrow$ trả về `SourceEvidence` có trường `error` ghi nhận rõ lý do.
- URL lạ hoặc bịa đặt $\rightarrow$ `validate_provenance` trả về `(False, ["Invented URL location..."])`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Schema | `locations.items` | `schemas/security-analysis-record.schema.json` | Cho phép vị trí dạng URL |
| Hàm | `evidence_for_finding` | `(finding, *, project_root, target_root, radius=4) -> SourceEvidence` | Điều phối bằng chứng theo tool |
| Hàm | `_dast_evidence` | `(finding: dict) -> SourceEvidence` | Tạo bằng chứng cho alert ZAP |
| Test | `test_url_locations.py` | `tests/unit/analysis/test_url_locations.py` | 4 unit test cho provenance URL |
| Test | `test_dast_evidence.py` | `tests/unit/analysis/test_dast_evidence.py` | 3 unit test cho evidence routing |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/analysis/test_url_locations.py tests/unit/analysis/test_dast_evidence.py -v
```

**Output thật:**

```text
============================= test session starts ==============================
collected 7 items

tests/unit/analysis/test_url_locations.py::test_schema_allows_both_location_shapes PASSED [ 14%]
tests/unit/analysis/test_url_locations.py::test_a_url_the_agent_invented_is_rejected PASSED [ 28%]
tests/unit/analysis/test_url_locations.py::test_a_url_present_in_the_input_is_accepted PASSED [ 42%]
tests/unit/analysis/test_url_locations.py::test_a_url_from_an_instance_is_accepted PASSED [ 57%]
tests/unit/analysis/test_dast_evidence.py::test_static_finding_takes_the_unchanged_source_path PASSED [ 71%]
tests/unit/analysis/test_dast_evidence.py::test_dast_finding_uses_its_own_alert_content PASSED [ 85%]
tests/unit/analysis/test_dast_evidence.py::test_line_zero_is_not_treated_as_a_source_location PASSED [100%]

============================== 7 passed in 0.12s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Mở rộng schema dạng `oneOf` và thêm hàm điều phối `evidence_for_finding` bọc ngoài `extract_source_window`.

**Lý do:**
- Giữ nguyên vẹn 100% hành vi và các bài test của `extract_source_window` đối với các finding mã nguồn tĩnh.
- Thực hiện kiểm tra provenance nghiêm ngặt hai chiều cho URL giống hệt như với file/line, loại bỏ hoàn toàn khả năng Agent hallucinate ra các endpoint không tồn tại.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_url_locations.py tests/unit/analysis/test_dast_evidence.py -v` | 0 | 7 passed |
| `make validate-analysis` | 0 | Validated 21 analysis records successfully |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 901 passed, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |

**Bất biến đã giữ:**
- Không thay đổi bất kỳ hành vi nào của luồng trích xuất source code cũ cho SAST.
- Mọi record lịch sử đều tiếp tục vượt qua schema validation hiện tại.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Finding ZAP luôn có `line == 0` và `tool == "zap"`.
- **Việc còn nợ:** Task 9: Chạy benchmark nghiệm thu toàn diện và xuất báo cáo metrics DAST.
