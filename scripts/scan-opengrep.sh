#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
report_path="$project_root/artifacts/raw/opengrep.json"
scan_compose_file="$project_root/compose.scan.yml"

mkdir -p "$project_root/artifacts/raw"

compose=(
  docker compose
  --project-directory "$project_root"
  --file "$scan_compose_file"
)

"${compose[@]}" build scanner
"${compose[@]}" run --rm --no-deps scanner \
  opengrep scan \
  --config configs/opengrep \
  --exclude 'target/**' \
  --json \
  --output artifacts/raw/opengrep.json \
  benchmarks/targets/webgoat

jq -e '
  type == "object"
    and (.results | type == "array")
    and (.errors | type == "array")
    and all(.results[]?;
      (.path | type == "string")
      and (.path | (startswith("benchmarks/targets/webgoat/") or startswith("targets/webgoat/")))
    )
' "$report_path" >/dev/null

printf 'OpenGrep report: %s\n' "$report_path"
