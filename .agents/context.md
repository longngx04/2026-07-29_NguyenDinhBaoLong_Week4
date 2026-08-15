# Project Sentinel — Week 4 Context

> **Source of truth:** `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`, mục
> “Tuần 4: API Gateway và kiểm thử request an toàn”.
>
> **Ngày đồng bộ:** 2026-08-15
>
> **Canonical architecture:** `.agents/implementation_plan.md`, Settled Decisions D1–D12.
>
> **Branch triển khai:** `week4-cont`

## 1. Mục tiêu và luồng bắt buộc

Week 4 cho phép một external LLM đề xuất request kiểm thử an toàn từ objective đã được review. Đề
xuất của model là dữ liệu không tin cậy và không bao giờ được thực thi trực tiếp.

```text
configs/verification/probe-objectives.json
  -> proposer + endpoint-catalog.json -> real external LLM
  -> untrusted ProbeProposal
  -> probe-proposal.schema.json
  -> IAM resolver re-resolves every field from reviewed configuration
  -> final policy check
  -> RealTransport at fixed http://127.0.0.1:9080
  -> Nginx Gateway: API key + method/path allowlist + rate/body limits
  -> internal-only WebGoat
  -> bounded result + sanitized request/response audit record
```

Week 4 là sub-project độc lập. Không module nào dưới `gateway/` hoặc `verification/` được import
`analysis`, đọc `artifacts/analysis/`, hoặc dùng `analysis_id`, `group_key` và provenance Tuần 3.
Provenance canonical là `objective_id` + `proposal_id`.

## 2. Deliverables và path canonical

| Deliverable | Path | Contract |
|---|---|---|
| Gateway | `infra/docker/gateway/`, `docker-compose.yml` | Chỉ bind `127.0.0.1:9080`; WebGoat không có host port |
| Gateway secret | runtime `SENTINEL_GATEWAY_API_KEY` | Header nội bộ `X-Sentinel-API-Key`; không commit/log |
| Gateway allowlist | `configs/gateway/endpoint-allowlist.json` | Exact endpoint/method/template tuples, deny-by-default |
| Agent catalog | `configs/verification/endpoint-catalog.json` | Chỉ `ep_health` và `ep_attack`, mỗi entry có `source` thật |
| Probe templates | `configs/verification/probe-templates.json` | GET hoặc benign POST đã review |
| Operator objectives | `configs/verification/probe-objectives.json` | Chọn bằng `--objective-id`; không nhận free text từ CLI |
| LLM proposal | `schemas/probe-proposal.schema.json` | Closed schema; `endpoint_id: null` là decline hợp lệ |
| IAM resolver | `src/project_sentinel/verification/resolver.py` | Re-resolve endpoint, method, template, payload, parameter và header |
| Safe Request Tool | `src/project_sentinel/verification/` | Chỉ gọi fixed Gateway origin qua `RealTransport` |
| Audit log | `artifacts/gateway/requests.log.jsonl` | Request + bounded response metadata, không secret/header/body |
| Run outputs | `artifacts/verification/` | Proposal, result và summary của lần chạy thật |
| Demo | `scripts/demo-week4.sh` | Accepted và denied proposal, Gateway controls, audit checks |

## 3. Settled security boundary

1. Gateway là host entry point duy nhất; origin `http://127.0.0.1:9080` được hard-code và không phải
   candidate input.
2. WebGoat chỉ expose port trên Docker network nội bộ; không publish `8080` ra host.
3. LLM chỉ được chọn ID/enum/value đã có trong catalog; không được sinh URL, host, port, scheme,
   path, header name hoặc literal payload.
4. Tool và Gateway cùng enforce exact method/path allowlist. Chỉ GET và benign POST đã review.
5. `endpoint_id: null` là kết quả `NOT_APPLICABLE`, không phải provider failure.
6. Không tồn tại fake LLM, fake transport, mock response hoặc mock run mode (D9).
7. Thiếu Docker, Gateway, WebGoat hoặc LLM key làm test fail loud; không skip (D10).
8. Denial được chứng minh tại Nginx access-log boundary, không đếm call trên test double (D11).
9. Test tốn token chỉ chạy qua `make llm-test`; các test khác dùng real containers (D12).

## 4. Request và resource limits

- Gateway/tool rate: 30 requests/phút/API key, burst 5.
- Tool timeout: default 5 giây, hard maximum 10 giây.
- Request body cap: 16 KiB; bounded long-string tối đa 1 KiB.
- Transport response cap: 64 KiB, đọc tối đa `cap + 1` để phát hiện truncation.
- Result/audit `response_preview`: tối đa 512 UTF-8 bytes.
- Redirect không được tự follow.
- Không retry POST tự động.
- HTTP 429, hoặc Gateway 503 có marker riêng, map thành `RATE_LIMITED`.

