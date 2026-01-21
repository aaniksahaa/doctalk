#!/bin/bash
#
# Export inference results without audio files
#
# Usage:
#   ./export.sh --data-dir ./data/test --output-dir ./export
#

set -e

DATA_DIR=""
OUTPUT_DIR=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 --data-dir <path> --output-dir <path>"
            echo ""
            echo "Exports inference results (gt, pred, stats) without audio files."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate
if [[ -z "$DATA_DIR" ]]; then
    echo "Error: --data-dir is required"
    exit 1
fi

if [[ -z "$OUTPUT_DIR" ]]; then
    echo "Error: --output-dir is required"
    exit 1
fi

DATA_DIR="$(cd "$DATA_DIR" && pwd)"

echo "Exporting results..."
echo "  From: $DATA_DIR"
echo "  To:   $OUTPUT_DIR"
echo ""

# Use rsync to copy everything except audio folders
rsync -av --exclude='audio/' --exclude='.temp_chunks/' "$DATA_DIR/" "$OUTPUT_DIR/"

echo ""
echo "✅ Export complete: $OUTPUT_DIR"
