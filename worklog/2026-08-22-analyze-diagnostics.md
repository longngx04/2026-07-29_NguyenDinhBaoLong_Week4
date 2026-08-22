# Worklog — Chẩn đoán lỗi phản hồi LLM và chống Race Condition Redaction

**Ngày:** 2026-08-22 · **Agent/Model:** Antigravity · inherit ·
**Branch:** `feat/zap-dast` · **Task:** `Redaction Race Fix & Invalid Output Diagnostics`

---

## 1. Tóm tắt

1. **Fix 1 (Race Condition):** Sửa lỗi race condition trong `RedactingProvider` (`analyze` và `generate`). Việc đọc lại thuộc tính `self.last_redaction_events` khi chạy đa luồng (`ThreadPoolExecutor`) có thể dẫn tới sự kiện audit của nhóm này bị ghi nhầm số đếm của nhóm khác. Đã chuyển sang đọc biến cục bộ `events` và bổ sung unit test đa luồng chứng minh lỗi (test đỏ trước khi sửa).
2. **Fix 2 (Chẩn đoán lỗi LLM):** Bổ sung cơ chế thu thập, chuẩn hoá và báo cáo chi tiết nguyên nhân phản hồi LLM không hợp lệ (`invalid_reasons` và `unresolved_group_reasons`). Mọi lỗi validation (schema, provenance, unsafe, objective, unparseable) từ tất cả các lần thử (lần đầu + retry) đều được ghi nhận, chuẩn hoá qua regex để gom nhóm đếm tần suất và đưa qua bộ che `redact_structure()` trước khi ghi vào `analysis-summary.json`.
3. **Thực thi lần chạy thật:** Đã chạy kiểm chứng end-to-end với LLM thật (`qwen/qwen3-235b-a22b-2507`) trên 37 nhóm (23 SAST + 14 DAST), thu thập đầy đủ số liệu chẩn đoán thực tế.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:**
  - Bảo đảm tính toàn vẹn và chính xác của nhật ký audit che dữ liệu (`events.jsonl`) trong môi trường đa luồng.
  - Cung cấp tính năng quan sát (observability) chi tiết và minh bạch cho tầng phân tích LLM: giúp người vận hành và kỹ sư prompt biết chính xác tại sao model bị từ chối, những nhóm nào bị loại bỏ và nguyên nhân phân bố thế nào.
- **Nằm ở đâu trong luồng:** Tại `src/project_sentinel/llm/redacting.py`, `src/project_sentinel/analysis/pipeline.py`, và xuất ra `artifacts/runs/<run_id>/analysis-summary.json`.
- **Không có nó thì hỏng gì:**
  - Số liệu redaction audit bị sai lệch giữa các nhóm khi chạy song song.
  - Khi tỷ lệ `invalid_outputs` tăng cao (ví dụ 8/37 nhóm bị vứt bỏ), hệ thống hoàn toàn "mù" nguyên nhân, không có căn cứ để tối ưu hóa prompt hay tinh chỉnh schema/allowlist.

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `src/project_sentinel/llm/redacting.py` | Sửa | Dùng biến cục bộ `events` khi gọi `append_event` trong `analyze` và `generate` | Khắc phục race condition đa luồng |
| `tests/unit/guardrails/test_llm_redaction_chokepoint.py` | Sửa | Thêm test đa luồng `test_concurrent_analyze_audit_events_count_matches_each_packet` | Tái hiện và kiểm chứng fix race condition |
| `src/project_sentinel/analysis/pipeline.py` | Sửa | Thêm `validation_errors` vào `_GroupOutcome`, thêm `as_reasons()` vào `_ResponseErrors`, thêm helper `_normalize_reason`, tổng hợp `invalid_reasons` và `unresolved_group_reasons` có redact | Thu thập và báo cáo chẩn đoán lỗi |
| `tests/unit/analysis/test_invalid_output_diagnostics.py` | Tạo mới | 4 unit tests kiểm tra provenance error, unresolved groups, normalization aggregation và empty run | Bảo đảm độ bao phủ của tính năng chẩn đoán |

---

## 4. Làm như thế nào