Payload chỉ đến từ registry version-controlled: empty value, bounded long string, non-control
special characters hoặc wrong primitive type. Exploit payload, arbitrary body, file upload,
`PUT/PATCH/DELETE` và thao tác thay đổi dữ liệu thật đều bị cấm.

## 5. Proposal, candidate và result contracts

Validation order:

1. Parse response của real LLM thành JSON.
2. Chuẩn hoá provider envelope generic tại `llm/openrouter.py`; giữ raw response làm audit trail.
3. Validate closed `probe-proposal.schema.json`.
4. Resolver xác minh lại từng field từ catalog, allowlist và template registry.
5. Final policy check tạo request từ reviewed values hoặc trả typed denial.
6. Real transport gửi request qua Gateway và trả bounded structured response.
7. Validate result/audit shape trước khi ghi atomic output.

Candidate decision:

- `PLANNED`: toàn bộ tuple đã resolve và policy-valid.
- `NOT_APPLICABLE`: model decline bằng `endpoint_id: null`.
- `NOT_PLANNABLE`: proposal/schema/catalog/policy không resolve được; không gửi packet.

Execution status:

- `OBSERVED`: status nằm trong expected statuses của reviewed template.
- `REACHABLE`: response hợp lệ nhưng khác expected benign status.
- `RATE_LIMITED`: Gateway rate limit đã chặn.
- `DENIED`: tool hoặc Gateway policy từ chối.
- `INCONCLUSIVE`, `UNREACHABLE`, `FAILED`: response, timeout/connection hoặc internal failure.

Không dùng “verified vulnerability” khi evidence chỉ chứng minh reachability/status.

## 6. Testing contract

`make agent-test` tự khởi động real Gateway + WebGoat và chạy tất cả test không tốn LLM token.
`make llm-test` là target duy nhất chạy test gắn marker `llm`; target mặc định chạy tuần tự để tránh
rate-limit/flakiness của provider. Không test nào skip khi dependency thiếu.

Coverage bắt buộc:

- catalog/allowlist agreement;
- proposal schema và generic OpenRouter envelope normalization;
- no-doubles guard và Week 3 import boundary;
- adversarial resolver denials với Nginx access log không tăng;
- real 200/302/401/403/405/429, timeout, connection error, redirect và truncation;
- response preview 512-byte cap và audit secret rejection;
- real LLM proposer cho mapped objective và injected/unmapped objective;
- direct host access tới WebGoat `127.0.0.1:8080` thất bại.

Canonical commands:

```bash
export SENTINEL_GATEWAY_API_KEY="$(openssl rand -hex 32)"
make scan
make agent-test
make gateway-test
make probe OBJ=obj-health-check
make llm-test
./scripts/demo-week4.sh
make gateway-down
```

## 7. Audit và secret safety

Audit record chỉ chứa request/result identifiers, `objective_id`, `proposal_id`, endpoint/template,
method/path, policy decision, status, latency, byte count, truncation, bounded response preview và
structured error. Logger từ chối header maps, body, API key, cookie, authorization và metadata chưa
được review. Không log raw environment hoặc secret-bearing exception.

Runtime writes chỉ nằm trong `artifacts/gateway/`, `artifacts/verification/` hoặc test `tmp_path` và
được ignore, trừ fixture/baseline được review rõ ràng.

## 8. Out of scope Week 4

- Human Approve/Reject UI và risk approval flow (Week 5).
- Prompt-injection filtering của application response (Week 5).
- General PII/secret redaction pipeline (Week 5).
- Public/external target scanning, exploitation hoặc destructive payload.
- Feeding `response_preview` trở lại bất kỳ LLM prompt nào.
- Multi-Agent, MCP/A2A, GraphRAG, vector database hoặc thay đổi WebGoat source.

## 9. Definition of Done

- Gateway/WebGoat topology đúng và không thể bypass qua host port.
- Key, allowlist, safe payload, rate, timeout và response caps được enforce bằng test thật.
- Proposal -> schema -> resolver -> policy -> Gateway flow hoạt động với real LLM.
- Denial/decline không tạo request ngoài policy.
- Audit có request/response evidence nhưng không chứa key/header/body/secret.
- `make scan` repeatable; dependency install chạy được trong clean environment.
- `make agent-test`, `make llm-test` và demo đạt; CI dùng cùng documented commands.
- Không test double, không skip, không Week 3 coupling, không sửa WebGoat/historical reports.

## 10. Source priority khi có xung đột

1. Yêu cầu người dùng hiện tại và PDF Week 4.
2. Security boundary và Settled Decisions D1–D12 trong `implementation_plan.md`.
3. `AGENTS.md`, `.agents/security.md`, context này và coding rules.
4. Existing implementation/tests.

Nếu code/test/tài liệu cũ mâu thuẫn với thứ tự trên, sửa contract cũ; không hạ guardrail để hợp thức
hoá implementation.
