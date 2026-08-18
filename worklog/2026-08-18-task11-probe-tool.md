# Worklog — Task 11: `probe/tool.py` — đường gửi request duy nhất của pipeline

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/probe-tool` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 11

---

## 1. Tóm tắt

- Triển khai `src/project_sentinel/probe/tool.py` đóng vai trò là kênh duy nhất gửi request kiểm thử bảo mật (probe) từ hệ thống tới API Gateway (:9080) một cách an toàn và có kiểm soát.
- Tách các cấu trúc dữ liệu HTTP transport (`HttpRequest`, `HttpResponse`) vào `src/project_sentinel/probe/http_models.py`, di chuyển `transport.py` và `rate_limit.py` từ package cũ `verification/` sang package mới `probe/`, đồng thời thêm compatibility shims tại `verification/` để duy trì tương thích cho đến khi Task 12 xoá hẳn package này.
- Hàm `send_probe(...)` thực thi luồng kiểm soát: kiểm tra `Allowlist` (từ chối ngay trước khi mở kết nối mạng), xác thực kiểu `payload_kind`, chờ rate limit (`ToolRateLimiter`), tiêm header `X-Sentinel-API-Key`, serialize payload, gửi qua `RealTransport`, cắt preview tối đa 512 bytes và ghi log audit JSONL bảo mật (tuyệt đối không ghi API key).
- Kiểm chứng thực tế: 20/20 bài kiểm thử unit trong `tests/unit/probe/` đạt trạng thái xanh (100% passed), dây bẫy `_NeverCalledTransport` chứng minh bằng đột biến rằng không request bị chặn nào chạm tới transport.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Là thành phần thực thi probe duy nhất của Project Sentinel, thay thế toàn bộ logic phức tạp cũ của `gateway_client.py` + `policy.py` + `templates.py`.
- **Nằm ở đâu trong luồng:** 
  - Đứng sau bước đề xuất và phê duyệt probe (`probe/proposal.py`).
  - Là mắt xích cuối cùng tiếp xúc với mạng ngoài qua loopback Gateway `http://127.0.0.1:9080`.
