#!/bin/bash
#
# Batch ASR Inference Script
#
# Usage:
#   ./batch_infer.sh --data-dir ./data --model tugstugi
#   ./batch_infer.sh --data-dir ./data/test --model titu
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
DATA_DIR=""
MODEL=""
FRESH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 --data-dir <path> --model <tugstugi|titu> [--fresh]"
            echo ""
            echo "Arguments:"
            echo "  --data-dir    Root directory to search for audio/gt folders"
            echo "  --model       Model name: 'tugstugi' or 'titu'"
            echo "  --fresh       Re-process all datapoints even if already done"
            exit 0
            ;;
        --fresh)
            FRESH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate arguments
if [[ -z "$DATA_DIR" ]]; then
    echo "Error: --data-dir is required"
    exit 1
fi

if [[ -z "$MODEL" ]]; then
    echo "Error: --model is required"
    exit 1
fi

if [[ "$MODEL" != "tugstugi" && "$MODEL" != "titu" ]]; then
    echo "Error: --model must be 'tugstugi' or 'titu'"
    exit 1
fi

# Resolve to absolute path
DATA_DIR="$(cd "$DATA_DIR" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Batch ASR Inference                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Data directory: $DATA_DIR"
echo "  Model: $MODEL"
if $FRESH; then
    echo "  Mode: FRESH (re-processing all)"
else
    echo "  Mode: SKIP existing (use --fresh to override)"
fi
echo ""

