# Worklog — Plan 2: Task 3 - Log Redaction Chokepoint

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 3 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-gateway-log` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã thiết lập nút thắt cổ chai bảo mật thứ hai tại `log_request()` trong `gateway/request_log.py`. Mọi trường audit trước khi ghi xuống đĩa đều được che qua `redact_structure()`. Đã khắc phục 3 điểm trọng yếu: (1) Cắt lại `response_preview` theo byte UTF-8 sau khi che để đảm bảo bất biến không vượt quá 512 byte (do placeholder làm chuỗi dài ra); (2) Bổ sung 5 trường provenance ID của audit log (`candidate_id`, `objective_id`, `proposal_id`, `endpoint_id`, `template_id`) vào `SKIP_KEYS` trong `guardrails/redaction.py` để không làm méo ID đối chiếu; (3) Khóa chặt ranh giới từ `\bkey\b\s+` cho hex secret bằng unit test. Kết quả: 10 unit test chokepoint pass 100%, toàn bộ suite 224 test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đóng vai trò là chokepoint (nút thắt cổ chai bắt buộc) của tầng gateway audit logging, đảm bảo không có bất kỳ dữ liệu nhạy cảm hay API key / credential nào bị ghi dưới dạng plaintext vào file log `requests.jsonl`, đồng thời duy trì tính toàn vẹn của các trường định danh đối chiếu và giới hạn kích thước 512 byte.
- **Nằm ở đâu trong luồng:** Nằm tại `gateway/request_log.py`, ngay trước khi các record audit được serialize sang JSON và ghi ra file.
- **Không có nó thì hỏng gì:** Nếu target upstream phản hồi nội dung chứa dữ liệu cá nhân (PII, email, số điện thoại) hoặc rò rỉ key bí mật trong `error_reason`, audit log sẽ lưu trữ plaintext. Ngược lại, nếu không re-clamp sau khi che thì việc thay thế `[REDACTED_EMAIL]` sẽ làm phình preview vượt quá 512 byte, vi phạm AGENTS.md bất biến #9; hoặc nếu che nhầm provenance ID dạng số như `obj-0912345678` thì phá hỏng khả năng đối chiếu trace log.
- **Ngoài phạm vi (cố ý không làm):** Chưa phát hiện prompt injection trong untrusted payload (thuộc Task 4 của Plan 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/gateway/request_log.py` | Sửa | 1. Sử dụng `redact_structure(dict(fields))` để che các giá trị chuỗi trước khi gộp vào `record`.<br>2. Thêm bước re-clamp `response_preview` về <= 512 byte UTF-8 sau khi che (dùng `encoded[:512].decode("utf-8", errors="ignore")`). | Nơi duy nhất serialize và ghi log audit request |
| `src/project_sentinel/guardrails/redaction.py` | Sửa | 1. Bổ sung `candidate_id`, `objective_id`, `proposal_id`, `endpoint_id`, `template_id` vào `SKIP_KEYS`.<br>2. Bổ sung pattern hex secret có từ khóa `\bkey\b\s+<hex>`. | Bảo vệ toàn vẹn provenance ID của audit log và bắt lỗi upstream key |
| `tests/unit/guardrails/test_log_redaction_chokepoint.py` | Tạo mới / Mở rộng | 10 unit test: kiểm tra che email, che API key trong error reason, che phone, bảo toàn cả 6 provenance ID, giữ nguyên clean fields, từ chối trường lạ, re-clamp preview <= 512 byte, và kiểm tra word boundary của từ khóa `key`. | Chứng minh tính đúng đắn và an toàn của nút thắt audit log |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–5 của Task 3 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md |  10 +-
 src/project_sentinel/gateway/request_log.py                       |  11 ++-
 src/project_sentinel/guardrails/redaction.py                      |  12 ++-
 tests/unit/guardrails/test_log_redaction_chokepoint.py           | 104 ++++++++++++++++++++++
 worklog/2026-08-19-plan2-task3-log-redaction-chokepoint.md        | 160 ++++++++++++++++++++++
 5 files changed, 285 insertions(+), 12 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. Trong hàm `log_request(log_path, **fields)`:
   - Giữ nguyên validation kiểm tra `unknown_fields` với `AUDIT_FIELD_NAMES` và kiểm tra `MAX_AUDIT_PREVIEW_BYTES` ban đầu trên caller input.
   - Gọi `safe_fields, _ = redact_structure(dict(fields))` để duyệt đệ quy và che sạch mọi chuỗi nhạy cảm.
   - Sau khi che, nếu `safe_fields.get("response_preview")` bị dãn nở vượt quá 512 byte UTF-8 do các chuỗi placeholder `[REDACTED_...]`, tiến hành cắt lại chuỗi theo đúng 512 byte với `errors="ignore"` để đảm bảo không vi phạm bất biến byte cap.
   - Ghi bản ghi nguyên tử ra đĩa qua file tạm `NamedTemporaryFile` + `os.replace`.