- **Không có nó thì hỏng gì:** Pipeline không có cách nào gửi probe tới Gateway an toàn hoặc sẽ bị phân tán rải rác các lời gọi mạng không qua kiểm soát allowlist/rate limit.
- **Ngoài phạm vi (cố ý không làm):** Task 11 không xoá toàn bộ `verification/` (được thực hiện ở Task 12) mà chỉ di chuyển `transport.py` và `rate_limit.py` sang `probe/` kèm shims tương thích tạm thời.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/probe/http_models.py` | Tạo mới | Định nghĩa dataclass `HttpRequest` và `HttpResponse` | Tách rời model transport khỏi package cũ `verification/` |
| `src/project_sentinel/probe/transport.py` | Tạo mới (di chuyển) | Di chuyển từ `verification/transport.py`, sửa import sang `.http_models` | Đặt transport vào đúng package probe mới |
| `src/project_sentinel/probe/rate_limit.py` | Tạo mới (di chuyển) | Di chuyển từ `verification/rate_limit.py` | Đặt rate limiter vào đúng package probe mới |
| `src/project_sentinel/probe/tool.py` | Tạo mới | Triển khai `GATEWAY_ORIGIN`, `ProbeOutcome`, kiểm tra `payload_kind`, `_preview()`, và `send_probe()` | Deliverable chính của Task 11 |
| `src/project_sentinel/verification/rate_limit.py` | Sửa (shim) | Re-export `ToolRateLimiter` từ `probe.rate_limit` | Giữ tương thích ngược cho tests cũ trước khi Task 12 xoá |
| `src/project_sentinel/verification/transport.py` | Sửa (shim) | Re-export `BaseTransport`, `RealTransport` từ `probe.transport` | Giữ tương thích ngược cho tests cũ trước khi Task 12 xoá |
| `tests/unit/probe/test_tool.py` | Tạo mới | 7 test cases kèm dây bẫy `_NeverCalledTransport` kiểm thử: loopback origin, chặn allowlist, audit log khi denied, secret redaction, payload rác | Bộ kiểm thử tự động cho `probe/tool.py` |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành Task 11 Step 1 → 7 | Cập nhật tiến độ kế hoạch tổng thể |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md |  14 +-
 src/project_sentinel/probe/http_models.py                 |  27 ++++
 src/project_sentinel/probe/rate_limit.py                  |  40 +++++
 src/project_sentinel/probe/tool.py                        | 139 ++++++++++++++++
 src/project_sentinel/probe/transport.py                   | 171 ++++++++++++++++++++
 src/project_sentinel/verification/rate_limit.py           |  42 +----
 src/project_sentinel/verification/transport.py            | 179 +--------------------
 tests/unit/probe/test_tool.py                             |  93 +++++++++++
 worklog/2026-08-18-task11-probe-tool.md                   | 157 ++++++++++++++++++
 9 files changed, 644 insertions(+), 218 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Khởi tạo `tests/unit/probe/test_tool.py` với 7 test cases và dây bẫy `_NeverCalledTransport` (kế thừa `BaseTransport`, ném `AssertionError` nếu bị gọi) kiểm thử:
   - Nguồn loopback duy nhất (`GATEWAY_ORIGIN = "http://127.0.0.1:9080"`).
   - Chặn endpoint ngoài allowlist trước khi chạm transport.
   - Ghi log audit đầy đủ với `policy_decision: "DENIED"` khi bị chặn.
   - Xác nhận API key tuyệt đối không bao giờ lọt vào audit log.
   - Chặn các giá trị `payload_kind` không hợp lệ (`['khong-ton-tai', 123, ['long_string']]`) ngay cả khi path hợp lệ.
2. Chạy `pytest` xác nhận thất bại `ModuleNotFoundError: No module named 'project_sentinel.probe.tool'` (TDD Red).
3. Tạo `src/project_sentinel/probe/http_models.py` với `HttpRequest` và `HttpResponse`.
4. Di chuyển `transport.py` và `rate_limit.py` sang `src/project_sentinel/probe/`, cập nhật import `.http_models`, đồng thời viết shims re-export tại `verification/rate_limit.py` và `verification/transport.py`.
5. Triển khai `src/project_sentinel/probe/tool.py`:
   - `GATEWAY_ORIGIN = "http://127.0.0.1:9080"`.
   - `ProbeOutcome`: frozen dataclass chứa kết quả và lý do từ chối.
   - `_preview()`: cắt ngắn preview tối đa 512 bytes.
   - `send_probe()`:
     - Kiểm tra `allowlist.is_allowed(probe.method, probe.path)` -> nếu vi phạm, ghi log `status="DENIED"`, `policy_decision="DENIED"` và trả `ProbeOutcome(sent=False, denied_reason=...)` ngay lập tức.
     - Kiểm tra `isinstance(probe.payload_kind, str)` và `probe.payload_kind in PAYLOAD_KIND_TO_TYPE` -> nếu không hợp lệ, ghi log `error_class="InvalidPayloadKind"`, `policy_decision="DENIED"` và trả `ProbeOutcome(sent=False)`.
     - Áp dụng rate limit qua `limiter.wait()`.
     - Gửi request qua `active_transport.send_request()` với header `X-Sentinel-API-Key: api_key`.
     - Ghi nhận audit log với `policy_decision="ALLOWED"` và trả `ProbeOutcome`.
6. Chạy `pytest tests/unit/probe/ -v` xác nhận 20/20 test cases xanh (TDD Green).

---

## 5. Output là gì

**Thành phần mới:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Module | `http_models.py` | `src/project_sentinel/probe/http_models.py` | Dataclass `HttpRequest`, `HttpResponse` |
| Module | `tool.py` | `src/project_sentinel/probe/tool.py` | Cổng gửi request probe duy nhất của pipeline |
| Hằng | `GATEWAY_ORIGIN` | `"http://127.0.0.1:9080"` | Loopback host origin của Gateway |
| Dataclass | `ProbeOutcome` | `ProbeOutcome(sent, status_code, body_preview, ...)` | Cấu trúc dữ liệu kết quả probe |
| Hàm | `send_probe` | `send_probe(probe, allowlist, api_key, *, transport=None, rate_limiter=None, log_path=...) -> ProbeOutcome` | Hàm gửi probe có kiểm soát chính sách |
| Test suite | `test_tool.py` | `tests/unit/probe/test_tool.py` | 7 test cases kiểm thử `send_probe` và audit logging |

**Cách chạy:**

```bash
python -m pytest tests/unit/probe/ -v
```

**Output thật:**

```text
$ .venv/bin/python -m pytest tests/unit/probe/ -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/longngx04/VinSOC/project_sentinel_main/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
plugins: respx-0.23.1, xdist-3.8.0, anyio-4.14.2
collecting ... collected 20 items                                                             

