# Worklog — Sửa hồi quy probe 403: Siết chặt so khớp template và ưu tiên payload ít xâm lấn

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Plan:** Sửa hồi quy probe 403 — Phương án A · **Task ID:** `PROBE-403-STRICT-TEMPLATE`

---

## 1. Tóm tắt

Đã sửa hàm `Allowlist.resolve_template` để so khớp nghiêm ngặt `wanted = payload_kind` (không bỏ qua `payload_kind` cho GET), cập nhật 5 unit test liên quan để khoá chính sách từ chối GET mang payload kind, và điều chỉnh tiêu chí chọn đề xuất trong `_choose_objective` để ưu tiên loại payload ít xâm lấn hơn (`empty_value` trước `long_string`). Đã kiểm chứng toàn bộ 946 test offline, `make agent-test`, và chạy thành công một lần pipeline thật đầu cuối qua OpenRouter LLM và Gateway thực tế với mã HTTP 302 thay vì 403.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đồng bộ logic xác thực template ở tầng Python (`resolve_template` và `validate_objective`) với chính sách của Gateway Nginx (chặn cả body lẫn query string trên GET, không chấp nhận bất kỳ payload nào cho GET).
- **Nằm ở đâu trong luồng:** Nằm tại `gateway/allowlist.py` (xác thực allowlist), `orchestrator/steps/propose.py` (chọn đề xuất probe an toàn nhất), và các unit test liên quan.
- **Không có nó thì hỏng gì:** Nếu Python validator cho phép GET mang `payload_kind`, `_choose_objective` sẽ chọn request GET đó và `probe/tool.py` sẽ sinh JSON body khiến Nginx Gateway chặn với mã `403 Forbidden` ở mọi lần chạy.
- **Ngoài phạm vi (cố ý không làm):** Không sửa `probe/tool.py`, không sửa map Nginx, không nới `$sentinel_body_len_ok`, không sửa JSON Schema.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/gateway/allowlist.py` | Sửa | `wanted = payload_kind` và viết lại comment giải thích lý do GET không mang được payload | Đảm bảo không bỏ qua `payload_kind` khi method là GET |
| `src/project_sentinel/orchestrator/steps/propose.py` | Sửa | Đổi tiêu chí chọn đề xuất từ "ưu tiên GET" sang "ưu tiên `empty_value` trước `long_string`" | GET mang payload bị loại theo cấu trúc; tiêu chí mới giữ được ý định chọn payload ít xâm lấn nhất |
| `tests/unit/gateway/test_template_binding.py` | Sửa | Đổi `test_a_get_is_payload_agnostic_because_it_has_no_body` thành `test_a_get_cannot_declare_a_payload_kind` và thêm `test_a_get_without_payload_kind_is_still_allowed` | Khóa chính sách cấm GET mang `payload_kind` nhưng vẫn cho phép GET trơn (`payload_kind=None`) |
| `tests/unit/orchestrator/test_steps_analyze_propose.py` | Sửa | Chuyển các fixture GET sang POST hợp lệ và đổi test ưu tiên GET thành `test_empty_value_is_preferred_over_long_string` | Đảm bảo test bộ chọn đề xuất và override hoạt động đúng theo chính sách mới |

**`git diff HEAD~2 --stat`:**

```text
 src/project_sentinel/gateway/allowlist.py          | 13 +++++-------
 src/project_sentinel/orchestrator/steps/propose.py | 13 ++++++------
 tests/unit/gateway/test_template_binding.py        | 24 ++++++++++++++--------
 .../orchestrator/test_steps_analyze_propose.py     | 24 +++++++++++-----------
 4 files changed, 40 insertions(+), 34 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **FIX 1:** Trong `src/project_sentinel/gateway/allowlist.py`, loại bỏ nhánh `wanted = None if normalized_method == "GET" else payload_kind` và thay bằng `wanted = payload_kind`. Cập nhật comment giải thích rõ hạ tầng Gateway chặn cả body và query string trên GET.
