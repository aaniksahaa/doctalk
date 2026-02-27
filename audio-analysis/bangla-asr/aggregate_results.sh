#!/bin/bash
#
# Aggregate Results Script
#
# Combines all prediction results under a data directory and creates summary CSVs.
#
# Usage:
#   ./aggregate_results.sh --data-dir ./data/test
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
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
            echo "Usage: $0 --data-dir <path> [--output-dir <path>]"
            echo ""
            echo "Arguments:"
            echo "  --data-dir    Root directory to scan for prediction results"
            echo "  --output-dir  Directory for output CSVs (default: data-dir)"
            exit 0
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

# Resolve to absolute path
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$DATA_DIR}"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Aggregate Results"
echo "=========================================="
echo "Data directory: $DATA_DIR"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Find all stats.csv files
find_stats_files() {
    find "$DATA_DIR" -type f -name "stats.csv" -path "*/pred/*"
}

# Combine all results
aggregate_results() {
    local combined_file="$OUTPUT_DIR/combined_results.csv"
    local summary_file="$OUTPUT_DIR/model_summary.csv"
    
    echo "datapoint,model,filename,wer,cer,mer,wil,is_valid,inference_time_s" > "$combined_file"
    
    local stats_files
    stats_files=$(find_stats_files)
    
    if [[ -z "$stats_files" ]]; then
        echo "No stats.csv files found in $DATA_DIR"
        exit 1
    fi
    
    # Process each stats file
    while IFS= read -r stats_file; do
        # Extract model name and datapoint path
        local pred_dir="$(dirname "$stats_file")"
        local model="$(basename "$pred_dir")"
        local datapoint_dir="$(dirname "$(dirname "$pred_dir")")"
        local datapoint_name="$(basename "$datapoint_dir")"
        
        # Also include parent directory for uniqueness
        local parent_name="$(basename "$(dirname "$datapoint_dir")")"
        local datapoint_id="${parent_name}/${datapoint_name}"
        
        echo "Processing: $stats_file (model: $model, datapoint: $datapoint_id)"
        
        # Skip header and append data
        tail -n +2 "$stats_file" | while IFS=, read -r filename wer cer mer wil is_valid inference_time; do
            echo "$datapoint_id,$model,$filename,$wer,$cer,$mer,$wil,$is_valid,$inference_time" >> "$combined_file"
        done
        
    done <<< "$stats_files"
    
    echo ""
    echo "Combined results saved to: $combined_file"
    
    # Generate model summary
    echo "model,num_files,valid_files,avg_wer,avg_cer,avg_mer,avg_wil,avg_inference_time_s" > "$summary_file"
    
    # Get unique models
    local models
    models=$(tail -n +2 "$combined_file" | cut -d',' -f2 | sort -u)
    
    while IFS= read -r model; do
        if [[ -z "$model" ]]; then
            continue
        fi
        
        # Extract data for this model
        local model_data
        model_data=$(grep ",$model," "$combined_file" | tail -n +1)
        
        local count=0
        local wer_sum=0
        local cer_sum=0
        local mer_sum=0
        local wil_sum=0
        local time_sum=0
        local valid_count=0
        
        while IFS=, read -r dp m filename wer cer mer wil is_valid inference_time; do
            ((count++)) || true
            
            # Sum inference times
            if [[ -n "$inference_time" && "$inference_time" != "N/A" ]]; then
                time_sum=$(echo "$time_sum + $inference_time" | bc)
            fi
            
            # Sum metrics only if is_valid=1
            if [[ "$is_valid" == "1" ]]; then
                wer_sum=$(echo "$wer_sum + $wer" | bc)
                cer_sum=$(echo "$cer_sum + $cer" | bc)
                mer_sum=$(echo "$mer_sum + $mer" | bc)
                wil_sum=$(echo "$wil_sum + $wil" | bc)
                ((valid_count++)) || true
            fi
        done <<< "$model_data"
        
        # Calculate averages
        local avg_wer="N/A"
        local avg_cer="N/A"
        local avg_mer="N/A"
        local avg_wil="N/A"
        local avg_time="N/A"
        
        if [[ $valid_count -gt 0 ]]; then
            avg_wer=$(echo "scale=6; $wer_sum / $valid_count" | bc)
            avg_cer=$(echo "scale=6; $cer_sum / $valid_count" | bc)
            avg_mer=$(echo "scale=6; $mer_sum / $valid_count" | bc)
            avg_wil=$(echo "scale=6; $wil_sum / $valid_count" | bc)
        fi
        
        if [[ $count -gt 0 ]]; then
            avg_time=$(echo "scale=3; $time_sum / $count" | bc)
        fi
        
        echo "$model,$count,$valid_count,$avg_wer,$avg_cer,$avg_mer,$avg_wil,$avg_time" >> "$summary_file"
        
        echo "Model: $model"
        echo "  Files processed: $count (valid: $valid_count)"
        echo "  Average WER: $avg_wer"
        echo "  Average CER: $avg_cer"
        echo "  Average MER: $avg_mer"
        echo "  Average WIL: $avg_wil"
        echo "  Average inference time: ${avg_time}s"
        echo ""
        
    done <<< "$models"
    
    echo "Model summary saved to: $summary_file"
    echo ""
    
    # Print comparison table if multiple models
    local num_models=$(echo "$models" | wc -l)
    if [[ $num_models -gt 1 ]]; then
        echo "=========================================="
        echo "Model Comparison"
        echo "=========================================="
        column -t -s',' "$summary_file"
        echo ""
    fi
    
    echo "=========================================="
    echo "Aggregation complete!"
    echo "=========================================="
}

# Run
aggregate_results
