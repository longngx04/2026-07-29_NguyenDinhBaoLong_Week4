# Coding Agent Rules — Project Sentinel Week 4

> **Áp dụng cho:** Antigravity, Codex, OpenCode, Claude Code, Copilot coding agent hoặc bất kỳ autonomous/semi-autonomous coding agent nào làm việc trong repository.
>
> **Priority:** Những rule này là ràng buộc triển khai. Khi có xung đột, ưu tiên: security/scope > data integrity > tests > convenience.

---

## 1. Mandatory startup protocol

Trước khi sửa code, agent phải:

1. Đọc toàn bộ `context.md`.
2. Đọc toàn bộ `implementation_plan.md`.
3. Đọc file rules này (`.agents/rules/coding_agent_rules.md`).
4. Inspect ít nhất:
   - `README.md`
   - `Makefile`
   - `AGENTS.md`
   - `src/project_sentinel/ingestion/normalizer.py`
   - `src/project_sentinel/analysis/pipeline.py`
   - `artifacts/analysis/security-analysis.jsonl`
   - `docker-compose.yml`
5. Tóm tắt trong working notes:
   - files sẽ thay đổi
   - acceptance criteria được cover
   - risks
   - tests sẽ chạy
6. Chỉ bắt đầu implementation sau khi có plan nhỏ theo phase.

Không được đọc một file đơn lẻ rồi tự thiết kế lại toàn hệ thống.

## 2. Scope rules

### 2.1 Agent MUST

- Triển khai Verification Candidate Planner & Safe Probing Pipeline (`src/project_sentinel/verification/`).
- Reuse analyzed findings từ Week 3 (`artifacts/analysis/security-analysis.jsonl`).
- Dùng deterministic preprocessing cho validation, grouping, retrieval và provenance checks.
- Tạo JSONL strict, một analyzed group mỗi dòng.
- Lưu System Prompt trong source control.
- Có mock provider cho tests/CI.
- Có tests cho valid, empty, invalid input; thêm hallucination canary nếu có thể.
- Ghi limitations khi evidence thiếu.

### 2.2 Agent MUST NOT

- Không thêm Multi-Agent.
- Không thêm GraphRAG/vector DB/embedding service.
- Không thêm LangChain/LlamaIndex chỉ để gọi một model.
- Không triển khai API Gateway, HTTP attack tool, HITL UI hoặc PII redaction trong Week 3.
- Không chạy exploit, destructive payload, shell injection test hoặc request vào hệ thống ngoài local authorized target.
- Không sửa source WebGoat để giảm findings hoặc làm demo đẹp hơn.
- Không thêm scanner thứ hai.
- Không tự tạo ground truth hoặc tuyên bố Precision/Recall khi chưa có reviewed labels.
- Không hard-code API key, model secret hoặc base URL.
- Không để LLM có shell, filesystem write, web browsing hoặc arbitrary tool access.
- Không commit generated raw prompts/responses có thể chứa sensitive source.

## 3. Data integrity rules

| Rule | Requirement |
|---|---|
| Raw/normalized preservation | Không sửa `results/normalized/findings.json` bằng tay để phù hợp output mong muốn |
| Provenance | Mọi analyzed record phải trace về input finding IDs |
| Location integrity | Path/line output phải là subset của group input |
| Knowledge integrity | Knowledge ref phải đến từ retrieval results thật |
| Scanner semantics | “Potential” không được đổi thành “confirmed” nếu evidence chưa đủ |
| Missing data | Dùng `null`, empty list hoặc limitation theo schema; không đoán |
| Stable ordering | Same input/config phải tạo same grouping/order |
| Atomic output | Không để partial JSONL khi run fail |

## 4. LLM trust rules

LLM output là **untrusted data**.

Agent phải:

1. Parse structured output.
2. Validate schema.
3. Validate provenance.
4. Reject invented references.
5. Retry tối đa theo config.
6. Fail rõ nếu vẫn invalid.

Agent không được:

- Tin LLM vì response “trông hợp lý”.
- Tự patch invented path/ID/CWE vào value gần nhất mà không báo lỗi.
- Parse JSON bằng regex không an toàn.
- Bỏ qua extra prose/fence mà không có controlled parser.
- Log API key, auth header hoặc full secret-bearing environment.

## 5. Security reasoning rules

### 5.1 Evidence hierarchy

Ưu tiên theo thứ tự:

1. Supplied scanner finding metadata.
2. Source snippet đọc trực tiếp từ allowlisted local target.
3. Local knowledge document được retriever trả về.
4. LLM inference được ghi rõ là inference/unknown.

### 5.2 Severity

- Giữ scanner severity riêng.
- Analysis severity phải có rationale.
- Không map `ERROR -> high` một cách mù quáng trong Agent output.
- Khi chỉ có sink và chưa biết attacker control/reachability, ưu tiên conservative classification và ghi precondition unknown.
- Không tự tính CVSS.

### 5.3 Remediation và verification

Được phép:

- Code review steps.
- Trace source-to-sink.
- Kiểm tra parameterized API.
- Unit/integration test không phá hoại.
- Safe invalid/edge-case input ở mức proposal.

Không được phép:

- PoC weaponized.
- Payload phá hoại.
- Command thực thi shell.
- Hướng dẫn khai thác hệ thống thật.
- Tự gửi HTTP request trong Week 3.

## 6. Path and filesystem rules

- Treat `file_or_url` as untrusted.
- Reject absolute path.
- Resolve dưới configured repository/target root.
- Reject path traversal và symlink escape.
- Chỉ read source; không write vào target.
- Giới hạn file size và source window.
- Output chỉ ghi vào approved output/temp directories.
- Không delete/overwrite user files ngoài generated output.

## 7. Dependency rules