# Process all datapoints
main() {
    # Collect datapoints into an array
    local -a datapoints_arr=()
    while IFS= read -r -d '' dp; do
        datapoints_arr+=("$dp")
    done < <(find "$DATA_DIR" -type d -name "audio" -print0 | while IFS= read -r -d '' audio_dir; do
        parent_dir="$(dirname "$audio_dir")"
        gt_dir="$parent_dir/gt"
        if [[ -d "$gt_dir" ]]; then
            printf '%s\0' "$parent_dir"
        fi
    done | sort -uz)
    
    local dp_count=${#datapoints_arr[@]}
    
    if [[ $dp_count -eq 0 ]]; then
        echo "❌ No datapoints found (directories with audio/ and gt/ subdirs)"
        exit 1
    fi
    
    # Count total files
    local total_files=0
    local processed_files=0
    
    for dp in "${datapoints_arr[@]}"; do
        for audio_file in "$dp/audio"/*.wav; do
            [[ -f "$audio_file" ]] && ((total_files++)) || true
        done
        for audio_file in "$dp/audio"/*; do
            [[ -f "$audio_file" ]] || continue
            local ext="${audio_file##*.}"
            local basename="$(basename "${audio_file%.*}")"
            if [[ "${ext,,}" != "wav" && ! -f "$dp/audio/${basename}.wav" ]]; then
                ((total_files++)) || true
            fi
        done
    done
    
    echo "📁 Found $dp_count datapoint(s) with $total_files audio file(s)"
    echo ""
    
    local dp_index=0
    
    # Process each datapoint
    for dp in "${datapoints_arr[@]}"; do
        ((dp_index++)) || true
        local dp_name=$(basename "$dp")
        local parent_name=$(basename "$(dirname "$dp")")
        
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📂 Datapoint [$dp_index/$dp_count]: $parent_name/$dp_name"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        local audio_dir="$dp/audio"
        local pred_dir="$dp/pred/$MODEL"
        local lock_file="$pred_dir/infer.lock"
        
        # Check if already processed (skip unless --fresh)
        if [[ -f "$lock_file" ]] && ! $FRESH; then
            echo "  ⏭️  Already processed (infer.lock found). Skipping..."
            echo ""
            continue
        fi
        
        mkdir -p "$pred_dir"
        
        local stats_file="$pred_dir/stats.csv"
        echo "filename,wer,cer,mer,wil,is_valid,inference_time_s" > "$stats_file"
        
        # ─────────────────────────────────────────────────────────────
        # STEP 1: Convert non-wav files to wav
        # ─────────────────────────────────────────────────────────────
        echo ""
        echo "  ┌─ Step 1: Ensuring WAV format"
        
        local converted_count=0
        for audio_file in "$audio_dir"/*; do
            [[ -f "$audio_file" ]] || continue
            
            local ext="${audio_file##*.}"
            local basename="$(basename "${audio_file%.*}")"
            local wav_file="$audio_dir/${basename}.wav"
            
            # Skip if already wav
            if [[ "${ext,,}" == "wav" ]]; then
                continue
            fi
            
            # Skip if wav already exists
            if [[ -f "$wav_file" ]]; then
                echo "  │  ✓ ${basename}.wav (already exists)"
                continue
            fi
            
            # Convert to wav
            echo "  │  🔄 Converting: $(basename "$audio_file") → ${basename}.wav"
            if python "$SCRIPT_DIR/convert.py" \
                --input-filepath "$audio_file" \
                --output-filepath "$wav_file" > /dev/null 2>&1; then
                echo "  │  ✓ Converted successfully"
                ((converted_count++)) || true
            else
                echo "  │  ❌ Failed to convert $(basename "$audio_file")"
            fi
        done
        
        if [[ $converted_count -eq 0 ]]; then
            echo "  │  (no conversion needed)"
        fi
        echo "  └─ Done"
        
        # ─────────────────────────────────────────────────────────────
        # STEP 2: Run inference on wav files only
        # ─────────────────────────────────────────────────────────────
        echo ""
        echo "  ┌─ Step 2: Running inference with $MODEL"
        
        # Collect unique basenames (prioritize original files over converted wav)
        declare -A processed_basenames
        local wav_files=()
        
        for audio_file in "$audio_dir"/*; do
            [[ -f "$audio_file" ]] || continue
            
            local ext="${audio_file##*.}"
            local basename="$(basename "${audio_file%.*}")"
            
            # Skip non-wav files
            if [[ "${ext,,}" != "wav" ]]; then
                continue
            fi
            
            # Skip if already processed this basename
            if [[ -n "${processed_basenames[$basename]}" ]]; then
                continue
            fi
            
            processed_basenames[$basename]=1
            wav_files+=("$audio_file")
        done
        
        local wav_count=${#wav_files[@]}
        local wav_index=0
        
        for wav_file in "${wav_files[@]}"; do
            ((wav_index++)) || true
            ((processed_files++)) || true
            local basename="$(basename "${wav_file%.*}")"
            local gt_file="$dp/gt/${basename}.txt"
            local pred_file="$pred_dir/${basename}.txt"
            
            echo "  │"
            echo "  ├─ [$wav_index/$wav_count] ${basename}.wav  (Overall: $processed_files/$total_files)"
            
            # Run inference with timing
            local start_time=$(date +%s.%N)
            
            echo "  │  🎤 Running $MODEL inference..."
            python "$SCRIPT_DIR/${MODEL}.py" \
                --input-filepath "$wav_file" \
                --output-filepath "$pred_file" > /dev/null
            
            local end_time=$(date +%s.%N)
            local inference_time=$(echo "$end_time - $start_time" | bc)
            
            echo "  │  ⏱️  Inference time: ${inference_time}s"
            
            # Calculate metrics if ground truth exists
            local wer="N/A"
            local cer="N/A"
            local mer="N/A"
            local wil="N/A"
            local is_valid="0"
            if [[ -f "$gt_file" ]]; then
                local metrics
                metrics=$(python "$SCRIPT_DIR/wer.py" --gt-file "$gt_file" --pred-file "$pred_file")
                # Parse CSV output: wer,cer,mer,wil,is_valid
                IFS=',' read -r wer cer mer wil is_valid <<< "$metrics"
                if [[ "$is_valid" == "1" ]]; then
                    echo "  │  📊 WER: $wer | CER: $cer | MER: $mer | WIL: $wil"
                else
                    echo "  │  ⚠️  Invalid metrics (empty GT or prediction)"
                fi
            else
                echo "  │  ⚠️  No ground truth file"
            fi
            
            # Append to stats
            echo "${basename},$wer,$cer,$mer,$wil,$is_valid,$inference_time" >> "$stats_file"
            
            echo "  │  ✓ Saved: pred/$MODEL/${basename}.txt"
        done
        
        echo "  └─ Done"
        echo ""
        echo "  📈 Stats saved to: $stats_file"
        echo ""
        
        # Cleanup
        unset processed_basenames
        
        # Create lock file to mark completion
        echo "$(date -Iseconds)" > "$lock_file"
        echo "  🔒 Lock file created: infer.lock"
        
    done
    
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              ✅ Batch Inference Complete                 ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Model: $MODEL"
    echo "  Datapoints: $dp_count"
    echo "  Files processed: $processed_files / $total_files"
    echo ""
}

# Run
main
