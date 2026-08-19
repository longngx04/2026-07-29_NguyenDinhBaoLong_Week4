# Worklog — Plan 2: Task 5 - System Prompt Rules and Injection Fixtures

**Kế hoạch:** Plan 2 (Tuần 5: Guardrails) · **Task:** Task 5 · **Ngày:** 2026-08-19 · **Agent/Model:** Antigravity · Gemini 3.7 Flash High ·
**Branch:** `feat/guardrails-prompt-rules` · **Plan path:** [`docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md`](../docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md)

---

## 1. Tóm tắt

Trong khuôn khổ Plan 2 (Tuần 5: Guardrails), đã bổ sung 3 luật chống Prompt Injection cốt lõi vào system prompt (`configs/prompts/security-analysis-system.md`), định nghĩa hàm dựng payload duy nhất `build_packet_dict` trong `llm/base.py` (đảm bảo không gây vòng lặp import giữa `analysis` và `llm`, đồng thời `allowed_endpoints` và `wrap_untrusted` luôn có mặt trong payload gửi OpenRouter lẫn khi tính `prompt_sha256`), hoàn thiện mẫu `exfiltrate_to_url` có từ khóa bí mật, và hoàn thiện 3 fixture phản hồi thử nghiệm: (1) `ignore-instructions.json`; (2) `exfiltrate-endpoint.json`; (3) `pii-leak.json` (kiểm chứng làm sạch bằng `redact()`). Kết quả: 16 unit test pass 100%, toàn bộ suite 261 test xanh.

---

## 2. Task này có chức năng gì

- **Chức năng trong hệ thống:** Định nghĩa chỉ dẫn bắt buộc cho mô hình phân tích an ninh về cách đối xử với nội dung untrusted nằm giữa thẻ `<untrusted_app_response>`, cấm thay đổi mục tiêu, cấm lộ secret/prompt và cấm gọi tool ngoài allowlist; đồng thời kết nối cơ chế bọc thẻ `wrap_untrusted` trực tiếp vào quá trình render payload và cung cấp bộ fixture giả lập các cuộc tấn công prompt injection và rò rỉ dữ liệu.
- **Nằm ở đâu trong luồng:** Nằm tại `configs/prompts/` (cấu hình prompt), `llm/base.py` (hàm dựng payload duy nhất), và `tests/fixtures/injection/` (dữ liệu kiểm thử phục vụ pipeline phân tích ở Task 6 & 7).
- **Không có nó thì hỏng gì:** LLM không nhận được chỉ thị rõ ràng rằng nội dung ứng dụng là dữ liệu thụ động chứ không phải chỉ dẫn thi hành; payload gửi đi thiếu các thẻ phân tách `<untrusted_app_response>` và thiếu `allowed_endpoints`; giá trị `prompt_sha256` tính trên dict một đằng gửi đi một nẻo làm hỏng tính toàn vẹn provenance.
- **Ngoài phạm vi (cố ý không làm):** Chưa tích hợp ghi nhận sự kiện vào `events.py` (thuộc Task 6 của Plan 2).

---

## 3. Đã làm gì

