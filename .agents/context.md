# Project Sentinel — Week 4 Context

> **Source of truth:** `docs/[NCUD-GPAI] VinUni x VinSOC 6-week of Project Sentinnel-1.pdf`, mục “Tuần 4: API Gateway và kiểm thử request an toàn”.
>
> **Ngày đồng bộ:** 2026-08-13
>
> **Branch:** `feat/week4`
>
> **Trạng thái:** Tài liệu triển khai đã được hiệu chỉnh; implementation hiện tại phải được đánh giá lại theo contract này.

## 1. Mục tiêu Week 4

Cho phép Security Analysis Agent đề xuất và thực thi một số HTTP request kiểm thử an toàn **thông qua API Gateway** trước WebGoat.

Week 4 không chỉ là một HTTP client gọi loopback. Luồng bắt buộc là:

```text
artifacts/analysis/security-analysis.jsonl
            |
            v
grounded request candidate planner
            |
            v
strict candidate validation
            |
            v
Python Safe Request Tool
            |
            v
API Gateway (API key + method/path allowlist + rate limit)
            |
            v
WebGoat on an internal Docker network
            |
            v
bounded response + sanitized JSONL audit log
```

Một request Week 4 hợp lệ phải đồng thời:

1. Có provenance từ analyzed finding và verification proposal của Week 3.
2. Dùng một `endpoint_id` có thật trong inventory/allowlist đã review.
3. Dùng method, headers và payload template được allowlist cho endpoint đó.
4. Đi qua Gateway, có API key hợp lệ và chịu rate limit.
5. Không thay đổi dữ liệu thật, không truy cập hệ thống, không chứa exploit payload.
6. Có timeout và giới hạn số byte response được đọc.
7. Sinh audit record không chứa API key, secret hoặc raw sensitive body.

## 2. Deliverables bắt buộc theo PDF

| Deliverable | Path dự kiến | Bằng chứng hoàn thành |
|---|---|---|
| API Gateway | `infra/docker/gateway/` + `docker-compose.yml` | Request được proxy tới WebGoat; WebGoat không thể bị tool gọi trực tiếp |
| API key riêng cho testing tool | `.env.example` + runtime env | Missing/wrong key bị từ chối; secret không nằm trong git/log |
| Endpoint allowlist | `configs/gateway/endpoint-allowlist.json` | Unknown endpoint/method bị reject ở tool và Gateway |
| Probe template inventory | `configs/verification/probe-templates.json` | Candidate chỉ tham chiếu template đã review |
| Python Safe Request Tool | `src/project_sentinel/verification/` | GET/POST/header/status/partial response hoạt động qua Gateway |
| Request limits | Gateway + tool config | Rate limit, timeout và response-size cap có test |
| Safe payload policy | schema + validator + fixtures | Chỉ empty, wrong-type, special-character, bounded-long-string templates |
| Audit log | `artifacts/verification/request-log.jsonl` | Metadata đầy đủ; không log API key/raw secret |
| End-to-end demo | CLI/Makefile + README | Agent proposal -> candidate -> Gateway -> WebGoat -> result/log |

## 3. Scope bắt buộc

### 3.1 API Gateway

- Đặt Gateway trước WebGoat trong `docker-compose.yml`.
- Gateway là entry point duy nhất của Safe Request Tool.
- Chỉ Gateway bind host loopback, ví dụ `127.0.0.1:8080`.
- WebGoat chỉ expose port trên Docker network nội bộ; không publish host port trong default profile.
- Gateway kiểm tra API key, allowlist method/path và rate limit trước khi proxy.
- Gateway access log không chứa API key, request body hoặc full response body.

Nginx là lựa chọn mặc định vì nhỏ và đủ scope. Dùng image được pin version; ưu tiên digest khi chốt implementation. Template config nhận API key từ runtime environment, không hard-code secret.

### 3.2 Endpoint inventory và allowlist

Không được suy đoán endpoint từ CWE, title, source filename hoặc prose do LLM sinh ra.

Mỗi entry tối thiểu có:

