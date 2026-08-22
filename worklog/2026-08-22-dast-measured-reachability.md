# Worklog — Ghi đè reachability bằng phép đo runtime thực tế

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 6`

---

## 1. Tóm tắt

Đã cập nhật module `analysis/calibration.py` để nhận `measured_reachability` và ghi đè lời khai `reachability` của Agent bằng phép đo động thực tế từ `correlation.py`. Khi có sự khác biệt giữa phép đo và lời khai, luật `reachability_measured` được ghi nhận trong vết `calibration`. Đồng thời cập nhật docstring nguyên tắc bất biến để phản ánh việc phép đo có thể nâng `reachability` một cách khách quan. Toàn bộ 7/7 unit test mới pass 100%, 26/26 tests calibration pass và bảo toàn 890 tests offline.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Thay thế trường `reachability` do LLM tự suy luận (có nguy cơ bịa đặt) bằng kết quả đo lường thực nghiệm khách quan từ việc ZAP có chạm được tới route tương ứng hay không.
- **Nằm ở đâu trong luồng:** Tại bước hiệu chỉnh `analysis/calibration.py`, được gọi ngay sau bước LLM hoàn tất phân tích nhóm finding trong `pipeline.py`.
- **Không có nó thì hỏng gì:** Kết luận của hệ thống về khả năng tiếp cận (`reachability`) vẫn hoàn toàn là "lời khai" chủ quan của Agent thay vì bằng chứng thực nghiệm đã đo được từ hạ tầng mạng.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp câu lệnh DAST vào CLI orchestrator 9 bước (nội dung Task 7).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/calibration.py` | Sửa | Thêm `measured_reachability`, luật `reachability_measured`, cập nhật docstring bất biến | Logic hiệu chỉnh theo phép đo |
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Trích xuất `measured_reachability` từ group và truyền vào `calibrate_record` | Tích hợp vào luồng chạy phân tích |
| `src/project_sentinel/models.py` | Sửa | Bổ sung trường `runtime_evidence` vào `NormalizedFinding` | Giữ bằng chứng runtime trong dataclass |
| `tests/unit/analysis/test_calibration_measured.py` | Tạo | 7 unit test kiểm tra ghi đè reachability, contradiction downward, invalid values, equal values | Bộ kiểm chứng TDD |

**`git diff --stat`:**

```text
 src/project_sentinel/analysis/calibration.py        | 21 +++++++++++++++++----
 src/project_sentinel/analysis/pipeline.py           | 40 +++++++++++++++++++++++++++++++++-------
 src/project_sentinel/models.py                      |  5 ++++-
 tests/unit/analysis/test_calibration_measured.py    | 65 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 119 insertions(+), 12 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
Khi `pipeline.py` nhận kết quả phân tích từ LLM, hàm `_extract_measured_reachability` kiểm tra các finding cấu thành nhóm.
Nếu finding có `strength` là `"reachable"` hoặc `"reachable_and_alerted"`, `measured_reachability` là `"proven"`.
Nếu `strength` là `"route_known_not_reached"`, `measured_reachability` là `"not_proven"`.
Nếu không xác định được route (`"no_route"`), trả về `None` để giữ nguyên phán đoán của Agent.

**Luồng dữ liệu:**
Finding SAST có `runtime_evidence` $\rightarrow$ `_extract_measured_reachability` $\rightarrow$ `calibrate_record(record_dict, measured_reachability=...)` $\rightarrow$ Ghi đè `reachability` và thêm rule `reachability_measured` vào `record["calibration"]`.

**Các quyết định kỹ thuật:**
- `measured_reachability` là keyword-only argument với giá trị mặc định là `None`, đảm bảo mọi lời gọi cũ không truyền tham số này vẫn giữ nguyên vẹn 100% hành vi ban đầu.
- Sửa docstring nguyên tắc bất biến: làm rõ rằng việc nâng `reachability` dựa trên phép đo hạ tầng mạng không vi phạm nguyên tắc "chỉ hạ dựa trên văn xuôi của Agent", mà là thay thế một lời khai chủ quan bằng một phép đo khách quan.

**Xử lý lỗi / trường hợp biên:**
- Giá trị `measured_reachability` không nằm trong `PROOF_VALUES` (ví dụ chuỗi lạ) sẽ bị bỏ qua an toàn mà không làm lỗi record.
- Nếu giá trị đo được trùng với giá trị Agent đã khai, không sinh ra rule `reachability_measured` thừa.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `calibrate_record` | `calibrate_record(record, *, measured_reachability=None)` | Hiệu chỉnh kèm phép đo reachability |
| Test | `test_calibration_measured.py` | `tests/unit/analysis/test_calibration_measured.py` | 7 unit test cho phép đo reachability |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/analysis/test_calibration_measured.py -v
```

**Output thật:**

```text
============================= test session starts ==============================
collected 7 items

tests/unit/analysis/test_calibration_measured.py::test_without_a_measurement_nothing_changes PASSED [ 14%]
tests/unit/analysis/test_calibration_measured.py::test_a_measurement_overwrites_what_the_agent_claimed PASSED [ 28%]
tests/unit/analysis/test_calibration_measured.py::test_measurement_can_contradict_the_agent_downward PASSED [ 42%]
tests/unit/analysis/test_calibration_measured.py::test_confirmed_survives_when_both_proofs_hold PASSED [ 57%]
tests/unit/analysis/test_calibration_measured.py::test_confirmed_still_falls_when_attacker_control_is_missing PASSED [ 71%]
tests/unit/analysis/test_calibration_measured.py::test_an_invalid_measurement_is_ignored PASSED [ 85%]
tests/unit/analysis/test_calibration_measured.py::test_a_measurement_equal_to_the_claim_leaves_no_trace PASSED [100%]

============================== 7 passed in 0.03s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Ghi đè `reachability` trong `calibrate_record` trước khi các quy tắc hạ cấp (`confirmed_requires_proof`, `severity_ceiling`) được đánh giá.

**Lý do:**
- Giúp quy tắc `confirmed_requires_proof` kiểm tra trên giá trị `reachability` đã được chuẩn hoá theo phép đo thực tế thay vì giá trị cũ.
- Tách biệt rõ ràng giữa hai khái niệm: `reachability` (đo được bằng DAST spider) và `attacker_control` (vẫn cần SAST / phân tích code).

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Bắt Agent tự đọc access log trong prompt | Agent có thể tự điều chỉnh | Lãng phí token, Agent có thể tiếp tục hallucinate hoặc bỏ qua dữ liệu log |
| Sửa reachability sau khi calibration hoàn tất | Không đụng vào code calibration | Làm sai lệch quy tắc `confirmed_requires_proof` (đòi hỏi cả attacker_control và reachability cùng proven) |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_calibration_measured.py -v` | 0 | 7 passed |
| `.venv/bin/python -m pytest tests/unit/analysis -v -k calibration` | 0 | 26 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 890 passed, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |

**Bất biến đã giữ:**
- Mọi test calibration cũ giữ nguyên vẹn 100% (26/26 passed).
- DAST chỉ chứng minh reachability, KHÔNG chứng minh attacker_control (`confirmed` vẫn rơi xuống `needs_review` nếu thiếu attacker_control).

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Quy tắc mapping: nhóm có cả finding `reachable` và `no_route` thì lấy `proven` theo nguyên tắc mức cao nhất tìm thấy.
- **Giả định đã đặt:** `source_finding_ids` trong record của Agent chứa đúng ID của các finding trong group.
- **Việc còn nợ:** Task 7: Tích hợp DAST vào context và bước ingest của Orchestrator.