2. **FIX 2:** Viết lại `test_template_binding.py` và `test_steps_analyze_propose.py` để khẳng định `is_allowed("GET", "/WebGoat/login", payload_kind="long_string")` là `False`, và `resolve_template("GET", "/WebGoat/login", "long_string")` trả về `None`.
3. **FIX 3:** Viết lại `_choose_objective` trong `src/project_sentinel/orchestrator/steps/propose.py` để tìm candidate có `payload_kind == "empty_value"` trước các payload khác (như `long_string`), thay thế cho nhánh ưu tiên GET đã lỗi thời.
4. **FIX 4:** Thực hiện đo thực tế khi người vận hành override bằng lệnh CLI `cli run --probe-method GET --probe-path /WebGoat/login` (bị từ chối do mặc định `--probe-payload-kind empty_value` và GET không nhận payload kind).

**Luồng dữ liệu:**
Input findings → LLM phân tích sinh đề xuất POST/GET → `validate_objective` (gọi `resolve_template` so khớp nghiêm ngặt `payload_kind`) → `_choose_objective` (chọn `empty_value` trước `long_string`) → SafeProbe POST gửi qua Gateway Nginx → WebGoat trả về 302 Found.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**
- `Allowlist.resolve_template` so khớp nghiêm ngặt `payload_kind`.
- `_choose_objective` ưu tiên `empty_value` trước `long_string`.
- `test_a_get_cannot_declare_a_payload_kind` và `test_empty_value_is_preferred_over_long_string`.

**Cách chạy:**

```bash
# Kiểm tra offline suite và static checks
pytest -m "not llm and not live_gateway" -q tests
make lint && make typecheck
make agent-test

# Chạy pipeline thật với LLM
KEY=$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env) \
  SENTINEL_GATEWAY_API_KEY="$KEY" \
  .venv/bin/python -m project_sentinel.cli run --yes
```

**Output thật (lần chạy thật 20260822T162314Z):**

- `artifacts/runs/20260822T162314Z/proposal.json`:
```json
{
  "accepted": true,
  "reason": "'POST /WebGoat/attack' đã được allowlist duyệt.",
  "probe": {
    "method": "POST",
    "path": "/WebGoat/attack",
    "payload_kind": "empty_value"
  },
  "source_analysis_id": "analysis-3a7b5c9d-1e2f-4a8b-9c6d-7e4f1a2b3c5d",
  "source_finding_ids": [
    "opengrep-005"
  ],
  "objective": {
    "description": "Gửi chuỗi serialized rỗng để kiểm tra phản hồi của ứng dụng",
    "endpoint_hint": "POST /WebGoat/attack",
    "payload_kind": "empty_value",
    "rationale": "Nếu endpoint POST /WebGoat/attack sử dụng SerializationHelper.fromString để xử lý dữ liệu, gửi giá trị rỗng có thể giúp phát hiện lỗi deserialize qua thông báo lỗi.",
    "expected_signal": "ClassNotFoundException hoặc InvalidClassException"
  },
  "objectives_found": 14,
  "operator_override": false,
  "objectives_accepted": 14
}
```

- `artifacts/runs/20260822T162314Z/gateway-requests.jsonl`:
```json
{"timestamp": "2026-08-22T16:32:46.630340+00:00", "request_id": "req-ee17700b0d1a", "method": "POST", "path": "/WebGoat/attack", "payload_type": "empty_value", "template_id": "tmpl_attack_post_empty", "status": "SENT", "status_code": 302, "elapsed_ms": 3.11, "response_bytes_observed": 0, "truncated": false, "response_preview": null, "error_class": "HTTPError", "error_reason": "HTTP 302: ", "policy_decision": "ALLOWED"}
```