```json
{
  "endpoint_id": "webgoat-start",
  "method": "GET",
  "path": "/WebGoat/start.mvc",
  "safe_payload_templates": [],
  "max_response_bytes": 65536,
  "purpose": "Application reachability only",
  "source": "benchmarks/targets/webgoat/.../MvcConfiguration.java:55"
}
```

Rules:

- `path` phải được xác minh từ source/router inventory hoặc tài liệu Week 1.
- Allowlist là deny-by-default.
- Method là một phần của identity; GET allowlist không tự động cho phép POST.
- Path variable/query names phải được mô tả rõ; không cho arbitrary URL.
- Tool và Gateway đều enforce; Gateway là security boundary cuối cùng.

### 3.3 Request candidate planner

Input là từng record đã validate theo `schemas/security-analysis-record.schema.json`.

Planner không parse prose để lấy arbitrary URL/payload. Nó chỉ có thể:

1. Map một grounded verification proposal sang `probe_template_id` đã review; hoặc
2. Trả `NOT_PLANNABLE` với lý do rõ ràng.

Candidate phải giữ:

- `analysis_record_id = analysis_id`
- `group_id = group_key`
- `source_finding_ids`
- `verification_step_index` hoặc grounded rationale
- `endpoint_id`
- `probe_template_id`
- method/path/payload sau khi resolve từ inventory

Không có mapping hợp lệ thì không gửi request.

### 3.4 Python Safe Request Tool

Tool hỗ trợ:

- GET.
- POST chỉ với endpoint và safe payload template được allowlist.
- Header allowlist; caller không được override `Host`, `Authorization`, API-key header hoặc hop-by-hop headers.
- Đọc status code và tối đa `max_response_bytes`.
- Timeout có default và hard maximum.
- Không tự follow redirect ra ngoài Gateway origin; redirect phải được trả về như evidence hoặc validate lại.
- Connection/timeout/HTTP errors trở thành structured result, không crash và không lộ secret.

Tool không hỗ trợ `PUT`, `PATCH`, `DELETE`, arbitrary body, arbitrary URL hoặc file upload trong Week 4.

### 3.5 Safe payload policy

Payload được phép chỉ đến từ version-controlled templates, ví dụ:

- empty string/value;
- bounded long string;
- non-control special characters;
- wrong primitive type trong test fixture;
- benign marker có request ID.

Payload bị cấm:

- shell/SQL/deserialization exploit payload;
- path traversal hoặc file access;
- credential/token guessing;
- dữ liệu làm thay đổi/xóa trạng thái thật;
- payload do LLM tự do tạo;
- payload vượt giới hạn byte/field count.

### 3.6 Rate limit, timeout và response cap

- Baseline Week 4: 30 requests/phút/API-key, burst tối đa 5; mọi thay đổi phải qua review.
- Request body tối đa 16 KiB; một bounded-long-string field tối đa 1 KiB.
- Tool timeout mặc định 5 giây, hard maximum 10 giây; không retry POST tự động.
- Response preview mặc định/tối đa Week 4 là 64 KiB.
- Tool đọc `max_response_bytes + 1`, đánh dấu `truncated=true`, không gọi `read()` không giới hạn.
- Response body chỉ lưu bounded preview khi thật sự cần; ưu tiên hash, content type, byte count và safe excerpt.

### 3.7 Audit logging

Mỗi execution ghi một JSONL record gồm:

- timestamp UTC, request ID;
- analysis/group/finding provenance;
- endpoint ID, method, payload template ID;
- status, latency, response byte count, truncation flag;
- error class và policy decision.

Không log:

- API key hoặc API-key header;
- `Authorization`, cookie/session token;
- full request headers;
- raw sensitive request/response body;
- secrets từ environment/exception.

## 4. Out of scope Week 4

- Human approval UI/Approve-Reject flow: Week 5.
- Prompt Injection response filter: Week 5.
- General PII/secret redaction pipeline: Week 5; Week 4 vẫn phải không log API key.
- Public/external target scanning.
- Automated exploitation hoặc destructive payload.
- Arbitrary LLM tool access, shell or filesystem writes.
- Multi-Agent, MCP/A2A, GraphRAG hoặc vector database.
- Chỉnh WebGoat để demo pass.

