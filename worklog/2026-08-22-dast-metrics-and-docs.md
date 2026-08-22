# Worklog — Số liệu tách theo công cụ và đồng bộ tài liệu

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** [`docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md`](../docs/superpowers/plans/2026-08-22-dast-zap-authenticated.md) · **Task ID:** `Task 9`

---

## 1. Tóm tắt

Đã hoàn thành Task 9 và nghiệm thu toàn diện kế hoạch DAST có phiên đăng nhập:
1. Cập nhật `src/project_sentinel/orchestrator/metrics.py` phân tách rõ số lượng finding theo công cụ (`findings_by_tool`) và bổ sung nhóm chỉ số `dast` (`endpoints_discovered`, `alerts_total`, `instances_total`).
2. Đồng bộ toàn bộ tài liệu dự án (`docs/architecture.md`, `docs/limitations.md`, `docs/target-webgoat.md`, `README.md`, `docs/demo-script.md`) phản ánh chính xác kiến trúc DAST qua Gateway có phiên đăng nhập, việc đo lường reachability tự động bằng Python, các ranh giới và giới hạn an toàn.
3. Fix lỗi biến môi trường `SENTINEL_DAST_SESSION` mặc định rỗng trong Docker Gateway để đảm bảo lane Agent hoạt động bình thường khi chạy độc lập.
4. Nghiệm thu toàn diện: 903 offline tests pass, 23/23 live Gateway policy tests pass, 5/5 live ZAP DAST tests pass, và 35/35 doc honesty tests pass.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Xuất bản các chỉ số định lượng chi tiết cho đợt quét DAST và đồng bộ tài liệu kiến trúc, vận hành, giới hạn và demo script của toàn bộ dự án.
- **Nằm ở đâu trong luồng:** Tại module thu thập chỉ số `orchestrator/metrics.py` (bước 9 `finalize`), cùng toàn bộ tài liệu kỹ thuật trong `docs/` và `README.md`.
- **Không có nó thì hỏng gì:** Các báo cáo và chỉ số metrics sẽ gộp chung số lượng finding OpenGrep và ZAP (vốn có độ mịn khác nhau) gây hiểu nhầm; tài liệu kỹ thuật sẽ lệch pha so với hành vi thực tế của hệ thống.
- **Ngoài phạm vi (cố ý không làm):** Không sửa logic trích xuất của các bước phân tích khác.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/orchestrator/metrics.py` | Sửa | Thêm `findings_by_tool` và khối `dast` (`endpoints_discovered`, `alerts_total`, `instances_total`) | Thu thập số liệu phân tách theo công cụ |
| `tests/unit/orchestrator/test_metrics_dast.py` | Tạo | 2 unit test cho `collect_metrics` khi có DAST và không có DAST | Bộ kiểm chứng TDD metrics |
| `docs/architecture.md` | Sửa | Cập nhật bước scan, sơ đồ vùng DAST session, reachability calibration, và cây artifact | Đồng bộ tài liệu kiến trúc |
| `docs/limitations.md` | Sửa | Ghi rõ các hạn chế kỹ thuật của baseline DAST, single session, và phân tích route Spring | Trung thực về giới hạn hệ thống |
| `docs/target-webgoat.md` | Sửa | Giải thích bề mặt `permitAll` và cơ chế tiêm phiên đăng nhập của Gateway | Hướng dẫn target WebGoat |
| `README.md` | Sửa | Cập nhật flowchart mermaid, sơ đồ 9 bước và lệnh DAST | Tài liệu trang chủ |
| `docs/demo-script.md` | Sửa | Thêm nội dung DAST và số liệu phân tách vào kịch bản demo 15 phút | Kịch bản thuyết trình |
| `infra/docker/gateway/Dockerfile` & `16-acquire-dast-session.envsh` | Sửa | Đặt mặc định `ENV SENTINEL_DAST_SESSION=""` | Tránh lỗi envsubst khi chạy mode probe |
| `tests/integration/test_zap_gateway_live.py` | Sửa | Cập nhật assertion khớp với log format có trường `query` | Đồng bộ test live log format |

**`git diff --stat`:**

```text
 README.md                                          |  7 ++--
 docs/architecture.md                               | 45 ++++++++++++++--------
 docs/demo-script.md                                |  7 ++--
 docs/limitations.md                                | 19 +++++----
 docs/target-webgoat.md                             |  7 ++++
 infra/docker/gateway/Dockerfile                    |  2 +
 .../16-acquire-dast-session.envsh                  |  3 ++
 src/project_sentinel/orchestrator/metrics.py       | 24 ++++++++++++
 tests/integration/test_zap_gateway_live.py         |  4 +-
 tests/unit/orchestrator/test_metrics_dast.py       | 52 ++++++++++++++++++++
 10 files changed, 140 insertions(+), 30 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