2. Trong `guardrails/redaction.py`:
   - Mở rộng `SKIP_KEYS` bao gồm cả 6 trường định danh provenance của audit log: `request_id`, `candidate_id`, `objective_id`, `proposal_id`, `endpoint_id`, `template_id`.

**Luồng dữ liệu:**
`Audit Data` ➔ `Caller Validation (Unknown fields, input byte bounds)` ➔ `redact_structure()` (che dữ liệu nhạy cảm, bảo toàn 6 provenance ID) ➔ `Post-redaction Byte Re-clamp (<= 512 bytes)` ➔ `Atomic JSONL Write`

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Constant | `SKIP_KEYS` | `guardrails/redaction.py` | Bao gồm đủ 6 trường định danh provenance audit log và 4 trường pipeline |
| Function | `log_request` | `gateway/request_log.py` | Hàm ghi audit log tự động che dữ liệu nhạy cảm và bảo đảm byte cap 512 bytes |
| Test file | `test_log_redaction_chokepoint.py` | `tests/unit/guardrails/test_log_redaction_chokepoint.py` | 10 unit tests bảo vệ nút thắt audit log |

**Cách chạy:**

```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_log_redaction_chokepoint.py -v
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Hai lớp kiểm soát độ dài (caller-check và post-redaction re-clamp) kết hợp `SKIP_KEYS` provenance.

**Lý do:**
- Bảo đảm tuyệt đối AGENTS.md Invariant #9 (Bounded Execution) ngay cả khi dữ liệu bên ngoài từ upstream cố tình làm dãn nở chuỗi qua các email/phone liên tiếp.
- Giữ nguyên các ID đối chiếu giữa các bảng log mà không làm suy giảm tính năng phát hiện nhạy cảm trên `response_preview` hay `error_reason`.

---

## 7. Kiểm chứng

### Bằng chứng test chạy thật

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 10 items

tests/unit/guardrails/test_log_redaction_chokepoint.py::test_email_in_response_preview_is_redacted PASSED [ 10%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_api_key_leaked_into_error_reason_is_redacted PASSED [ 20%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_phone_number_in_preview_is_redacted PASSED [ 30%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_request_id_provenance_survives_redaction PASSED [ 40%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_clean_fields_are_written_unchanged PASSED [ 50%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_unreviewed_field_names_are_still_rejected PASSED [ 60%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_preview_stays_within_the_byte_cap_after_redaction PASSED [ 70%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_all_audit_provenance_ids_survive_redaction PASSED [ 80%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_response_preview_with_phone_number_is_still_redacted PASSED [ 90%]
tests/unit/guardrails/test_log_redaction_chokepoint.py::test_key_keyword_needs_a_word_boundary PASSED [100%]

============================== 10 passed in 0.05s ==============================
```

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_log_redaction_chokepoint.py tests/unit/gateway -v` | 0 | **22 passed** in 0.45s |
| `PYTHONPATH=src python3 -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **224 passed**, 13 deselected in 1.74s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |
| `grep -r 'Week\|week' src/project_sentinel/` | 0 | **0 match** (không chứa week token trong production code) |

---

## 8. Cần người review kỹ ở đâu

- **Chỗ ít chắc chắn nhất:** `src/project_sentinel/gateway/request_log.py:46-52` — Logic re-clamp chuỗi UTF-8 `encoded[:MAX_AUDIT_PREVIEW_BYTES].decode("utf-8", errors="ignore")`.
- **Đính chính giả định:** Giả định ban đầu cho rằng chỉ có `request_id` là provenance trong audit log là không đầy đủ. Audit log có tới 6 trường provenance ID liên quan đến workflow (`request_id`, `candidate_id`, `objective_id`, `proposal_id`, `endpoint_id`, `template_id`) và tất cả đều đã được đưa vào `SKIP_KEYS`.
- **Việc còn nợ:** Task 4 của Plan 2 (`guardrails/injection.py` — phát hiện prompt injection).
- **Câu hỏi cho người dùng:** Không có.