- `artifacts/runs/20260822T162314Z/probe-result.json`:
```json
{
  "sent": true,
  "status_code": 302,
  "body_preview": "",
  "elapsed_ms": 3.11,
  "error_class": "HTTPError",
  "error_reason": "HTTP 302: ",
  "denied_reason": null,
  "redactions": []
}
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:**
1. Siết `resolve_template` để bắt buộc khớp `payload_kind` của template (khai trừ toàn bộ `payload_kind` không rỗng trên GET).
2. Viết lại `_choose_objective` theo Phương án (b) (ưu tiên `empty_value` trước `long_string`).

**Lý do:**
1. Ràng buộc bất biến của Nginx Gateway: toàn bộ location GET đều có `if ($args) { return 400; }` và `$sentinel_body_len_ok` chỉ chấp nhận body length 0. Bất kỳ request GET nào có body đều bị Gateway trả 403. Việc cho phép Python validator chấp nhận `payload_kind` trên GET là mâu thuẫn với hạ tầng thực tế.
2. Phương án (b) giữ được nguyên lý thiết kế "chọn probe ít xâm lấn nhất", đảm bảo khi có cả `empty_value` và `long_string`, hệ thống sẽ luôn ưu tiên payload an toàn hơn (`empty_value`).

**Phương án đã cân nhắc và loại bỏ:**

| Phương án | Ưu | Vì sao loại |
|---|---|---|
| Bỏ qua hoàn toàn logic ưu tiên trong `_choose_objective` (Phương án a) | Đơn giản hoá code | Mất đi khả năng tự động chọn phương án kiểm chứng ít xâm lấn nhất giữa các probe POST hợp lệ |
| Cho phép GET mang body ở Gateway Nginx | Giữ được GET mang payload | Vi phạm chính sách bảo mật và thiết kế RESTful chuẩn (GET không mang body) |

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `pytest -m "not llm and not live_gateway" -q tests` | 0 | 946 passed, 41 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 78 source files clean |
| `make agent-test` | 0 | 946 passed + Live Gateway integration tests passed |
| `python -m project_sentinel.cli run --yes` | 0 | DONE, proposal POST accepted, Gateway trả về 302 Found |

**Test mới thêm / sửa:**
- `tests/unit/gateway/test_template_binding.py::test_a_get_cannot_declare_a_payload_kind`: Khẳng định GET với `payload_kind="long_string"` bị từ chối.
- `tests/unit/gateway/test_template_binding.py::test_a_get_without_payload_kind_is_still_allowed`: Khẳng định GET với `payload_kind=None` được chấp nhận.
- `tests/unit/orchestrator/test_steps_analyze_propose.py::test_empty_value_is_preferred_over_long_string`: Khẳng định `empty_value` được ưu tiên hơn `long_string`.

**Bất biến đã giữ:** Không mock/stub, Gateway và WebGoat thực tế, kiểm tra phân quyền và bí mật.

---

## 8. Cần người review kỹ ở đâu

- **Hệ quả của FIX 4 (Override thủ công của người vận hành):**
  - Khi chạy lệnh của người vận hành:
    ```bash
    .venv/bin/python -m project_sentinel.cli run --probe-method GET --probe-path /WebGoat/login --yes
    ```
  - CLI `src/project_sentinel/cli.py` hiện có cấu hình mặc định:
    `--probe-payload-kind` = `"empty_value"`
  - Do `Allowlist.resolve_template` nay đã siết chặt (GET không nhận bất kỳ `payload_kind` nào), lệnh trên tạo ra một `probe_override` với `method="GET"`, `path="/WebGoat/login"`, `payload_kind="empty_value"`.
  - Kết quả đo thực tế tại `artifacts/runs/20260822T161015Z/proposal.json`:
    ```json
    {
      "accepted": false,
      "reason": "payload_kind 'empty_value' chưa được review cho 'GET /WebGoat/login'.",
      "probe": null,
      "source_analysis_id": "operator-override",
      "source_finding_ids": [],
      "objective": {
        "description": "Bước kiểm chứng do người vận hành chỉ định",
        "endpoint_hint": "GET /WebGoat/login",
        "payload_kind": "empty_value",
        "rationale": "Người vận hành chọn request này để quan sát phản hồi; allowlist Gateway vẫn kiểm tra như thường."
      },
      "objectives_found": 17,
      "operator_override": true,
      "objectives_accepted": 17
    }
    ```
  - Và `events.jsonl` ghi nhận sự kiện `allowlist_block`.
  - **Câu hỏi / Quyết định cần từ người dùng:**
    Hiện tại tuân thủ yêu cầu "KHÔNG tự sửa cli.py". Nếu muốn người vận hành có thể override GET thông qua CLI trong tương lai, `cli.py` cần được điều chỉnh để `--probe-payload-kind` nhận giá trị `None` khi người dùng chỉ định `--probe-method GET` (hoặc để mặc định của `--probe-payload-kind` là `None` nếu method là GET).