- Reuse standard library và code Week 2 trước.
- Chỉ thêm dependency khi có use case rõ và test được.
- Allowed minimal classes: typed validation, provider SDK, test runner.
- Mỗi dependency mới phải được ghi trong PR/report với lý do.
- Không thêm orchestration framework, database hoặc background service.
- Không chạy `curl | sh`, không execute downloaded script.
- Không pin wildcard/unbounded dependency trong production requirements.

## 8. Code quality rules

### 8.1 Module design

- Module nhỏ, một responsibility.
- Public function có type hints và docstring ngắn.
- Pure functions cho grouping, retrieval query building, provenance validation.
- Side effects chỉ ở CLI/provider/I/O boundaries.
- Không dùng global mutable state.
- Config tập trung, không rải magic constants.
- Error types rõ ràng; không `except Exception: pass`.

### 8.2 Naming

- Python files/functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- JSON fields: `snake_case`.
- IDs/group keys deterministic và documented.

### 8.3 Comments

Comment giải thích **why**, không lặp lại code. Security-sensitive assumptions phải được comment rõ.

## 9. Testing rules

Mọi code change phải có test tương ứng.

### Mandatory assertions

- Output JSONL parse được từng line.
- Output line validate schema.
- Không có invented finding ID/path/line/ref.
- Empty input không gọi LLM.
- Invalid input không gọi LLM.
- Grouping deterministic khi shuffle input.
- Same CWE khác file không bị over-merge.
- Path traversal bị reject.
- FakeLLM invalid response bị reject/retry đúng policy.

### Test isolation

- Không gọi external LLM/network trong unit/CI tests.
- Không phụ thuộc WebGoat container cho phần lớn tests.
- Dùng fixture source tree nhỏ cho evidence tests.
- Test file không dùng secret thật.

Không được xóa/skip test fail để hoàn thành nhanh.

## 10. CI rules

- CI phải chạy không cần secret.
- Real provider smoke test chỉ manual/local hoặc protected workflow riêng.
- Giữ Week 1 scan job hiện tại hoạt động.
- Thêm Agent tests như job độc lập hoặc step rõ ràng.
- Upload artifact chỉ cho output không chứa secret/sensitive prompt.
- Set timeout hợp lý.

## 11. Logging and metrics rules

Được log:

- run ID
- input/group/output counts
- model identifier
- latency
- token counts nếu có
- retry/error class
- prompt hash
- path của generated artifacts

Không log mặc định:

- API key/token/header
- full environment
- full prompt/raw response
- source code ngoài mức cần thiết
- secrets/credentials trong exception

## 12. Change management rules

Trước mỗi thay đổi đáng kể, agent phải nêu:

```text
Change:
Reason:
Files:
Tests:
Risk:
Rollback:
```

Agent phải dừng và xin review trước khi:

- thay đổi normalized input schema Week 2
- thay grouping policy theo hướng broad merge
- thêm dependency/framework lớn
- thêm network/tool access cho LLM
- thay Docker network/port exposure
- thay CI permissions/secrets
- triển khai bất kỳ Week 4/5 feature nào

## 13. Backward compatibility rules

- `make scan`, `make normalize`, `make search` phải tiếp tục hoạt động.
- `week2.search.search()` nếu sửa phải backward-compatible.
- Không rename/remove path Week 1–2 nếu không có migration và approval.
- Không thay baseline 23 findings trong committed normalized report bằng output Agent.
- Agent output ghi vào `results/analysis/`, không ghi đè normalized input.

## 14. Documentation rules

Mọi PR Week 3 phải update phù hợp:

- README commands.
- `docs/report-week3.md`.
- `.env.example` khi config thay đổi.
- JSON schema/version khi output contract thay đổi.
- Known limitations.

Report phải phân biệt:

| Loại statement | Cách viết |
|---|---|
| Observed fact | Nêu evidence/path/metric |
| Model inference | Ghi là inference và confidence |
| Unknown | Nêu rõ missing evidence |
| Future work | Không mô tả như đã triển khai |

## 15. Definition of Done for each task

Một task chỉ Done khi:

- [ ] Code đúng scope.
- [ ] Type/error handling hợp lý.
- [ ] Tests mới pass.
- [ ] Existing tests/commands không regression.
- [ ] Không secret.
- [ ] Output/provenance validate.
- [ ] Docs cập nhật.
- [ ] Agent đã nêu limitations/risks còn lại.

## 16. Forbidden shortcuts

- Hard-code sample output để pass demo.
- Copy toàn bộ knowledge base vào prompt mỗi call.
- Gộp findings chỉ theo title/CWE.
- Dùng LLM để validate chính output của nó.
- Tắt strict schema vì model trả sai.
- Catch mọi exception rồi trả report rỗng.
- Chỉnh fixture để khớp bug implementation.
- Claim “no hallucination” chỉ vì prompt có rule.
- Claim vulnerability confirmed dựa trên scanner message generic.
- Claim precision/recall khi chưa có ground truth.

## 17. Recommended coding-agent execution loop

```text
1. Inspect current state
2. Select one small phase/task
3. State change plan
4. Write/adjust failing test
5. Implement minimal code
6. Run targeted tests
7. Run full Week 2–3 tests
8. Validate generated JSONL
9. Update docs
10. Report evidence, limitations, next task
```

Không làm nhiều phase lớn trong một unreviewed change.

## 18. Final agent response format

Sau mỗi implementation chunk, coding agent phải trả:

```markdown
## Implemented
- ...

## Files changed
- `path`: reason

## Validation
- Command: `...`
- Result: ...

## Security/provenance checks
- ...

## Remaining limitations
- ...

## Next planned step
- ...
```

Không nói “done” nếu chưa chạy/ghi rõ validation evidence.
