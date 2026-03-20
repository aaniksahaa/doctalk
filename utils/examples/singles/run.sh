#!/usr/bin/env bash
set -euo pipefail

#######################################
# Configuration
#######################################
SUB_LANG="bn"
PROCESS_SCRIPT="process_srt_with_timestamp.py"
HEADER_FILE="header.md"   # in current dir
PROMPT_NAME="prompt.md"   # created inside the video's output dir

#######################################
# Helpers
#######################################
usage() {
  cat <<EOF
Usage: ./run.sh --video-id <YOUTUBE_VIDEO_ID>

Options:
  -v, --video-id    YouTube video ID (required)
  -h, --help        Show this help message

Example:
  ./run.sh --video-id iQGd-XYFfoc
EOF
}

error() {
  echo "❌ Error: $1" >&2
  exit 1
}

sanitize() {
  # Remove unsafe characters for folder names
  echo "$1" | tr '/:' '_' | tr -cd '[:alnum:] _-'
}

#######################################
# Argument parsing
#######################################
VIDEO_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--video-id)
      VIDEO_ID="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      error "Unknown argument: $1"
      ;;
  esac
done

[[ -z "$VIDEO_ID" ]] && error "--video-id is required"

#######################################
# Fetch video title
#######################################
echo "🔎 Fetching video title..."
RAW_TITLE=$(yt-dlp --get-title "$VIDEO_ID")
SAFE_TITLE=$RAW_TITLE
# SAFE_TITLE=$(sanitize "$RAW_TITLE")

#######################################
# Directory setup
#######################################
OUTPUT_DIR="${VIDEO_ID}_${SAFE_TITLE}"
mkdir -p "$OUTPUT_DIR"

RAW_SRT="${OUTPUT_DIR}/${VIDEO_ID}_transcription.srt"
PROCESSED_TXT="${OUTPUT_DIR}/${VIDEO_ID}_transcription-processed-with-timestamp.txt"
PROMPT_MD="${OUTPUT_DIR}/${PROMPT_NAME}"

#######################################
# Main
#######################################
echo "▶️  Video ID   : $VIDEO_ID"
echo "🎬 Video Title: $RAW_TITLE"
echo "📁 Output Dir : $OUTPUT_DIR"

yt-dlp \
  --write-auto-subs \
  --sub-lang "$SUB_LANG" \
  --convert-subs srt \
  --skip-download \
  "$VIDEO_ID" \
  -o "${OUTPUT_DIR}/temp"

SUB_FILE="${OUTPUT_DIR}/temp.${SUB_LANG}.srt"

[[ ! -f "$SUB_FILE" ]] && error "Subtitle file not found: $SUB_FILE"

mv "$SUB_FILE" "$RAW_SRT"
rm -f "${OUTPUT_DIR}/temp"* || true

echo "📝 Subtitle saved: $RAW_SRT"

python "$PROCESS_SCRIPT" "$RAW_SRT" "$PROCESSED_TXT"

#######################################
# Build prompt.md = header.md + processed transcript
#######################################
[[ ! -f "$HEADER_FILE" ]] && error "Header file not found in current dir: $HEADER_FILE"
[[ ! -f "$PROCESSED_TXT" ]] && error "Processed transcript not found: $PROCESSED_TXT"

# Write header, then a blank line, then transcript
cat "$HEADER_FILE" > "$PROMPT_MD"
printf "\n\n" >> "$PROMPT_MD"
cat "$PROCESSED_TXT" >> "$PROMPT_MD"

echo "🧩 Prompt file created: $PROMPT_MD"

echo "✅ Done!"
echo "📄 Processed output:"
echo "   $PROCESSED_TXT"
echo "🧾 Prompt output:"
echo "   $PROMPT_MD"
