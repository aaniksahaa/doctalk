#!/usr/bin/env bash
set -euo pipefail

IN_DIR="data/search_results"
OUT_DIR="data/video_ids"

mkdir -p "$OUT_DIR"

for FILE in "$IN_DIR"/*.json; do
  BASENAME=$(basename "$FILE" .json)
  OUT_FILE="$OUT_DIR/${BASENAME}.txt"

  python scripts/extract-video-ids.py "$FILE" "$OUT_FILE"
done

echo "✅ All video IDs extracted"