| File | Thao tác | Nội dung thay đổi | Vì sao phải đụng file này |
|---|---|---|---|
| `configs/prompts/security-analysis-system.md` | Sửa | Thêm mục "Nội dung không đáng tin" cùng 3 luật tuyệt đối: không thay đổi mục tiêu, không lộ system prompt/API key, không gọi công cụ ngoài `allowed_endpoints` | Chỉ thị cốt lõi cho LLM trong toàn hệ thống |
| `src/project_sentinel/llm/base.py` | Sửa | Định nghĩa hàm duy nhất `build_packet_dict()` bọc `wrap_untrusted()` cho `source_evidence[]["content"]` và có đầy đủ 8 trường (bao gồm `allowed_endpoints`) | Đặt tại module base để tránh vòng lặp import với `analysis` |
| `src/project_sentinel/analysis/prompt_builder.py` | Sửa | Sử dụng `build_packet_dict()` từ `llm.base` trong `PromptBuilder.build()` | Đảm bảo tính toán `prompt_sha256` trùng khớp 100% với payload thực tế |
| `src/project_sentinel/llm/openrouter.py` | Sửa | Sử dụng `build_packet_dict()` trong `OpenRouterClient.analyze()`, xoá bỏ việc tự dựng dict trùng lặp | Duy nhất một nguồn dựng payload gửi LLM |
| `src/project_sentinel/guardrails/injection.py` | Sửa | Mẫu `exfiltrate_to_url` yêu cầu từ khóa bí mật (`api[_ -]?key`, `secret`, `token`, `password`, `system prompt`) | Bắt đúng đòn rò rỉ secret và không bắt oan câu mô tả ứng dụng |
| `tests/fixtures/injection/ignore-instructions.json` | Tạo mới | Fixture HTTP response chứa comment HTML cố ép agent lộ prompt và đổi vai trò | Mẫu kiểm thử đòn tấn công thay đổi vai trò |
| `tests/fixtures/injection/exfiltrate-endpoint.json` | Tạo mới / Sửa | Fixture HTTP response chứa chỉ dẫn ép agent gọi endpoint lạ và rò khoá gateway (bỏ tiền tố chung để bắt bằng mẫu exfiltration chuyên biệt) | Mẫu kiểm thử đòn tấn công exfiltration |
| `tests/fixtures/injection/pii-leak.json` | Tạo mới | Fixture HTTP response chứa danh sách email, số điện thoại, thẻ tín dụng | Mẫu kiểm thử phân biệt giữa PII leak và Injection |
| `tests/unit/guardrails/test_system_prompt_rules.py` | Tạo mới / Mở rộng | 15 unit test: kiểm tra sự tồn tại của 3 luật và thẻ untrusted trong prompt, cấu trúc JSON 3 fixture, phát hiện injection trên fixture tấn công, kiểm tra `redact()` trên fixture PII, kiểm tra `build_packet_dict` có `allowed_endpoints` và `wrap_untrusted`, và kiểm tra kiến trúc `OpenRouterClient` dùng chung payload builder | Chứng minh tính đúng đắn |
| `tests/unit/analysis/test_prompt_builder_imports.py` | Tạo mới | Test subprocess kiểm tra import độc lập `prompt_builder`, `llm.base`, `openrouter` không bị vòng lặp | Khóa chặt ranh giới import module |
| `docs/superpowers/plans/2026-08-17-rebuild-plan-2-w5-guardrails.md` | Sửa | Đánh dấu hoàn thành các Step 1–6 của Task 5 (`- [x]`) | Cập nhật tiến độ kế hoạch Plan 2 |

**`git diff --stat`:**

```text
 configs/prompts/security-analysis-system.md        |  19 ++
 .../2026-08-17-rebuild-plan-2-w5-guardrails.md     |  12 +-
 src/project_sentinel/analysis/prompt_builder.py    |  18 +-
 src/project_sentinel/guardrails/injection.py       |   1 +
 src/project_sentinel/llm/base.py                   |  27 ++-
 src/project_sentinel/llm/openrouter.py             |  17 +-
 tests/fixtures/injection/exfiltrate-endpoint.json  |   9 +
 tests/fixtures/injection/ignore-instructions.json  |   9 +
 tests/fixtures/injection/pii-leak.json             |   9 +
 tests/unit/analysis/test_prompt_builder_imports.py |  16 ++
 tests/unit/guardrails/test_system_prompt_rules.py  | 111 ++++++++++++
 ...plan2-task5-system-prompt-rules-and-fixtures.md | 200 +++++++++++++++++++++
 12 files changed, 419 insertions(+), 29 deletions(-)
```

---

## 4. Làm như thế nào

**Cách tiếp cận:**
1. **Thiết lập 3 luật trong System Prompt:**
   - Xác định rõ nội dung giữa `<untrusted_app_response>` là dữ liệu quan sát, không phải chỉ dẫn.
   - Luật 1: Không thay đổi mục tiêu (Goal hijacking defense).
   - Luật 2: Không tiết lộ system prompt / API key (Secret exfiltration defense).
   - Luật 3: Không gọi endpoint ngoài `allowed_endpoints` (Out-of-scope tool invocation defense).
2. **Khắc phục Vòng lặp Import & Hợp nhất Payload Builder:**
   - Chuyển hàm `build_packet_dict(packet: AnalysisPacket)` vào `llm/base.py` (nơi định nghĩa `AnalysisPacket`), tránh phụ thuộc chéo `analysis.prompt_builder` ➔ `llm.openrouter` ➔ `analysis.prompt_builder`.
   - Bọc `wrap_untrusted()` cho `content` trong `source_evidence`.
   - `PromptBuilder.build()` và `OpenRouterClient.analyze()` đều gọi chung `build_packet_dict()`.
3. **Mẫu Exfiltration chuyên biệt và 3 Fixtures chuẩn JSON:**
   - Thêm `exfiltrate_to_url` yêu cầu từ khóa bí mật kết hợp URL đích ngoài localhost.
   - `exfiltrate-endpoint.json` kiểm chứng đòn exfiltration trực tiếp mà không cần dựa vào tiền tố "New instructions:".
   - `pii-leak.json` kích hoạt `scan()` trả về `verdict="clean"`, đồng thời khi chạy qua `redact()` trả về đủ các sự kiện email, phone, pii.