1. **Fix 1:**
   - Trong `RedactingProvider.analyze` và `RedactingProvider.generate`: gán `events = _merge(...)`, giữ `self.last_redaction_events = events` cho tương thích backward, nhưng khi gọi `append_event` thì truyền trực tiếp `events` cục bộ.
   - Viết test đa luồng với `ThreadPoolExecutor`, cài property delay để ép context switch và assert `total_redacted` khớp chính xác với từng `group_key`.
2. **Fix 2:**
   - Thêm `validation_errors: List[str] = field(default_factory=list)` vào `_GroupOutcome`.
   - Trong `_ResponseErrors`, cài đặt `.as_reasons() -> List[str]` gom các trường `schema`, `provenance`, `unsafe`, `objective` thành danh sách có tiền tố rõ ràng.
   - Trong `_analyze_one_group`, sau mỗi lần parse hoặc validate thất bại (cả lần đầu và lần retry), gọi `outcome.validation_errors.extend(...)`.
   - Trong `run_pipeline`, chuẩn hoá lỗi bằng regex (`_QUOTED_RE.sub("'<val>'", ...)` và `_NUMBER_RE.sub("<num>", ...)`), đếm tần suất vào `invalid_reasons`, trích xuất `unresolved_group_reasons` cho các nhóm `outcome.record is None`, và bọc `redact_structure()` trước khi ghi file.

---

## 5. Output là gì

### Dữ liệu chẩn đoán thực tế từ lần chạy `20260822T051901Z`

#### Các số liệu vận hành chính:
- `llm_call_count`: **63**
- `retry_count`: **26**
- `invalid_responses_observed`: **39**
- `output_record_count`: **29**
- `group_count`: **37**
- `runtime_ms`: **437523.22** (analyze step: ~437.5 s)

#### Bảng `invalid_reasons` (xếp theo số lần giảm dần):
```json
{
  "objective: verification_objective bị allowlist từ chối: payload_kind '<val>' chưa được review cho '<val>'.": 17,
  "schema: Schema validation error: '<val>' does not match '<val>' at path ['<val>']": 10,
  "objective: verification_objective bị allowlist từ chối: '<val>' không có trong allowlist Gateway.": 10,
  "provenance: Source evidence cho '<val>' khong khop input: content/start_line/end_line da bi doi hoac bia ra": 3,
  "unsafe: verification_steps: sql_injection_payload — '<val>' OR '<val>'='<val>'": 2,
  "objective: verification_objective bị allowlist từ chối: Method '<val>' không được phép.": 1,
  "unsafe: verification_steps: destructive_sql — '<val>'": 1,
  "unsafe: explanation: sql_injection_payload — '<val>'or '<val>'='<val>'": 1,
  "unsafe: verification_steps: xss_payload — '<val>'": 1,
  "unsafe: verification_objective.expected_signal: xss_payload — '<val>'": 1
}
```

