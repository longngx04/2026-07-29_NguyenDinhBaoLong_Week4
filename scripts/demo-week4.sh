#!/usr/bin/env bash
#
# Week 4 demo — API Gateway & Safe Test Request Tool
#
# Usage:
#   ./scripts/demo-week4.sh                 # full demo, tears containers down at the end
#   ./scripts/demo-week4.sh --pause         # wait for Enter between sections (live presentation)
#   ./scripts/demo-week4.sh --keep-up       # leave gateway/webgoat running afterwards
#
set -uo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

PAUSE=0
KEEP_UP=0
for arg in "$@"; do
  case "$arg" in
    --pause) PAUSE=1 ;;
    --keep-up) KEEP_UP=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
GATEWAY=http://127.0.0.1:9080
WEBGOAT_DIRECT=http://127.0.0.1:8080
AUDIT_LOG=artifacts/gateway/requests.log.jsonl
PYTHON=$(command -v "$project_root/.venv/bin/python3" 2>/dev/null || command -v python3)
checks_passed=0
checks_failed=0

section() { printf '\n%s\n%s %s %s\n%s\n' "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}" "${BOLD}${CYAN}$1${RESET}" "${DIM}—${RESET}" "${DIM}$2${RESET}" "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}"; }
run() { printf '%s$ %s%s\n' "$DIM" "$*" "$RESET"; "$@"; }
pause() { if [ "$PAUSE" = 1 ]; then printf '\n%s[Enter để tiếp tục]%s ' "$DIM" "$RESET"; read -r _; fi; }

# Compare an observed HTTP status against the expected one and record the verdict.
expect_status() {
  local label="$1" expected="$2" observed="$3"
  if [ "$observed" = "$expected" ]; then
    printf '  %s✔%s %-46s expected=%-4s observed=%s%s%s\n' "$GREEN" "$RESET" "$label" "$expected" "$BOLD" "$observed" "$RESET"
    checks_passed=$((checks_passed + 1))
  else
    printf '  %s✘%s %-46s expected=%-4s observed=%s%s%s\n' "$RED" "$RESET" "$label" "$expected" "$BOLD" "$observed" "$RESET"
    checks_failed=$((checks_failed + 1))
  fi
}

status_of() { curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 "$@" || true; }

# ─────────────────────────────────────────────────────────────
# 0. Preflight
# ─────────────────────────────────────────────────────────────
section "0. Preflight" "kiểm tra Gateway key, LLM key, docker, python"

API_KEY="${SENTINEL_GATEWAY_API_KEY:-$(sed -n 's/^SENTINEL_GATEWAY_API_KEY=//p' .env 2>/dev/null)}"
API_KEY="${API_KEY:-$(sed -n 's/^SENTINEL_API_KEY=//p' .env 2>/dev/null)}"
if [ -z "$API_KEY" ]; then
  printf '%sThiếu SENTINEL_GATEWAY_API_KEY.%s Thêm vào .env rồi chạy lại:\n\n' "$RED" "$RESET"
  printf "  printf 'SENTINEL_GATEWAY_API_KEY=%%s\\\\n' \"\$(openssl rand -hex 24)\" >> .env\n\n"
  exit 2
fi
export SENTINEL_GATEWAY_API_KEY="$API_KEY"
LLM_KEY="${LLM_API_KEY:-$(sed -n 's/^LLM_API_KEY=//p' .env 2>/dev/null)}"
if [ -z "$LLM_KEY" ]; then
  printf '%sThiếu LLM_API_KEY.%s Phase 6 demo bắt buộc dùng real proposer.\n' "$RED" "$RESET"
  exit 2
fi
export LLM_API_KEY="$LLM_KEY"
command -v docker >/dev/null || { printf '%sdocker không có sẵn%s\n' "$RED" "$RESET"; exit 2; }
printf '  Gateway key   : %s<redacted>%s (%d ký tự)\n' "$BOLD" "$RESET" "${#API_KEY}"
printf '  LLM key       : %s<redacted>%s (%d ký tự)\n' "$BOLD" "$RESET" "${#LLM_KEY}"
printf '  Python        : %s\n' "$PYTHON"
printf '  Gateway origin: %s\n' "$GATEWAY"
pause