- Khi thu thập metrics, duyệt qua toàn bộ `findings` trong `findings.json` và phân loại theo trường `tool`. Đối với tool `zap`, đếm số loại alert và tổng số `instances_total`.
- Đọc `gateway-access.log` qua `parse_gateway_access_log` để đếm số endpoint duy nhất đã được phát hiện trong lần quét.
- Nếu không có DAST, trả về các giá trị `0` đầy đủ trong khối `dast` thay vì thiếu key, đảm bảo tính nhất quán của schema `metrics.json`.
- Cập nhật đồng bộ và trung thực mọi tài liệu hướng dẫn và phân tích giới hạn.

**Luồng dữ liệu:**
`findings.json` + `gateway-access.log` $\rightarrow$ `collect_metrics` $\rightarrow$ `metrics.json`.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Hàm | `collect_metrics` | `src/project_sentinel/orchestrator/metrics.py` | Trả về `findings_by_tool` và khối `dast` |
| Test | `test_metrics_dast.py` | `tests/unit/orchestrator/test_metrics_dast.py` | 2 unit test cho metrics DAST |

**Cách chạy:**

```bash
.venv/bin/python -m pytest tests/unit/orchestrator/test_metrics_dast.py -v
```

**Output thật:**

```text
============================= test session starts ==============================
collected 2 items

tests/unit/orchestrator/test_metrics_dast.py::test_findings_are_counted_per_tool PASSED [ 50%]
tests/unit/orchestrator/test_metrics_dast.py::test_a_run_without_dast_reports_zeros_not_missing_keys PASSED [100%]

============================== 2 passed in 0.12s ===============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Phân tách rõ `findings_by_tool` và khối `dast` riêng biệt trong `metrics.json`.

**Lý do:**
- Finding SAST (OpenGrep) tính theo từng vị trí dòng mã nguồn (fine-grained), trong khi finding DAST (ZAP) được gộp theo loại alert (coarse-grained). Nếu chỉ dùng một con số `findings_total`, số liệu sẽ không phản ánh đúng bản chất dữ liệu.
- Tài liệu trung thực làm rõ ranh giới giữa baseline scanning và active exploitation giúp người sử dụng hiểu đúng phạm vi của công cụ.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/orchestrator/test_metrics_dast.py -v` | 0 | 2 passed |
| `.venv/bin/python -m pytest tests/unit/infra/test_docs_complete.py tests/test_docs_are_honest.py -v` | 0 | 35 passed |
| `make lint && make typecheck` | 0 | All checks passed, 0 errors |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | 903 passed, 38 deselected |
| `make dast-test` | 0 | 5 live ZAP & Gateway integration tests passed |
| `make gateway-live-test` | 0 | 23 live Gateway policy tests passed |
| `make agent-test` | 0 | 903 passed, 38 deselected |

**Bất biến đã giữ:**
- Zero mock / stub trong các bài test tích hợp live.
- `JSESSIONID` không xuất hiện trong bất kỳ log hoặc báo cáo nào.
- Toàn bộ 9 task hoàn thành tuần tự, độc lập và đã kiểm chứng xanh 100%.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Môi trường production nếu chạy DAST phải có Docker Engine hỗ trợ Docker Compose v2.
- **Việc còn nợ:** Toàn bộ 9 task trong kế hoạch đã hoàn thành trọn vẹn.