## 5. Data contracts

### 5.1 Candidate states

- `PLANNED`: grounded, schema-valid, allowlisted and safe.
- `NOT_PLANNABLE`: thiếu endpoint/template/provenance; không execute.
- `REJECTED_POLICY`: có proposal nhưng vi phạm method/path/header/payload policy.

### 5.2 Execution result states

- `REACHABLE`: Gateway trả response hợp lệ; chỉ chứng minh reachability.
- `OBSERVED`: expected benign indicator/status được quan sát.
- `INCONCLUSIVE`: response không đủ để kết luận.
- `DENIED`: Gateway/tool policy từ chối.
- `UNREACHABLE`: timeout/connection failure.
- `FAILED`: internal/schema/I/O failure.

Không dùng “verified vulnerability” nếu request chỉ chứng minh endpoint reachable.

### 5.3 Output artifacts

```text
artifacts/verification/
  verification-plan.json
  verification-results.jsonl
  request-log.jsonl
  run-summary.json
```

Mọi write phải atomic. Runtime artifacts phải được ignore, trừ fixture/baseline được phê duyệt rõ ràng.

## 6. Required tests

Unit/CI tests chạy offline, không khởi động Docker và không gọi network thật.

Tối thiểu:

1. Valid GET candidate qua fake transport.
2. Valid safe POST template qua fake transport.
3. Invalid Week 3 record bị reject trước planning.
4. Unknown endpoint/path/method bị reject trước network.
5. Missing/wrong Gateway API key không được gửi/log.
6. `PUT/PATCH/DELETE` bị reject.
7. Unsafe/arbitrary payload bị reject.
8. Timeout và connection error tạo structured result.
9. Response vượt cap bị truncate.
10. Redirect không thoát Gateway origin.
11. Rate-limit response được xử lý rõ.
12. Audit log không chứa API key/token/raw secret.
13. Empty input tạo output rỗng hợp lệ, không network.
14. Multi-record ordering và IDs deterministic.

Live Docker acceptance test chạy manual/local:

- missing key -> denied;
- forbidden endpoint -> denied;
- allowlisted GET -> proxied;
- allowlisted safe POST -> proxied;
- rate limit -> 429;
- WebGoat direct host access -> unavailable;
- audit logs contain no API key.

## 7. Definition of Done

Week 4 chỉ Done khi:

- [ ] Gateway chạy trước WebGoat và là host entry point duy nhất.
- [ ] Tool không thể bypass Gateway hoặc gọi arbitrary URL.
- [ ] API key không hard-code, không commit, không log.
- [ ] Endpoint/method/payload allowlist deny-by-default hoạt động ở tool và Gateway.
- [ ] GET và safe POST hoạt động qua Gateway.
- [ ] Rate limit, timeout và response-size cap được enforce/test.
- [ ] Input Week 3, plan và result đều schema/provenance-valid.
- [ ] Không có endpoint hoặc payload được suy đoán từ LLM prose/CWE/path.
- [ ] Request/result audit JSONL được ghi atomic và sanitized.
- [ ] `make agent-test` pass hoàn toàn offline.
- [ ] Manual Docker acceptance evidence được ghi lại.
- [ ] README và architecture mô tả đúng Gateway flow.
- [ ] Không sửa historical reports hoặc WebGoat source.

Baseline configuration:

- Gateway origin: `http://127.0.0.1:8080`.
- Gateway API-key header: `X-Sentinel-API-Key`.
- Rate limit: 30 requests/phút/API-key, burst 5.
- Tool timeout: default 5 giây, hard max 10 giây.
- Request body cap: 16 KiB.
- Response preview cap: 64 KiB.

## 8. Source priority khi có xung đột

1. PDF capstone và yêu cầu người dùng hiện tại.
2. `AGENTS.md`, `.agents/security.md`, file context này.
3. Week 4 design/spec và implementation plan đã đồng bộ.
4. Existing implementation/tests.

Nếu code hoặc test mâu thuẫn với PDF, sửa code/test; không hạ yêu cầu để hợp thức hóa implementation hiện tại.
