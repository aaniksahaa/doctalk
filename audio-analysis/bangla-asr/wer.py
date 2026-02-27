#!/usr/bin/env python3
"""
ASR Evaluation Metrics Calculator

Calculates multiple metrics for speech recognition evaluation:
- WER (Word Error Rate)
- CER (Character Error Rate)
- MER (Match Error Rate)
- WIL (Word Information Lost)

Usage:
  python wer.py --gt-file gt.txt --pred-file pred.txt
  python wer.py --gt-text "ground truth" --pred-text "prediction"
  python wer.py --gt-file gt.txt --pred-file pred.txt --json  # Output as JSON
"""

import argparse
import json
import sys

try:
    import jiwer
except ImportError:
    print("Installing jiwer...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jiwer", "-q"])
    import jiwer


def calculate_metrics(gt_text: str, pred_text: str) -> dict:
    """Calculate all ASR evaluation metrics between ground truth and prediction.
    
    Returns dict with metrics and is_valid flag.
    is_valid=0 when either GT or prediction is empty (metrics undefined).
    """
    # Normalize texts
    gt_text = gt_text.strip()
    pred_text = pred_text.strip()
    
    # Handle edge cases - mark as invalid, don't return fake metrics
    if not gt_text or not pred_text:
        return {
            "wer": None,
            "cer": None,
            "mer": None,
            "wil": None,
            "is_valid": 0
        }
    
    # Calculate word-level metrics
    wer = jiwer.wer(gt_text, pred_text)
    mer = jiwer.mer(gt_text, pred_text)
    wil = jiwer.wil(gt_text, pred_text)
    
    # Calculate character-level error rate
    cer = jiwer.cer(gt_text, pred_text)
    
    return {
        "wer": wer,
        "cer": cer,
        "mer": mer,
        "wil": wil,
        "is_valid": 1
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate ASR Evaluation Metrics")
    parser.add_argument("--gt-file", type=str, help="Path to ground truth file")
    parser.add_argument("--pred-file", type=str, help="Path to prediction file")
    parser.add_argument("--gt-text", type=str, help="Ground truth text (alternative to file)")
    parser.add_argument("--pred-text", type=str, help="Prediction text (alternative to file)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--metric", type=str, choices=["wer", "cer", "mer", "wil", "all"],
                        default="all", help="Which metric to output (default: all)")
    args = parser.parse_args()
    
    # Get ground truth text
    if args.gt_file:
        with open(args.gt_file, 'r', encoding='utf-8') as f:
            gt_text = f.read()
    elif args.gt_text is not None:
        gt_text = args.gt_text
    else:
        parser.error("Must specify --gt-file or --gt-text")
    
    # Get prediction text
    if args.pred_file:
        with open(args.pred_file, 'r', encoding='utf-8') as f:
            pred_text = f.read()
    elif args.pred_text is not None:
        pred_text = args.pred_text
    else:
        parser.error("Must specify --pred-file or --pred-text")
    
    metrics = calculate_metrics(gt_text, pred_text)
    
    # Output
    if args.json:
        print(json.dumps(metrics))
    elif args.metric == "all":
        # CSV-friendly output: wer,cer,mer,wil,is_valid
        if metrics["is_valid"] == 1:
            print(f"{metrics['wer']:.6f},{metrics['cer']:.6f},{metrics['mer']:.6f},{metrics['wil']:.6f},{metrics['is_valid']}")
        else:
            print(f"N/A,N/A,N/A,N/A,{metrics['is_valid']}")
    else:
        if metrics["is_valid"] == 1:
            print(f"{metrics[args.metric]:.6f}")
        else:
            print("N/A")


if __name__ == "__main__":
    main()
