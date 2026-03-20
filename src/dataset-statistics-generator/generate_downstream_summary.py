import argparse
import pandas as pd
import json
from pathlib import Path
from collections import Counter

def generate_downstream_summary(downstream_dir, output_dir):
    ds_p = Path(downstream_dir)
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    
    if not ds_p.exists():
        print(f"Error: Could not find '{downstream_dir}'.")
        return

    print(f"Scanning granular downstream tasks in {ds_p.absolute()}...")
    print(f"All outputs will be neatly saved to: {out_p.absolute()}\n")
    
    summary_data = []
    class_distributions = {}

    for task_dir in ds_p.iterdir():
        if not task_dir.is_dir():
            continue
            
        task_name = task_dir.name
        
        # 1. Read summary.json
        summary_file = task_dir / "summary.json"
        train_c, val_c, test_c, source_vids = 0, 0, 0, 0
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    ds_meta = json.load(f)
                    train_c = ds_meta.get('train_count', 0)
                    val_c = ds_meta.get('val_count', 0)
                    test_c = ds_meta.get('test_count', 0)
                    source_vids = ds_meta.get('source_videos', 0)
            except Exception as e:
                print(f"Warning: Could not parse {summary_file}: {e}")

        # 2. Extract Data from 'all' folder
        all_dir = task_dir / "all"
        total_profiles = 0
        total_granular_items = 0
        
        task_labels = Counter()
        items_per_sample = [] 
        
        if all_dir.exists():
            for sample_dir in all_dir.iterdir():
                if not sample_dir.is_dir():
                    continue
                
                gt_file = sample_dir / "ground_truth.json"
                if gt_file.exists():
                    try:
                        with open(gt_file, 'r', encoding='utf-8') as f:
                            gt_data = json.load(f)
                            total_profiles += 1
                            
                            labels_in_sample = []
                            items_c = 0
                            
                            # --- SMART PARSING BASED ON TASK ---
                            if "ner" in task_name and "entities" in gt_data:
                                items_c = len(gt_data["entities"])
                                labels_in_sample = [ent.get("label") for ent in gt_data["entities"] if "label" in ent]
                                
                            # --- FIXED: Now catches BOTH advice-safety and advice-generation ---
                            elif "advice" in task_name and "recommendations" in gt_data:
                                items_c = len(gt_data["recommendations"])
                                labels_in_sample = [rec.get("label") for rec in gt_data["recommendations"] if "label" in rec]
                                
                            elif "triage" in task_name:
                                triage_type = gt_data.get("type")
                                if triage_type:
                                    labels_in_sample = [triage_type]
                                    items_c = 1
                            
                            task_labels.update(labels_in_sample)
                            items_per_sample.append(items_c)
                            total_granular_items += items_c
                            
                    except Exception:
                        pass
        
        # Save the items-per-sample distribution to the clean folder
        if items_per_sample:
            dist_df = pd.DataFrame({"items_per_sample": items_per_sample})
            dist_df.to_csv(out_p / f"stat_{task_name}_items_dist.csv", index=False)
            
        class_distributions[task_name] = task_labels

        display_name = task_name.replace('-', ' ').title().replace('Ner', 'NER')
        summary_data.append({
            "Downstream Task": display_name,
            "Source Videos": f"{source_vids:,}",
            "Samples": f"{total_profiles:,}",
            "Total Labels/Items": f"{total_granular_items:,}",
            "Train/Val/Test Split": f"{train_c}/{val_c}/{test_c}"
        })

    # 3. Generate Final Output
    if summary_data:
        df_final = pd.DataFrame(summary_data).sort_values(by="Samples", ascending=False)
        
        output_text = "=== DOWNSTREAM BENCHMARK DATASETS ===\n"
        output_text += df_final.to_string(index=False) + "\n\n"
        
        output_text += "=== CLASS DISTRIBUTIONS (For Appendix) ===\n"
        for task, labels in class_distributions.items():
            if labels:
                output_text += f"\n-- {task.replace('-', ' ').title()} --\n"
                for label, count in labels.most_common():
                    output_text += f"   {label}: {count:,}\n"
                
                # Save label distributions to CSV in the clean folder
                pd.DataFrame(list(labels.items()), columns=["Label", "Count"]).sort_values(by="Count", ascending=False).to_csv(out_p / f"stat_{task}_label_dist.csv", index=False)
        
        print(output_text)
        
        # Save tables directly to the clean folder
        with open(out_p / "table_downstream_summary.txt", "w", encoding="utf-8") as f:
            f.write(output_text)
            
        with open(out_p / "table_downstream_summary.tex", "w", encoding="utf-8") as f:
            f.write(df_final.to_latex(index=False))
            
        print(f"\n✓ Saved all tables and distribution CSVs neatly into the '{out_p.name}' folder!")
    else:
        print("No downstream tasks found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate granular summary table for downstream NLP tasks.")
    parser.add_argument("--downstream-dir", type=str, required=True, help="Directory containing downstream tasks")
    parser.add_argument("--output-dir", type=str, default="downstream_results", help="Directory to save the summary tables")
    args = parser.parse_args()
    
    generate_downstream_summary(args.downstream_dir, args.output_dir)