---

## 5. Output là gì

**Thành phần mới hoặc thay đổi:**

| Loại | Tên | Chữ ký / đường dẫn | Mô tả |
|---|---|---|---|
| Function | `build_packet_dict` | `src/project_sentinel/llm/base.py` | Hàm duy nhất dựng payload JSON an toàn cho LLM |
| Prompt | `security-analysis-system.md` | `configs/prompts/security-analysis-system.md` | System prompt đã bổ sung 3 luật chống injection |
| Fixture | `ignore-instructions.json` | `tests/fixtures/injection/ignore-instructions.json` | Fixture thử nghiệm tấn công ép lộ prompt |
| Fixture | `exfiltrate-endpoint.json` | `tests/fixtures/injection/exfiltrate-endpoint.json` | Fixture thử nghiệm tấn công exfiltrate endpoint |
| Fixture | `pii-leak.json` | `tests/fixtures/injection/pii-leak.json` | Fixture thử nghiệm rò rỉ dữ liệu nhạy cảm |
| Test file | `test_system_prompt_rules.py` | `tests/unit/guardrails/test_system_prompt_rules.py` | 15 unit tests bảo vệ prompt rules, payload builder, và fixtures |
| Test file | `test_prompt_builder_imports.py` | `tests/unit/analysis/test_prompt_builder_imports.py` | Test subprocess bảo vệ chống vòng lặp import |

**Cách chạy:**

```bash
PYTHONPATH=src python3 -m pytest tests/unit/guardrails/test_system_prompt_rules.py tests/unit/analysis/test_prompt_builder_imports.py -v
```

---

## 6. Vì sao chọn cách implement này

**Cách đã chọn:** Đặt hàm `build_packet_dict` tại `llm/base.py` làm Single Source of Truth cho cấu trúc payload gửi LLM, giải quyết triệt để vòng lặp import.

**Lý do:**
- `llm/base.py` là tầng thấp nhất trong package `llm`, không import `analysis`, chỉ import `wrap_untrusted` từ `guardrails`.
- Khắc phục triệt để lỗ hổng provenance: `prompt_sha256` giờ đây chứng thực chính xác 100% payload mà `OpenRouterClient` gửi tới API.
- Đảm bảo `allowed_endpoints` luôn tới được LLM, giúp luật số 3 trong system prompt có giá trị thực thi.

---

## 7. Kiểm chứng

### Bằng chứng test bắt được lỗi trước khi sửa (Fail-first Verification)

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 1 item

tests/unit/analysis/test_prompt_builder_imports.py::test_prompt_builder_imports_cleanly_on_its_own FAILED [100%]

=================================== FAILURES ===================================
________________ test_prompt_builder_imports_cleanly_on_its_own ________________

    def test_prompt_builder_imports_cleanly_on_its_own():
        """Import prompt_builder trước bất cứ thứ gì khác không được gây vòng lặp."""
        for stmt in [
            "import project_sentinel.analysis.prompt_builder",
            "from project_sentinel.analysis.prompt_builder import build_packet_dict",
            "from project_sentinel.llm.base import build_packet_dict",
            "import project_sentinel.llm.openrouter",
        ]:
            r = subprocess.run([sys.executable, "-c", stmt], capture_output=True, text=True, env={"PYTHONPATH": "src"})
