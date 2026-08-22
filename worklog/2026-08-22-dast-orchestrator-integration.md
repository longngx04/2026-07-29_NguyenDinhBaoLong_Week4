# Worklog — Tích hợp DAST vào CLI orchestrator 9 bước

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 7`

---

## 1. Tóm tắt

Đã tích hợp DAST vào orchestrator chính của Project Sentinel: bổ sung `dast_command` vào `RunContext`, thực thi DAST song hành/hậu SAST trong `step_scan` (xử lý lỗi mềm, không chặn luồng SAST), cập nhật `scan-zap.sh` nhận output path linh hoạt, và trong `step_normalize` chuẩn hoá `cwe`/`owasp` thành list, trộn finding ZAP và thực hiện đối chiếu `correlate` với `gateway-access.log`. Toàn bộ 4/4 unit test mới pass 100%, 894 offline test suite xanh hoàn toàn.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Cho phép orchestrator tự động kích hoạt lần quét DAST khi môi trường sẵn sàng và đưa dữ liệu DAST vào luồng chuẩn hoá / đối chiếu của pipeline.
- **Nằm ở đâu trong luồng:** Tại `step_scan` (bước 1) và `step_normalize` (bước 2) trong `orchestrator/steps/ingest.py`.
- **Không có nó thì hỏng gì:** DAST chỉ chạy được bằng lệnh thủ công ngoài pipeline; orchestrator 9 bước sẽ thiếu vắng hoàn toàn các quan sát động và không sinh được bằng chứng runtime cho các bước sau.
- **Ngoài phạm vi (cố ý không làm):** Chưa sửa JSON Schema và Validator provenance cho URL (nội dung Task 8).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/context.py` | Sửa | Thêm `dast_command: list[str]` vào `RunContext` và `RunContext.default` | Tiêm cấu hình lệnh DAST |
| `scripts/scan-zap.sh` | Sửa | Nhận `$2` làm đường dẫn `gateway_log` | Cho phép orchestrator định tuyến log vào thư mục run |
| `src/project_sentinel/orchestrator/steps/ingest.py` | Sửa | Chạy DAST trong `step_scan`, chuẩn hoá cwe/owasp, trộn và correlate trong `step_normalize` | Luồng tích hợp DAST trong pipeline |
| `tests/unit/orchestrator/test_step_scan_dast.py` | Tạo | 4 unit test cho DAST done, DAST skip mềm, no DAST command, và `_normalise_finding_fields` | Bộ kiểm chứng TDD |

**`git diff --stat`:**

```text
 scripts/scan-zap.sh                               |   5 +-
 src/project_sentinel/orchestrator/context.py      |  22 +++++
 src/project_sentinel/orchestrator/steps/ingest.py | 109 +++++++++++++++++++++-
 tests/unit/orchestrator/test_step_scan_dast.py   |  78 ++++++++++++++++
 4 files changed, 208 insertions(+), 6 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
- SAST là xương sống bắt buộc, DAST là tùy chọn làm giàu dữ liệu. Do đó, nếu lệnh DAST thất bại (ví dụ máy host không có Docker), `step_scan` vẫn hoàn thành thành công và ghi nhận `detail["dast"] = "skipped"`.
- Trong `step_normalize`, nếu có `zap-alerts.json`, hệ thống chuẩn hoá nó bằng `run_normalize`, trộn vào file trung gian `.findings.merged.json` rồi atomic replace `findings.json`.
- Ép kiểu toàn bộ trường `cwe` và `owasp` về `list[str]` thống nhất qua `_normalise_finding_fields`.
- Thực hiện `correlate` với `gateway-access.log` và ghi đè `runtime_evidence` vào danh sách finding.

**Luồng dữ liệu:**
`step_scan` $\rightarrow$ sinh `raw.json`, `zap-alerts.json`, `gateway-access.log` $\rightarrow$ `step_normalize` $\rightarrow$ chuẩn hoá OpenGrep + ZAP $\rightarrow$ `_normalise_finding_fields` $\rightarrow$ `correlate` $\rightarrow$ `findings.json`.

**Các quyết định kỹ thuật:**
- Không gọi `merge_files([target, zap], target)` trực tiếp trên cùng một file để tránh rủi ro đọc/ghi tranh chấp.
- Ghi nhận số lượng `correlated` trong `detail` của bước normalize để giám sát.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Trường | `dast_command` | `RunContext.dast_command: list[str]` | Cấu hình lệnh DAST trong context |
| Hàm | `_normalise_finding_fields` | `(findings: list[dict]) -> None` | Chuẩn hoá trường cwe/owasp về list |
| Test | `test_step_scan_dast.py` | `tests/unit/orchestrator/test_step_scan_dast.py` | 4 unit test cho DAST ingest |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_step_scan_dast.py -v
```

**Output thật:**

```text
============================= test session starts ==============================
collected 4 items

tests/unit/orchestrator/test_step_scan_dast.py::test_dast_success_is_recorded_as_done PASSED [ 25%]
tests/unit/orchestrator/test_step_scan_dast.py::test_dast_failure_does_not_fail_the_scan_step PASSED [ 50%]
tests/unit/orchestrator/test_step_scan_dast.py::test_no_dast_command_means_skipped_not_error PASSED [ 75%]
tests/unit/orchestrator/test_step_scan_dast.py::test_cwe_and_owasp_are_normalised_to_lists_after_merging PASSED [100%]

============================== 4 passed in 0.17s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Tích hợp DAST dạng pluggable song hành trong `step_scan` với cơ chế fallback skip mềm.

**Lý do:**
- Đảm bảo tính sẵn sàng của CI/CD và môi trường dev không có Docker: pipeline luôn hoàn thành phần SAST và phân tích mà không bị gián đoạn.
- Chuẩn hoá sớm định dạng `cwe`/`owasp` ngay sau bước trộn giúp đơn giản hoá toàn bộ các consumer phía sau (prompt generator, validator, UI exporter).

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/orchestrator/test_step_scan_dast.py -v` | 0 | 4 passed |
| `.venv/bin/python -m pytest tests/unit/infra/test_zap_scan_script.py -v` | 0 | 4 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 894 passed, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |

**Bất biến đã giữ:**
- Không chứa `http://webgoat:8080` trong `scan-zap.sh`.
- SAST thành công thì `step_scan` luôn thành công (`status="done"`), bất kể DAST `done` hay `skipped`.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Biến môi trường `SENTINEL_DAST_COMMAND` nếu được cấp phải trỏ tới file executable hợp lệ.
- **Việc còn nợ:** Task 8: Cập nhật JSON Schema và validator provenance cho finding URL.