# ─────────────────────────────────────────────────────────────
# 1. Bản đồ file
# ─────────────────────────────────────────────────────────────
section "1. Các file đã implement" "mở sẵn những file này khi demo"
cat <<'FILEMAP'
  Gateway boundary (hạ tầng)
    infra/docker/gateway/Dockerfile                       nginx:1.27-alpine
    infra/docker/gateway/nginx.conf                       limit_req_zone 30r/m, log_format
    infra/docker/gateway/templates/default.conf.template  API key + allowlist + 401/403/405/429
    docker-compose.yml                                    chỉ gateway publish port; webgoat internal-only

  Cấu hình đã review (deny-by-default)
    configs/gateway/endpoint-allowlist.json               2 endpoint, có trường "source" dẫn nguồn
    configs/verification/endpoint-catalog.json            catalog cho proposer + IAM resolver
    configs/verification/probe-objectives.json            objective version-controlled
    configs/verification/probe-templates.json             3 probe template an toàn

  Agent + IAM + Python Safe Request Tool
    src/project_sentinel/verification/proposer.py         gọi real LLM, strict proposal schema
    src/project_sentinel/verification/resolver.py         re-resolve mọi field, deny-by-default
    src/project_sentinel/gateway/allowlist.py             nạp allowlist, fail-closed
    src/project_sentinel/gateway/payloads.py              4 payload an toàn
    src/project_sentinel/gateway/request_log.py           audit log, chặn cứng field nhạy cảm
    src/project_sentinel/gateway/cli.py                   CLI demo cho operator
    src/project_sentinel/verification/templates.py        registry probe template
    src/project_sentinel/verification/policy.py           validate deny-by-default trước khi ra mạng
    src/project_sentinel/verification/rate_limit.py       token bucket phía client
    src/project_sentinel/verification/transport.py        timeout 5s, cap 64 KiB, tắt redirect
    src/project_sentinel/verification/gateway_client.py   đường thực thi HTTP DUY NHẤT

  Test
    tests/unit/gateway/                                   allowlist, payload, log redaction, CLI
    tests/unit/verification/                              policy, transport, rate limit, executor
    tests/integration/test_gateway_live.py                acceptance thật (opt-in)
FILEMAP
pause

# ─────────────────────────────────────────────────────────────
# 2. Pure contract guards
# ─────────────────────────────────────────────────────────────
section "2. Contract guards" "không doubles, không Week 3 coupling"
run "$PYTHON" -m pytest \
  tests/test_no_doubles.py \
  tests/unit/verification/test_no_week3_imports.py -q
pause

# ─────────────────────────────────────────────────────────────
# 3. Khởi động topology
# ─────────────────────────────────────────────────────────────
section "3. Khởi động Docker" "gateway + webgoat"
run docker compose up --detach --build gateway webgoat
# Recreate the gateway so the nginx template is rendered with the current API key.
docker compose up --detach --force-recreate --no-deps gateway >/dev/null
printf '  Chờ gateway sẵn sàng'
gateway_ready=0
for _ in $(seq 1 60); do
  if [ "$(status_of "$GATEWAY/WebGoat/actuator/health")" = "401" ]; then
    gateway_ready=1
    break
  fi
  printf '.'; sleep 1
done
if [ "$gateway_ready" = 1 ]; then
  printf ' %ssẵn sàng%s\n\n' "$GREEN" "$RESET"
  checks_passed=$((checks_passed + 1))
else
  printf ' %skhông sẵn sàng%s\n\n' "$RED" "$RESET"
  checks_failed=$((checks_failed + 1))
fi
run docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
printf '\n  %sChỉ gateway có host port. webgoat không có dòng 0.0.0.0/127.0.0.1 nào.%s\n' "$DIM" "$RESET"
pause

# ─────────────────────────────────────────────────────────────
# 4. WebGoat không thể bị gọi trực tiếp
# ─────────────────────────────────────────────────────────────
section "4. Cách ly target" "WebGoat chỉ nằm trên mạng nội bộ Docker"
direct=$(status_of "$WEBGOAT_DIRECT/WebGoat/actuator/health")
expect_status "gọi thẳng WebGoat :8080 từ host" "000" "$direct"
printf '  %s000 = connection refused: không có host port nào được publish cho WebGoat.%s\n' "$DIM" "$RESET"
pause

# ─────────────────────────────────────────────────────────────
# 5. Gateway chặn ở 4 tầng
# ─────────────────────────────────────────────────────────────
section "5. Guardrail tại Gateway" "API key / allowlist path / method"
expect_status "không có API key"                    "401" "$(status_of "$GATEWAY/WebGoat/actuator/health")"
expect_status "API key sai"                         "401" "$(status_of -H 'X-Sentinel-API-Key: wrong-key-123' "$GATEWAY/WebGoat/actuator/health")"
expect_status "path ngoài allowlist (/registration)" "403" "$(status_of -H "X-Sentinel-API-Key: $API_KEY" "$GATEWAY/WebGoat/registration")"
expect_status "method không cho phép (DELETE)"      "405" "$(status_of -X DELETE -H "X-Sentinel-API-Key: $API_KEY" "$GATEWAY/WebGoat/actuator/health")"
expect_status "key đúng + path/method hợp lệ"       "200" "$(status_of -H "X-Sentinel-API-Key: $API_KEY" "$GATEWAY/WebGoat/actuator/health")"
pause

# ─────────────────────────────────────────────────────────────
# 6. Agent proposal -> IAM resolver -> Gateway
# ─────────────────────────────────────────────────────────────
section "6. Agent → IAM → Gateway" "accepted proposal bên cạnh denied proposal"
printf '  %s6a. Real LLM đề xuất objective đã review; IAM resolve; tool execute%s\n' "$BOLD" "$RESET"
if run "$PYTHON" -m project_sentinel.cli probe --objective-id obj-health-check \
  && "$PYTHON" - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/verification/run-summary.json").read_text(encoding="utf-8"))
