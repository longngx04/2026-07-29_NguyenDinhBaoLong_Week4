# Worklog — Bổ sung Test Bất biến Hai chiều cho Allowlist và Endpoint Quảng bá

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Task:** `Bidirectional Invariant Test for Advertised Allowlist Payloads`

---

## 1. Tóm tắt

1. **Vấn đề của test cũ:** `test_every_advertised_payload_kind_is_accepted_by_validate_objective` là kiểm thử bất biến một chiều (chiều xuôi: `advertised -> accepted`). Khi một endpoint bị trả về danh sách rỗng (`[]`), vòng lặp không chạy và test vẫn xanh rỗng mà không phát hiện được lỗi bỏ sót (như trường hợp GET bị gán `[]` ở lượt trước).
2. **Giải pháp:** Bổ sung test bất biến chiều ngược `test_every_kind_the_allowlist_accepts_is_advertised` trong `tests/unit/analysis/test_allowed_endpoints_in_packet.py`. Test này lặp qua toàn bộ các cặp `(method, path)` và toàn bộ 4 loại payload trong `PAYLOAD_KIND_TO_TYPE`. Nếu `validate_objective` chấp nhận một tổ hợp, tổ hợp đó bắt buộc phải có mặt trong `allowed_payload_kinds` của endpoint tương ứng.
3. **Chứng minh guard thực tế:** Đã thử nghiệm làm hỏng code (gán `allowed_payload_kinds: []` cho GET), xác nhận test chuyển ĐỎ (bắt đúng lỗi), sau đó hoàn tác về code đúng và xác nhận test chuyển XANH.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đóng vai trò là chốt chặn tự động (test guard) 2 chiều hoàn chỉnh giữa tầng dữ liệu prompt (`load_allowed_endpoints`) và tầng kiểm định nghiệp vụ (`validate_objective` / `Allowlist`).
- **Nằm ở đâu trong luồng:** Tại `tests/unit/analysis/test_allowed_endpoints_in_packet.py`.
- **Không có nó thì hỏng gì:** Nếu trong tương lai có sự thay đổi logic khiến `load_allowed_endpoints` bỏ sót một `payload_kind` hợp lệ, test chiều xuôi sẽ không bắt được và làm giấu mất lựa chọn hợp lệ khỏi LLM.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `tests/unit/analysis/test_allowed_endpoints_in_packet.py` | Sửa | Thêm test case `test_every_kind_the_allowlist_accepts_is_advertised` | Đảm bảo kiểm tra bất biến chiều ngược |

---

## 4. Làm như thế nào

1. Sử dụng hằng số `PAYLOAD_KIND_TO_TYPE` từ `project_sentinel.probe.payload_kinds` để duyệt qua toàn bộ 4 loại payload an toàn.
2. Với mỗi cặp `(method, path)` xuất hiện trong `load_allowed_endpoints(ALLOWLIST_PATH)`:
   - Dựng một `verification_objective` mẫu với `payload_kind=kind`.
   - Nếu `validate_objective(objective, allowlist).accepted` là `True`, khẳng định `kind in entry["allowed_payload_kinds"]`.
   - Nếu vi phạm, báo lỗi rõ ràng: `"{method} {path}: allowlist chap nhan {kind} nhung allowed_payload_kinds khong quang ba no"`.

---

## 5. Output là gì

### 1. Bằng chứng Test ĐỎ khi cố tình làm hỏng code (GET trả về `[]`):
```text
FAILED tests/unit/analysis/test_allowed_endpoints_in_packet.py::test_every_kind_the_allowlist_accepts_is_advertised
=================================== FAILURES ===================================
_____________ test_every_kind_the_allowlist_accepts_is_advertised ______________
...
>                   assert kind in advertised_kinds, (
                        f"{method} {path}: allowlist chap nhan {kind} nhung "
                        "allowed_payload_kinds khong quang ba no"
                    )
E                   AssertionError: GET /WebGoat/actuator/health: allowlist chap nhan long_string nhung allowed_payload_kinds khong quang ba no
E                   assert 'long_string' in []

tests/unit/analysis/test_allowed_endpoints_in_packet.py:126: AssertionError
======================= 1 failed, 12 deselected in 0.11s =======================
```

### 2. Bằng chứng Test XANH khi chạy trên code chuẩn:
```text
tests/unit/analysis/test_allowed_endpoints_in_packet.py::test_every_kind_the_allowlist_accepts_is_advertised PASSED [100%]
============================== 13 passed in 0.07s ==============================
```

---

## 6. Vì sao chọn cách implement này

- **Dùng chung hằng số `PAYLOAD_KIND_TO_TYPE`:** Tránh việc hardcode danh sách payload kinds ở nhiều nơi, đảm bảo khi thêm loại payload mới vào registry thì test tự động kiểm tra ngay mà không bị lệch.
- **Bất biến 2 chiều (Bi-directional Invariant):**
  - Chiều 1 (`test_every_advertised_payload_kind_is_accepted_by_validate_objective`): Mọi thứ quảng bá đều phải dùng được (Soundness).
  - Chiều 2 (`test_every_kind_the_allowlist_accepts_is_advertised`): Mọi thứ dùng được đều phải được quảng bá (Completeness).

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_allowed_endpoints_in_packet.py -v` | 0 | 13 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **923 passed**, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |

---

## 8. Cần người review kỹ ở đâu

- **Phạm vi áp dụng của test:** Test hiện tại quét qua tất cả các cặp `(method, path)` do `load_allowed_endpoints` trả về. Trong trường hợp allowlist có một rule mới nhưng `load_allowed_endpoints` bị lỗi không trả về endpoint đó (ví dụ bị drop do parse lỗi), test này sẽ không duyệt endpoint bị mất đó. Để chặt chẽ tuyệt đối, test có thể duyệt trực tiếp trên `allowlist.rules` thay vì chỉ trên kết quả của `load_allowed_endpoints`.
