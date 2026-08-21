#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# Orchestrator truyen duong dan raw.json cua chinh lan chay do. Truoc day script
# bo qua argument nay va luon ghi vao artifacts/raw/opengrep.json, nen step_scan
# khong tim thay file no vua yeu cau, phai copy lai ban cu va ghi
# `used_fallback: true` cho mot ket qua vua quet xong. Provenance noi sai su that.
report_path="${1:-$project_root/artifacts/raw/opengrep.json}"
compose_file="$project_root/docker-compose.yml"

mkdir -p "$(dirname -- "$report_path")" "$project_root/artifacts/raw"
temporary_report=$(mktemp "$project_root/artifacts/raw/.opengrep.json.XXXXXX")

cleanup() {
  rm -f -- "$temporary_report"
}
trap cleanup EXIT

compose=(
  docker compose
  --project-directory "$project_root"
  --file "$compose_file"
  --profile scan
)

"${compose[@]}" build scanner
"${compose[@]}" run --rm --no-deps scanner \
  opengrep scan \
  --config configs/opengrep \
  --exclude 'target/**' \
  --json \
  benchmarks/targets/webgoat \
  >"$temporary_report"

jq -e '
  type == "object"
    and (.results | type == "array")
    and (.errors | type == "array")
    and all(.results[]?;
      (.path | type == "string")
      and (.path | (startswith("benchmarks/targets/webgoat/") or startswith("targets/webgoat/")))
    )
' "$temporary_report" >/dev/null

mv -f -- "$temporary_report" "$report_path"
trap - EXIT

printf 'OpenGrep report: %s\n' "$report_path"
