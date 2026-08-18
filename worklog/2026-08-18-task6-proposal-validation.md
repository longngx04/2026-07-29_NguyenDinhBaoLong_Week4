# Worklog — Task 6: probe/proposal.py — đối chiếu đề xuất với allowlist

**Ngày:** 2026-08-18 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/w1-w4-task6-proposal-validation` · **Plan:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md) · **Task ID:** Task 6

---

## 1. Tóm tắt

- Tạo package `project_sentinel.probe` với hai module cốt lõi: `payload_kinds.py` và `proposal.py`.
- Triển khai hàm guardrail an toàn `validate_objective(objective, allowlist)` trả về `ProposalDecision(accepted, probe, reason)` để kiểm tra chặt chẽ đề xuất kiểm chứng `verification_objective` từ LLM Agent.
- Thực thi kiểm tra cấu trúc nghiêm ngặt: kiểm tra `None` và `isinstance(objective, dict)`, kiểm tra các trường bắt buộc (`description`, `endpoint_hint`, `payload_kind`, `rationale`), kiểm tra kiểu chuỗi cho `payload_kind` (ngăn crash `TypeError: unhashable type`), kiểm tra định dạng `"<METHOD> <path>"`, phương thức `GET`/`POST`, đường dẫn tương đối không chứa query string, `payload_kind` thuộc 4 loại an toàn, và đối chiếu trực tiếp với `Allowlist.is_allowed(method, path)`.
- Kết quả: 13/13 unit tests mới trong `tests/unit/probe/test_proposal.py` pass, và 120/120 toàn bộ offline test suite xanh sạch.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đóng vai trò là chốt chặn bảo mật (Security Guardrail) ở phía backend để phân tích và chuẩn hóa đề xuất kiểm chứng động (`verification_objective`) do LLM sinh ra thành cấu trúc request an toàn (`SafeProbe`), ngăn chặn triệt để các hành vi ngoài ý muốn trước khi gửi bất kỳ request nào tới API Gateway.
- **Nằm ở đâu trong luồng:** 
  - Nằm ở module `src/project_sentinel/probe/`.
  - Được gọi sau khi LLM phản hồi kết quả phân tích và trước khi client thực thi kiểm thử an toàn qua Gateway (chuẩn bị cho Task 11).
- **Không có nó thì hỏng gì:** Nếu không có hàm xác thực này, hệ thống sẽ tin tưởng mù quáng vào output của LLM, có nguy cơ gửi các request tới endpoint ngoài ý muốn, URL độc hại bên ngoài, chuỗi query không kiểm soát, hoặc sử dụng payload ngoài 4 loại lành tính đã quy định.
- **Ngoài phạm vi (cố ý không làm):** Chưa thực hiện gửi HTTP request qua Gateway (phần gửi request an toàn qua Gateway sẽ do các task tiếp theo đảm nhiệm).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/probe/payload_kinds.py` | Tạo mới | Định nghĩa từ điển `PAYLOAD_KIND_TO_TYPE` và hàm `payload_value_for(kind)` | Ánh xạ tên loại payload sang `SafePayloadType` và lấy giá trị lành tính |
| `src/project_sentinel/probe/proposal.py` | Tạo mới | Định nghĩa dataclass `SafeProbe`, `ProposalDecision` và hàm `validate_objective()` kèm guard kiểu dữ liệu | Thực thi logic kiểm tra và kẹp chặt đề xuất của LLM vào allowlist |
| `src/project_sentinel/probe/__init__.py` | Tạo mới | Khởi tạo package và export các class, hàm chính | Cung cấp giao diện công khai gọn gàng cho package probe |
| `tests/unit/probe/__init__.py` | Tạo mới | Package marker cho probe unit tests | Khởi tạo namespace test |
| `tests/unit/probe/test_proposal.py` | Tạo mới | Viết 13 unit test cases kiểm thử đầy đủ các nhánh chấp nhận, từ chối và kiểu dữ liệu sai | Khóa chặt tính đúng đắn theo TDD |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md` | Sửa | Đánh dấu hoàn thành các checkbox Step 1 → Step 7 của Task 6 | Cập nhật tiến độ kế hoạch |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-1-w1-w4.md | 14 +++++------
 src/project_sentinel/probe/__init__.py                     | 19 +++++++++++++++
 src/project_sentinel/probe/payload_kinds.py               | 19 +++++++++++++++
 src/project_sentinel/probe/proposal.py                    | 70 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 tests/unit/probe/__init__.py                              |  0
 tests/unit/probe/test_proposal.py                         | 108 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 6 files changed, 223 insertions(+), 7 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:** 
1. Áp dụng quy trình TDD Red-Green:
   - Tạo trước `tests/unit/probe/test_proposal.py` với 13 test case bao phủ mọi kịch bản (kể cả kiểu dữ liệu sai, unhashable types).
   - Chạy test xác nhận FAIL với lỗi `ModuleNotFoundError: No module named 'project_sentinel.probe'`.
2. Tạo module `src/project_sentinel/probe/payload_kinds.py` kết nối với `gateway.models.SafePayloadType` và `gateway.payloads.SAFE_PAYLOADS`.
3. Tạo module `src/project_sentinel/probe/proposal.py` với quy trình kiểm tra tuần tự:
   - Kiểm tra `None` hoặc kiểu không phải `dict`.
   - Kiểm tra đầy đủ 4 trường bắt buộc (`description`, `endpoint_hint`, `payload_kind`, `rationale`).
   - Kiểm tra kiểu dữ liệu `isinstance(kind, str)` trước khi tra cứu `kind in PAYLOAD_KIND_TO_TYPE`.
   - Phân tách `endpoint_hint` thành `"<METHOD> <path>"`, bắt buộc đúng 2 token kiểu chuỗi.
   - Kiểm tra `method in {"GET", "POST"}`.
   - Kiểm tra `path.startswith("/")` và không chứa `?`.
   - Kiểm tra `allowlist.is_allowed(method, path)`.
   - Nếu thỏa mãn tất cả: trả về `ProposalDecision(accepted=True, probe=SafeProbe(...), reason=...)`.
4. Export các định danh qua `src/project_sentinel/probe/__init__.py`.
5. Chạy lại test suite xác nhận 13/13 tests chuyển sang PASS (Green).
6. Chạy toàn bộ offline test suite (`pytest -m "not llm"`) xác nhận không có regression.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Dataclass | `SafeProbe` | `SafeProbe(method: str, path: str, payload_kind: str | None)` | Cấu trúc probe an toàn sau khi validate |
| Dataclass | `ProposalDecision` | `ProposalDecision(accepted: bool, probe: SafeProbe | None, reason: str)` | Quyết định chấp nhận / từ chối đề xuất |
| Function | `validate_objective` | `validate_objective(objective: dict | None, allowlist: Allowlist) -> ProposalDecision` | Hàm đối chiếu đề xuất với allowlist |
| Function | `payload_value_for` | `payload_value_for(kind: str) -> Any` | Lấy giá trị payload thật từ allowlist payloads |
| File Test | `test_proposal.py` | `tests/unit/probe/test_proposal.py` | 13 unit test cases kiểm thử đề xuất |

**Cách chạy:**

```bash
pytest tests/unit/probe/test_proposal.py -v
pytest -m "not llm" tests/unit/probe -v
```

**Output thật:**

```text
$ pytest tests/unit/probe/test_proposal.py -v
============================== test session starts ==============================
collected 13 items

