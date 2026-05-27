#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL_FILE="${REPO_ROOT}/scripts/verify_matrix_urls.txt"
OUTPUT_ROOT="${REPO_ROOT}/artifacts/anthropic-content-verify"

if [[ ! -f "$URL_FILE" ]]; then
  echo "[ERROR] Missing verify matrix: $URL_FILE"
  exit 1
fi

cmd=(python3 "${REPO_ROOT}/scripts/anthropic_content_pipeline.py"
  --batch-size 5
  --output-root "$OUTPUT_ROOT"
  --translate-mode off
)

url_count=0
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | xargs)"
  [[ -z "$line" ]] && continue
  cmd+=(--target-url "$line")
  url_count=$((url_count + 1))
done < "$URL_FILE"

if [[ "$url_count" -eq 0 ]]; then
  echo "[ERROR] No URLs in verify matrix: $URL_FILE"
  exit 1
fi

echo "[INFO] anthropic:verify:qa — ${url_count} URLs, batch-size 5, QA enabled -> ${OUTPUT_ROOT}"
exec "${cmd[@]}"