tests/unit/probe/test_proposal.py::test_four_payload_kinds_are_mapped PASSED [  5%]
tests/unit/probe/test_proposal.py::test_allowlisted_objective_is_accepted PASSED [ 10%]
tests/unit/probe/test_proposal.py::test_null_objective_is_rejected_without_error PASSED [ 15%]
tests/unit/probe/test_proposal.py::test_endpoint_outside_allowlist_is_rejected PASSED [ 20%]
tests/unit/probe/test_proposal.py::test_absolute_url_is_rejected PASSED  [ 25%]
tests/unit/probe/test_proposal.py::test_method_not_allowed_for_that_path_is_rejected PASSED [ 30%]
tests/unit/probe/test_proposal.py::test_unknown_payload_kind_is_rejected PASSED [ 35%]
tests/unit/probe/test_proposal.py::test_malformed_hint_is_rejected PASSED [ 40%]
tests/unit/probe/test_proposal.py::test_query_string_in_hint_is_rejected PASSED [ 45%]
tests/unit/probe/test_proposal.py::test_missing_required_field_is_rejected PASSED [ 50%]
tests/unit/probe/test_proposal.py::test_non_string_payload_kind_is_rejected PASSED [ 55%]
tests/unit/probe/test_proposal.py::test_non_dict_objective_is_rejected PASSED [ 60%]
tests/unit/probe/test_proposal.py::test_non_string_endpoint_hint_is_rejected PASSED [ 65%]
tests/unit/probe/test_tool.py::test_gateway_origin_is_loopback_only PASSED [ 70%]
tests/unit/probe/test_tool.py::test_probe_outside_allowlist_is_denied_before_any_transport PASSED [ 75%]
tests/unit/probe/test_tool.py::test_denied_probe_is_still_written_to_the_audit_log PASSED [ 80%]
tests/unit/probe/test_tool.py::test_api_key_never_reaches_the_audit_log PASSED [ 85%]
tests/unit/probe/test_tool.py::test_invalid_payload_kind_is_denied_before_transport[khong-ton-tai] PASSED [ 90%]
tests/unit/probe/test_tool.py::test_invalid_payload_kind_is_denied_before_transport[123] PASSED [ 95%]
tests/unit/probe/test_tool.py::test_invalid_payload_kind_is_denied_before_transport[junk_payload_kind2] PASSED [100%]

============================== 20 passed in 0.04s ==============================
```

---

## 6. Vì sao chọn cách implement này

- **Kiểm soát ranh giới mạng nghiêm ngặt (Single egress point):** Gom toàn bộ trách nhiệm kiểm tra allowlist, xác thực payload, áp dụng rate limit, và audit log vào một hàm duy nhất `send_probe()`. Không có bất kỳ thành phần nào khác được tự ý mở kết nối mạng.
- **Fail-closed trước transport:** Nếu endpoint/method hoặc payload không hợp lệ, hàm từ chối ngay lập tức mà không bao giờ khởi tạo hay gọi phương thức `transport.send_request()`. Dây bẫy `_NeverCalledTransport` chứng minh transport không bị đụng tới.
- **Bảo mật audit log (Zero secret leakage):** `log_request` chỉ nhận các trường metadata đã duyệt trong `AUDIT_FIELD_NAMES`, loại trừ hoàn toàn các trường nhạy cảm như header auth hay API key.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `python -m pytest tests/unit/probe -v` | 0 | 20 passed (100%) |
| `python -m pytest -m "not llm and not live_gateway" -q` | 1 | 210 passed, 22 Docker errors (đúng kỳ vọng khi container chưa bật) |
| `python3 -m compileall -q src/project_sentinel/probe` | 0 | PASSED |

**Chứng minh dây bẫy `_NeverCalledTransport` hoạt động:**

1. Khi tạm đổi dòng kiểm tra allowlist thành `if False:` trong `probe/tool.py`:
```text
$ pytest tests/unit/probe/test_tool.py -q
.FFF...                                                                  [100%]
=================================== FAILURES ===================================
_________ test_probe_outside_allowlist_is_denied_before_any_transport __________
...
E       AssertionError: Transport bị gọi cho request lẽ ra phải bị chặn: GET http://127.0.0.1:9080/WebGoat/admin

tests/unit/probe/test_tool.py:20: AssertionError
3 failed, 4 passed in 0.09s
```
*(Bắt chính xác lỗi qua AssertionError từ `_NeverCalledTransport`, không có kết nối thật nào được mở).*

2. Khi trả lại nguyên trạng:
```text
$ pytest tests/unit/probe/test_tool.py -q
.......                                                                  [100%]
7 passed in 0.02s
```

**Bất biến đã giữ:** Không mock/stub trong transport/gateway, fail-closed ở allowlist và payload_kind, audit logging an toàn tuyệt đối.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Không có.
- **Giả định đã đặt:** Gateway chạy trên `http://127.0.0.1:9080` theo cấu hình loopback tiêu chuẩn.
- **Việc còn nợ:** Task 12 (Xoá hoàn toàn `verification/`, nối lệnh `probe` trong CLI và cập nhật test integration Gateway).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 11 lên nhánh `feat/probe-tool` ngay bây giờ không?