if summary.get("decision") != "PLANNED":
    raise SystemExit(f"expected PLANNED, got {summary.get('decision')}")
if summary.get("status") not in {"OBSERVED", "REACHABLE"}:
    raise SystemExit(f"expected an observed/reachable result, got {summary.get('status')}")
print(f"Accepted candidate={summary['candidate_id']} result={summary['status']}")
PY
then
  checks_passed=$((checks_passed + 1))
else
  checks_failed=$((checks_failed + 1))
fi

printf '\n  %s6b. Proposal adversarial bị IAM deny trước network%s\n' "$BOLD" "$RESET"
if "$PYTHON" - <<'PY'
import json
from pathlib import Path

from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.verification.resolver import ResolutionDenial, resolve_proposal
from project_sentinel.verification.templates import ProbeTemplateRegistry

catalog = json.loads(Path("configs/verification/endpoint-catalog.json").read_text(encoding="utf-8"))
allowlist = Allowlist.from_json("configs/gateway/endpoint-allowlist.json")
templates = ProbeTemplateRegistry.from_json("configs/verification/probe-templates.json")
proposal = {
    "objective_id": "obj-health-check",
    "proposal_id": "prop-demo-denied",
    "endpoint_id": "ep_unreviewed",
    "reason": "Demonstrate exact IAM denial",
    "method": "GET",
    "template_id": "tmpl_health_get",
    "payload_type": None,
    "headers": {},
    "parameters": {},
}
outcome = resolve_proposal(proposal, catalog, allowlist, templates)
if not isinstance(outcome, ResolutionDenial):
    raise SystemExit("adversarial proposal was not denied")
print(f"IAM decision=NOT_PLANNABLE reason_code={outcome.reason_code}")
PY
then
  checks_passed=$((checks_passed + 1))
else
  checks_failed=$((checks_failed + 1))
fi
pause

# ─────────────────────────────────────────────────────────────
# 7. Rate limit
# ─────────────────────────────────────────────────────────────
section "7. Rate limit" "nginx limit_req 30r/m, burst=5 -> 429"
printf '  Chờ token bucket hồi lại...'; sleep 12; printf ' xong\n'
printf '  10 request liên tiếp với key hợp lệ:\n    '
for i in $(seq 1 10); do
  printf '%s ' "$(status_of -H "X-Sentinel-API-Key: $API_KEY" "$GATEWAY/WebGoat/actuator/health")"
done
printf '\n\n  %sHết burst budget thì nginx trả 429 ngay, WebGoat không hề nhận request.%s\n' "$DIM" "$RESET"
pause

# ─────────────────────────────────────────────────────────────
# 8. Audit log không chứa secret
# ─────────────────────────────────────────────────────────────
section "8. Audit log" "$AUDIT_LOG"
if [ -f "$AUDIT_LOG" ]; then
  printf '  Bản ghi gần nhất:\n'
  tail -n 1 "$AUDIT_LOG" | "$PYTHON" -m json.tool | sed 's/^/    /'
  printf '\n  Tìm API key trong toàn bộ log (canary check):\n'
  if grep -q -- "$API_KEY" "$AUDIT_LOG"; then
    printf '  %s✘ API KEY BỊ LỘ TRONG LOG%s\n' "$RED" "$RESET"; checks_failed=$((checks_failed + 1))
  else
    printf '  %s✔%s không tìm thấy API key trong log\n' "$GREEN" "$RESET"; checks_passed=$((checks_passed + 1))
  fi
  if grep -qiE '"(headers|body|authorization|cookie)"' "$AUDIT_LOG"; then
    printf '  %s✘ log chứa header/body%s\n' "$RED" "$RESET"; checks_failed=$((checks_failed + 1))
  else
    printf '  %s✔%s không có header/body/cookie nào được ghi\n' "$GREEN" "$RESET"; checks_passed=$((checks_passed + 1))
  fi
  if tail -n 1 "$AUDIT_LOG" | grep -q '"response_preview"'; then
    printf '  %s✔%s audit có bounded response_preview\n' "$GREEN" "$RESET"; checks_passed=$((checks_passed + 1))
  else
    printf '  %s✘ audit thiếu response_preview%s\n' "$RED" "$RESET"; checks_failed=$((checks_failed + 1))
  fi
else
  printf '  %sChưa có audit log%s\n' "$RED" "$RESET"
fi
pause

# ─────────────────────────────────────────────────────────────
# Kết thúc
# ─────────────────────────────────────────────────────────────
section "Tổng kết" "$checks_passed pass / $checks_failed fail"
if [ "$KEEP_UP" = 1 ]; then
  printf '  Container vẫn chạy. Tắt bằng: %sdocker compose down%s\n' "$BOLD" "$RESET"
else
  printf '  Dọn dẹp container...\n'
  docker compose down >/dev/null 2>&1
  printf '  %s✔%s đã tắt gateway và webgoat\n' "$GREEN" "$RESET"
fi
[ "$checks_failed" -eq 0 ] || exit 1