#### Chi tiết `unresolved_group_reasons` (8 nhóm bị loại bỏ):
```json
{
  "group-bbf829922e": [
    "objective: verification_objective bị allowlist từ chối: payload_kind 'special_chars' chưa được review cho 'POST /WebGoat/attack'.",
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-7k8l9m0n1o2p' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']"
  ],
  "group-eed1ac6e96": [
    "objective: verification_objective bị allowlist từ chối: payload_kind 'special_chars' chưa được review cho 'POST /WebGoat/attack'.",
    "schema: Schema validation error: 'analysis-8a3f5c2d-b9e1-4b7a-9c6a-1d2e3f4g5h6i' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']"
  ],
  "group-e46b371f0d": [
    "provenance: Source evidence cho 'benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionLesson6b.java' khong khop input: content/start_line/end_line da bi doi hoac bia ra",
    "provenance: Source evidence cho 'benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/advanced/SqlInjectionLesson6b.java' khong khop input: content/start_line/end_line da bi doi hoac bia ra"
  ],
  "group-e044122e79": [
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-k7l8m9n0o1p2' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']",
    "provenance: Source evidence cho 'benchmarks/targets/webgoat/src/main/java/org/owasp/webgoat/lessons/sqlinjection/introduction/SqlInjectionLesson10.java' khong khop input: content/start_line/end_line da bi doi hoac bia ra"
  ],
  "group-0fe1a55d91": [
    "objective: verification_objective bị allowlist từ chối: 'POST /SqlInjection/attack2' không có trong allowlist Gateway.",
    "unsafe: verification_steps: sql_injection_payload — \"' OR '1'='1\"",
    "objective: verification_objective bị allowlist từ chối: payload_kind 'special_chars' chưa được review cho 'POST /WebGoat/attack'."
  ],
  "group-c5e03ea132": [
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-7k8l9m0n1o2p' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']",
    "objective: verification_objective bị allowlist từ chối: payload_kind 'special_chars' chưa được review cho 'POST /WebGoat/attack'.",
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-7k8l9m0n1o2p' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']"
  ],
  "group-d39bbcac22": [
    "objective: verification_objective bị allowlist từ chối: 'GET /WebGoat/start.mvc' không có trong allowlist Gateway.",
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-7k8l9m0n1o2p' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']"
  ],
  "group-fb12de6299": [
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-k7l8m9n0o1p2' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']",
    "objective: verification_objective bị allowlist từ chối: 'GET /WebGoat/start.mvc' không có trong allowlist Gateway.",
    "schema: Schema validation error: 'analysis-7a8b9c0d-1e2f-3g4h-5i6j-k7l8m9n0o1p2' does not match '^analysis-[a-f0-9-]+$' at path ['analysis_id']"
  ]
}
```

---

## 6. Vì sao chọn cách implement này

- **Biến cục bộ trong `RedactingProvider`:** Biến cục bộ nằm trên stack của từng thread, đảm bảo thread-safe tuyệt đối mà không cần dùng threading lock gây nghẽn I/O.
- **Chuẩn hoá regex đơn giản:** Thay thế chuỗi trích dẫn và chữ số bằng token chung giúp gom các lỗi cùng loại (ví dụ lỗi định dạng UUID hay lỗi payload template) về đúng một danh mục để dễ thống kê tần suất.
- **Không tự ý sửa prompt/validator:** Đúng theo chỉ thị, việc thu thập số liệu là bước quan sát độc lập để cung cấp bằng chứng cho quyết định kỹ thuật tiếp theo.

---

## 7. Kiểm chứng

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `.venv/bin/python -m pytest tests/unit/guardrails/test_llm_redaction_chokepoint.py -v` | 0 | 12 passed (bao gồm test race condition) |
| `.venv/bin/python -m pytest tests/unit/analysis/test_invalid_output_diagnostics.py -v` | 0 | 4 passed |
| `make lint && make typecheck` | 0 | All checks passed, 0 issues |
| `.venv/bin/python -m pytest -m "not llm and not live_gateway" -q tests` | 0 | **914 passed**, 38 deselected |
| `python -m project_sentinel.cli run --yes` | 0 | Chạy thành công 9 bước, thu được đầy đủ chẩn đoán |

---

## 8. Cần người review kỹ ở đâu

1. **Lỗi sinh UUID của Model (`analysis_id` format):**
   Trong 10 lỗi schema, đa phần là do Model sinh các chuỗi UUID giả lập có chứa ký tự ngoài hệ hex (như `g`, `h`, `i`, `j`, `k`, `p` trong `analysis-7a8b9c0d-1e2f-3g4h-5i6j-7k8l9m0n1o2p`), dẫn tới vi phạm regex `^analysis-[a-f0-9-]+$` của JSON Schema. Cần xem xét hướng dẫn rõ trong prompt hoặc hỗ trợ bộ sinh ID tự động.
2. **Lỗi `payload_kind` không hợp lệ:**
   Có tới 17 lần Model chọn `special_chars` cho endpoint `POST /WebGoat/attack` (vốn chỉ allowlist `empty_value`, `wrong_type`, `long_string`).
3. **Lỗi bịa endpoint:**
   Model tự đề xuất `GET /WebGoat/start.mvc` và `POST /SqlInjection/attack2` (10 lần) không có trong allowlist Gateway.
