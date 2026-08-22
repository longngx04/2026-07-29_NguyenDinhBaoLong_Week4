#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
artifacts_root="$project_root/artifacts"
report_path="${1:-$artifacts_root/raw/zap.json}"
gateway_log="${2:-$artifacts_root/dast/gateway-access.log}"
compose_file="$project_root/docker-compose.yml"

mkdir -p "$artifacts_root/raw" "$artifacts_root/dast" "$(dirname -- "$report_path")" "$(dirname -- "$gateway_log")"


artifacts_real=$(realpath -m -- "$artifacts_root")
report_real=$(realpath -m -- "$report_path")
case "$report_real" in
  "$artifacts_real"/*) ;;
  *)
    printf 'ZAP report must stay under %s\n' "$artifacts_root" >&2
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  printf 'Docker is required to run the real ZAP Baseline scan.\n' >&2
  exit 127
fi

random_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  fi
}

export SENTINEL_DAST_API_KEY="${SENTINEL_DAST_API_KEY:-$(random_key)}"

spider_minutes="${ZAP_SPIDER_MINUTES:-1}"
max_minutes="${ZAP_MAX_MINUTES:-5}"
case "$spider_minutes:$max_minutes" in
  *[!0-9:]*|:*|*:)
    printf 'ZAP_SPIDER_MINUTES and ZAP_MAX_MINUTES must be non-negative integers.\n' >&2
    exit 2
    ;;
esac

temporary_report=$(mktemp "$artifacts_root/raw/.zap.json.XXXXXX")
temporary_log=$(mktemp "$artifacts_root/dast/.gateway-access.log.XXXXXX")
chmod 0666 "$temporary_report"
cp -f "$project_root/infra/docker/zap/requestor-plan.yaml" "$artifacts_root/requestor-plan.yaml"
cleanup() {
  rm -f -- "$temporary_report" "$temporary_log" "$artifacts_root/requestor-plan.yaml"
}
trap cleanup EXIT

report_name=$(basename -- "$temporary_report")
scan_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
compose=(
  docker compose
  --project-directory "$project_root"
  --file "$compose_file"
  --profile dast
)

"${compose[@]}" up --detach --build gateway-dast webgoat

"${compose[@]}" run --rm zap \
  zap-baseline.py \
  -t http://gateway-dast:8081/WebGoat/login \
  -m "$spider_minutes" \
  -T "$max_minutes" \
  -J "raw/$report_name" \
  -I \
  --autooff

"${compose[@]}" run --rm --no-deps zap \
  /zap/zap.sh -cmd -autorun /zap/wrk/requestor-plan.yaml \
  -config replacer.full_list.description=dast-key \
  -config replacer.full_list.enabled=true \
  -config replacer.full_list.matchtype=REQ_HEADER \
  -config replacer.full_list.matchstr=X-Sentinel-DAST-Key \
  -config replacer.full_list.regex=false \
  -config replacer.full_list.replacement="${SENTINEL_DAST_API_KEY}"

jq -e '
  type == "object"
  and (.site | type == "array")
  and all(.site[]?; (.alerts | type == "array"))
' "$temporary_report" >/dev/null

"${compose[@]}" logs --no-color --since "$scan_started_at" gateway-dast >"$temporary_log"
grep -Eq 'channel=dast method=(GET|HEAD) path=/WebGoat/login ' "$temporary_log" || {
  printf 'ZAP produced a report but the DAST Gateway has no ZAP target access evidence.\n' >&2
  exit 1
}

if grep -Fq -- "$SENTINEL_DAST_API_KEY" "$temporary_report" "$temporary_log"; then
  printf 'DAST credential leaked into a report or Gateway log.\n' >&2
  exit 1
fi

mv -f -- "$temporary_report" "$report_real"
mv -f -- "$temporary_log" "$gateway_log"
rm -f -- "$artifacts_root/requestor-plan.yaml"
trap - EXIT

printf 'ZAP Baseline report: %s\n' "$report_real"
printf 'DAST Gateway evidence: %s\n' "$gateway_log"