tests/unit/probe/test_proposal.py::test_four_payload_kinds_are_mapped PASSED [  7%]
tests/unit/probe/test_proposal.py::test_allowlisted_objective_is_accepted PASSED [ 15%]
tests/unit/probe/test_proposal.py::test_null_objective_is_rejected_without_error PASSED [ 23%]
tests/unit/probe/test_proposal.py::test_endpoint_outside_allowlist_is_rejected PASSED [ 30%]
tests/unit/probe/test_proposal.py::test_absolute_url_is_rejected PASSED  [ 38%]
tests/unit/probe/test_proposal.py::test_method_not_allowed_for_that_path_is_rejected PASSED [ 46%]
tests/unit/probe/test_proposal.py::test_unknown_payload_kind_is_rejected PASSED [ 53%]
tests/unit/probe/test_proposal.py::test_malformed_hint_is_rejected PASSED [ 61%]
tests/unit/probe/test_proposal.py::test_query_string_in_hint_is_rejected PASSED [ 69%]
tests/unit/probe/test_proposal.py::test_missing_required_field_is_rejected PASSED [ 76%]
tests/unit/probe/test_proposal.py::test_non_string_payload_kind_is_rejected PASSED [ 84%]
tests/unit/probe/test_proposal.py::test_non_dict_objective_is_rejected PASSED [ 92%]
tests/unit/probe/test_proposal.py::test_non_string_endpoint_hint_is_rejected PASSED [100%]

============================== 13 passed in 0.03s ==============================
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Triển khai một hàm thuần túy `validate_objective()` độc lập, deterministic, nhận `objective` và `Allowlist`, trả về dataclass `ProposalDecision` bất biến (`frozen=True`) kèm các guard kiểm tra kiểu để đảm bảo fail-closed.

**Lý do:**
- Thay thế các kiến trúc phức tạp nhiều lớp (proposer, resolver, policy engine) bằng một hàm guardrail tinh gọn, dễ đọc, dễ kiểm thử và không có trạng thái ẩn (stateless).
- Tách biệt rõ ràng giữa quyết định chấp nhận (`accepted: bool`) và dữ liệu probe (`SafeProbe`), giúp luồng gọi ở các bước sau dễ dàng xử lý mà không cần bắt ngoại lệ phức tạp.
- Đảm bảo fail-closed: dù LLM trả về bất kỳ dạng dữ liệu nào (kể cả unhashable types như list/dict trong payload_kind/endpoint_hint), hàm validate đều trả về `ProposalDecision(accepted=False)` thay vì ném ngoại lệ làm sập pipeline.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest tests/unit/probe/test_proposal.py -v` | 0 | 13 passed (100%) |
| `pytest -m "not llm" tests/unit/retrieval tests/unit/infra tests/unit/ingestion tests/unit/analysis tests/unit/probe tests/test_no_doubles.py -v` | 0 | 120 passed, 1 deselected (100%) |
| `python3 -m compileall -q src/project_sentinel` | 0 | PASSED |

**Bất biến đã giữ:** Không mock/stub, không skip test, không phá vỡ tương thích ngược, tuân thủ nguyên tắc Deny-by-default và bảo toàn báo cáo lịch sử `reports/week-XX/`.

**Còn fail / chưa chạy được:** Không có.

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** Logic phân tách `endpoint_hint.split(" ")` — đảm bảo chỉ chấp nhận đúng định dạng `<METHOD> <path>` với 1 khoảng trắng duy nhất, cấm query string và cấm khoảng trắng thừa.
- **Giả định đã đặt:** `Allowlist.is_allowed(method, path)` đã được kiểm thử tính đúng đắn ở package `gateway`.
- **Việc còn nợ:** Task 7 (Ba kịch bản kiểm thử mẫu cho Agent).
- **Câu hỏi cho người dùng:** Bạn có muốn commit và push Task 6 lên nhánh `feat/w1-w4-task6-proposal-validation` ngay bây giờ không?
