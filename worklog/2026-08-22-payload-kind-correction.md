# Worklog — Hiệu chỉnh `payload_kind` và Đồng bộ `allowed_endpoints` với Allowlist

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Task:** `Payload Kind Correction and Allowlist Synchronization`

---

## 1. Tóm tắt

1. **Khắc phục lỗi logic `payload_kind`:** Trước đây `load_allowed_endpoints` đọc trực tiếp `template.payload_kind` từ JSON (vốn là `null` cho các template GET) và gán `allowed_payload_kinds: []`, đồng thời prompt hướng dẫn model gán `payload_kind: null` cho request GET. Điều này vi phạm JSON Schema (`verification_objective.payload_kind` bắt buộc là enum 4 chuỗi, không chấp nhận `null`), khiến 6 record bị loại bỏ ở lần chạy trước.
2. **Fix A (Hỏi trực tiếp Allowlist):** Cập nhật `load_allowed_endpoints` trong `src/project_sentinel/analysis/packet_builder.py` để dùng `Allowlist.from_json` và truy vấn trực tiếp `allowlist.is_allowed(method, path, payload_kind=k, enforce_template=True)` cho toàn bộ 4 loại payload. Kết quả: các endpoint GET nhận đầy đủ 4 loại payload, và `POST /WebGoat/attack` nhận đúng 2 loại (`['long_string', 'empty_value']`).
3. **Fix B (Loại bỏ chỉ dẫn `null` trong Prompt):** Xoá bỏ hoàn toàn hướng dẫn gán `payload_kind: null` trong `configs/prompts/security-analysis-system.md`, làm rõ quy tắc: `payload_kind` phải luôn là một chuỗi thuộc `allowed_payload_kinds`, nếu không muốn kiểm chứng thì đặt cả object `verification_objective: null`.
4. **Kiểm chứng thực tế:** Lần chạy LLM thật `20260822T094343Z` đạt **33/37 output records** (tăng mạnh từ 29 và 23), số lượt gọi LLM giảm xuống còn **44** (tiết kiệm 30.2% so với mốc gốc 63), số lượt retry chỉ còn **7** (giảm 73.1%), và tổng token tiết kiệm được **117,613 tokens**.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Đồng bộ hoá tuyệt đối giữa dữ liệu quảng bá cho Model (`allowed_endpoints`), định dạng JSON Schema của record, và bộ kiểm định an toàn phía Gateway/Probe (`Allowlist`).
- **Nằm ở đâu trong luồng:** Tại module `src/project_sentinel/analysis/packet_builder.py`, `configs/prompts/security-analysis-system.md`, và tác động trực tiếp đến kết quả của `run_pipeline`.
- **Không có nó thì hỏng gì:** Model xuất ra `payload_kind: null` vi phạm schema khiến các record phân tích có đề xuất GET bị vứt bỏ hoàn toàn.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/analysis/packet_builder.py` | Sửa | Dùng `Allowlist.from_json` và gọi `is_allowed(..., enforce_template=True)` để tính `allowed_payload_kinds` | Đảm bảo tính toán `allowed_payload_kinds` chuẩn xác và đồng nhất với validator |
| `configs/prompts/security-analysis-system.md` | Sửa | Xoá chỉ dẫn `payload_kind: null`, nhấn mạnh `payload_kind` bắt buộc là chuỗi hợp lệ | Ngăn Model sinh `payload_kind: null` vi phạm JSON Schema |
| `tests/unit/analysis/test_allowed_endpoints_in_packet.py` | Sửa & Thêm | Thêm test bất biến giữa `load_allowed_endpoints` và `validate_objective`, test reject unadvertised kind, test prompt không chứa regex `payload_kind.{0,40}null` | Bảo đảm chống hồi quy bằng kiểm thử tự động |

---

## 4. Làm như thế nào

1. **Fix A:**
   ```python
   allowlist = Allowlist.from_json(allowlist_path)
   for rule in allowlist.rules:
       kinds = [
           k for k in ALL_PAYLOAD_KINDS
           if allowlist.is_allowed(rule.method, rule.path, payload_kind=k, enforce_template=True)
       ]
       pairs.append({"method": rule.method, "path": rule.path, "allowed_payload_kinds": kinds})
   ```
2. **Fix B:**
   - Diễn đạt lại mục `payload_kind` trong prompt:
     `payload_kind` phải luôn là một trong bốn giá trị và phải nằm trong `allowed_payload_kinds` của chính endpoint đã chọn. CẤM TUYỆT ĐỐI bỏ trống trường này. Muốn không đề xuất bước kiểm chứng, hãy đặt CẢ object `verification_objective` thành `null`.
3. **Viết Test:**
   - Kiểm tra bất biến 2 chiều: Mọi `(endpoint, payload_kind)` do `load_allowed_endpoints` sinh ra đều phải được `validate_objective` chấp nhận (`accepted is True`). Ngược lại, kind không được phép (`POST /WebGoat/attack` với `special_chars`) phải bị từ chối.

---

## 5. Output là gì

### Bảng so sánh 3 mốc vận hành thực tế

| Chỉ số | 051901Z (Nền ban đầu) | 092310Z (Sau FIX 3 hỏng) | 094343Z (Sau FIX A & B) | Thay đổi so với nền |
|---|---|---|---|---|
| `llm_call_count` | 63 | 52 | **44** | **-19 (-30.2 %)** |
| `retry_count` | 26 | 15 | **7** | **-19 (-73.1 %)** |
| `invalid_responses_observed` | 39 | 38 | **26** | **-13 (-33.3 %)** |
| `output_record_count` | 29 / 37 | 23 / 37 | **33 / 37** | **+4 (VƯỢT MỐC)** |
| `unresolved_groups` | 8 | 14 | **4** | **-4 (-50.0 %)** |
| `runtime_ms` | 437,523 ms (~437.5 s) | 424,322 ms (~424.3 s) | **368,810 ms (~368.8 s)** | **-68.7 s (-15.7 %)** |
| `token_usage.total` | 417,607 | 345,903 | **299,994** | **-117,613 (-28.2 %)** |

### `invalid_reasons` mới (xếp theo số lần giảm dần):
```json
{
  "objective: verification_objective bị allowlist từ chối: payload_kind '<val>' chưa được review cho '<val>'.": 16,
  "schema: Schema validation error: '<val>' does not match '<val>' at path ['<val>']": 4,
  "objective: verification_objective bị allowlist từ chối: '<val>' không có trong allowlist Gateway.": 3,
  "provenance: Source evidence cho '<val>' khong khop input: content/start_line/end_line da bi doi hoac bia ra": 3,
  "unsafe: verification_steps: sql_injection_payload — '<val>' OR '<val>'='<val>'": 2,
  "unsafe: verification_steps: destructive_sql — '<val>'": 1,
  "unsafe: verification_steps: sql_injection_payload — '<val>' OR <num>=<num>\"": 1,
  "provenance: Invented source evidence path '<val>' not present in input evidence": 1,
  "unsafe: remediation: sql_injection_payload — '<val>'; script\"": 1
}
```

### Chi tiết 4 nhóm unresolved còn lại:
1. `group-e46b371f0d`: Lỗi provenance (source evidence không khớp nội dung file `SqlInjectionLesson6b.java`).
2. `group-beea6607a4`: Lỗi schema UUID (`analysis-1a2b3c4d-5e6f-7g8h-9i10-j11k12l13m14` chứa `g`, `h`, `j`, `k`, `l`, `m`).
3. `group-9a3037319f`: Lỗi provenance (bịa đường dẫn file `SqlIteration9.java`).
4. `group-669f94e4b9`: Lỗi schema UUID (`analysis-6a3b2c8d-e4f5-4g6h-7i8j-9k1l2m3n4o5p` chứa `g`, `h`, `j`, `k`, `l`, `m`, `n`, `o`, `p`).

---

## 6. Vì sao chọn cách implement này

- **Single Source of Truth:** Thay vì tự parse lại template JSON bằng hàm riêng, `load_allowed_endpoints` ủy quyền việc xác định tính hợp lệ trực tiếp cho lớp `Allowlist`. Điều này đảm bảo packet gửi cho Model và logic kiểm tra của Validator luôn đồng nhất 100%.
- **Bảo toàn Schema Invariant:** Giữ nguyên contract schema bắt buộc của `verification_objective.payload_kind`, đồng thời tôn trọng bản chất của các endpoint GET (không có request payload).

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/analysis/test_allowed_endpoints_in_packet.py -v` | 0 | 12 passed |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **922 passed**, 38 deselected |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |
| `python -m project_sentinel.cli run --yes` | 0 | Chạy thành công 9 bước, đạt 33/37 records ($\ge 29$) |

---

## 8. Cần người review kỹ ở đâu

- **4 lỗi schema UUID còn sót lại:** Mặc dù số lỗi sinh UUID sai đã giảm mạnh (từ 10 xuống còn 2 nhóm `group-beea6607a4` và `group-669f94e4b9`), Model đôi khi vẫn sinh chuỗi kiểu `analysis-1a2b3c4d-5e6f-7g8h-9i10-j11k12l13m14` theo dạng chuỗi ký tự nối tiếp `1a2b3c...`. Trong tương lai, có thể xem xét việc hệ thống tự gán `analysis_id` nếu Model để trống hoặc hướng dẫn mạnh hơn về UUIDv4 chuẩn.
- **16 lỗi objective do Model vẫn chọn `special_chars` cho `POST /WebGoat/attack`:** Model vẫn có xu hướng tự nhiên muốn thử `special_chars` trên endpoint injection. Tuy nhiên nhờ FIX 1, các lỗi này không còn làm mất record mà được xử lý êm qua `_settle`.
