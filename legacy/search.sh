#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------
# Config (global)
# ---------------------------------
REGION="BD"
DURATION="long"
SORT="date"

SCRIPT="scripts/search-videos-yt-api.py"
OUT_DIR="data/search_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$OUT_DIR"

# ---------------------------------
# Query list (bash array)
# ---------------------------------
QUERIES=(
  "Sustho Thakun - Rtv Health"
  "Sustho Thakun - ATN Bangla"
  "Shastho Protidin - NTV Health Show"
  "My Health - Mytv"
  "Doctor's Chamber - GTV"
  "DBC NEWS - স্বাস্থ্যকথা"
  "Channel 24 - সুরক্ষায় প্রতিদিন"
  "Doctors On Call - Jamuna TV"
  "Doctor's Chamber - Maasranga TV Program"
  "Sustho Merudondo - Channel 24"
  "Sustha Jibon - Deepto Health Show"
  "Shastha Katha - Banglavision"
  "Boishakhi Health - Boishakhi TV Health"
  "Health Tips - News24"
)

# ---------------------------------
# Loop over queries
# ---------------------------------
for QUERY in "${QUERIES[@]}"; do
  SAFE_NAME=$(echo "$QUERY" | tr ' /' '__')
  OUT_FILE="${OUT_DIR}/${SAFE_NAME}_${TIMESTAMP}.json"

  echo "--------------------------------------"
  echo "Running search for: $QUERY"
  echo "Output: $OUT_FILE"
  echo "--------------------------------------"

  python "$SCRIPT" \
    --query "$QUERY" \
    --region "$REGION" \
    --duration "$DURATION" \
    --sort "$SORT" \
    > "$OUT_FILE"

  sleep 1  # polite delay (rate-limit safety)
done

echo "✅ All searches completed."
