#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
report_path="$project_root/artifacts/raw/opengrep.json"

mkdir -p "$project_root/artifacts/raw"

env_file_arg=()
if [ -f "$project_root/.env" ]; then
  env_file_arg=(--env-file "$project_root/.env")
fi

docker compose --project-directory "$project_root" "${env_file_arg[@]}" build scanner
docker compose --project-directory "$project_root" "${env_file_arg[@]}" run --rm scanner \
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
