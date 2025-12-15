#!/usr/bin/env bash
set -euo pipefail

ID_DIR="data/video_ids"
OUT_DIR="data/video_metadata"

mkdir -p "$OUT_DIR"

for ID_FILE in "$ID_DIR"/*.txt; do
  CHANNEL=$(basename "$ID_FILE" .txt)
  CHANNEL_DIR="$OUT_DIR/$CHANNEL"

  mkdir -p "$CHANNEL_DIR"

  while read -r VIDEO_ID; do
    OUT_FILE="$CHANNEL_DIR/${VIDEO_ID}.json"

    if [[ -f "$OUT_FILE" ]]; then
      echo "Skipping $VIDEO_ID (already exists)"
      continue
    fi

    echo "Fetching metadata: $VIDEO_ID"
    yt-dlp -j "https://www.youtube.com/watch?v=$VIDEO_ID" > "$OUT_FILE"

    sleep 1
  done < "$ID_FILE"
done

echo "✅ Metadata fetch complete"