>           assert r.returncode == 0, f"{stmt} thất bại:\n{r.stderr}"
E           AssertionError: import project_sentinel.analysis.prompt_builder thất bại:
E             Traceback (most recent call last):
E               File "<string>", line 1, in <module>
E               File "/home/longngx04/VinSOC/project_sentinel_main/src/project_sentinel/analysis/prompt_builder.py", line 13, in <module>
E                 from project_sentinel.llm.base import AnalysisPacket
E               File "/home/longngx04/VinSOC/project_sentinel_main/src/project_sentinel/llm/__init__.py", line 4, in <module>
E                 from project_sentinel.llm.openrouter import OpenRouterClient
E               File "/home/longngx04/VinSOC/project_sentinel_main/src/project_sentinel/llm/openrouter.py", line 14, in <module>
E                 from project_sentinel.analysis.prompt_builder import build_packet_dict
E             ImportError: cannot import name 'build_packet_dict' from partially initialized module 'project_sentinel.analysis.prompt_builder' (most likely due to a circular import)
```

### Bằng chứng test chạy thật sau khi sửa

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/longngx04/VinSOC/project_sentinel_main
configfile: pyproject.toml
collecting ... collected 16 items

tests/unit/analysis/test_prompt_builder_imports.py::test_prompt_builder_imports_cleanly_on_its_own PASSED [  6%]
tests/unit/guardrails/test_system_prompt_rules.py::test_prompt_forbids_changing_goal_from_app_content PASSED [ 12%]
tests/unit/guardrails/test_system_prompt_rules.py::test_prompt_forbids_disclosing_secrets PASSED [ 18%]
tests/unit/guardrails/test_system_prompt_rules.py::test_prompt_forbids_out_of_scope_tools PASSED [ 25%]
tests/unit/guardrails/test_system_prompt_rules.py::test_prompt_declares_untrusted_block_as_data PASSED [ 31%]
tests/unit/guardrails/test_system_prompt_rules.py::test_fixture_exists_and_is_valid_json[ignore-instructions] PASSED [ 37%]
tests/unit/guardrails/test_system_prompt_rules.py::test_fixture_exists_and_is_valid_json[exfiltrate-endpoint] PASSED [ 43%]
tests/unit/guardrails/test_system_prompt_rules.py::test_fixture_exists_and_is_valid_json[pii-leak] PASSED [ 50%]
tests/unit/guardrails/test_system_prompt_rules.py::test_injection_fixtures_are_detected[ignore-instructions] PASSED [ 56%]
tests/unit/guardrails/test_system_prompt_rules.py::test_injection_fixtures_are_detected[exfiltrate-endpoint] PASSED [ 62%]
tests/unit/guardrails/test_system_prompt_rules.py::test_exfiltrate_fixture_is_caught_by_an_exfiltration_pattern PASSED [ 68%]
tests/unit/guardrails/test_system_prompt_rules.py::test_exfiltrate_pattern_catches_direct_leaks_and_ignores_benign_prose PASSED [ 75%]
tests/unit/guardrails/test_system_prompt_rules.py::test_pii_fixture_is_not_flagged_as_injection PASSED [ 81%]
tests/unit/guardrails/test_system_prompt_rules.py::test_pii_fixture_is_actually_redacted PASSED [ 87%]
tests/unit/guardrails/test_system_prompt_rules.py::test_llm_payload_contains_allowed_endpoints_and_wrapped_evidence PASSED [ 93%]
tests/unit/guardrails/test_system_prompt_rules.py::test_openrouter_uses_the_same_payload_builder PASSED [100%]

============================== 16 passed in 0.45s ==============================
```

```text
$ PYTHONPATH=src python3 -c "from project_sentinel.llm.base import build_packet_dict, AnalysisPacket; print(sorted(build_packet_dict(AnalysisPacket(group_key='g')).keys()))"
['allowed_endpoints', 'finding_group', 'group_key', 'knowledge_hits', 'output_language', 'output_schema', 'source_evidence', 'task']
```

| Lệnh | Exit code | Kết quả |
|---|---|---|
| `PYTHONPATH=src pytest tests/unit/guardrails/test_system_prompt_rules.py tests/unit/analysis/test_prompt_builder_imports.py -v` | 0 | **16 passed** in 0.45s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" tests/unit/guardrails tests/unit/llm tests/unit/analysis -v` | 0 | **143 passed**, 2 deselected in 0.82s |
| `PYTHONPATH=src pytest -m "not llm and not live_gateway" -q tests` | 0 | **261 passed**, 13 deselected in 1.93s |
| `python3 -m compileall -q src/project_sentinel tests` | 0 | Thành công, không có lỗi cú pháp |
| `grep -r 'Week\|week' src/project_sentinel/ configs/prompts/` | 0 | **0 match** (không chứa week token) |

---

## 8. Cần người review kỹ ở đâu

- **Kiến trúc Import Module:** `build_packet_dict` được đặt tại `src/project_sentinel/llm/base.py`. `llm` không import bất cứ thứ gì từ `analysis`, ngăn chặn hoàn toàn khả năng phát sinh vòng lặp import khi các module phân tích được nạp độc lập.
- **Khắc phục lỗi Provenance Hash:** Việc `prompt_sha256` trước đây được tính trên `packet_dict` của `PromptBuilder` trong khi `OpenRouterClient` tự dựng `packet_dict` riêng (thiếu `allowed_endpoints`) là một lỗ hổng provenance có sẵn từ các sprint trước. Việc gom về hàm duy nhất `build_packet_dict()` đã sửa dứt điểm vấn đề này.
- **Việc còn nợ:** Task 6 của Plan 2 (`guardrails/events.py` — ghi nhận sự kiện bảo mật).
- **Câu hỏi cho người dùng:** Không có.
