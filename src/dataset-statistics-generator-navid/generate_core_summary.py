import argparse
import pandas as pd
from pathlib import Path

def generate_core_summary(input_dir, output_dir):
    in_p = Path(input_dir)
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    
    if not in_p.exists():
        print(f"Error: Could not find '{input_dir}'. Please run the extractor script first.")
        return

    print(f"Reading core statistics from {in_p.absolute()}...")

    try:
        # Load Basic CSVs
        df_types = pd.read_csv(in_p / "stat_conversation_types.csv")
        df_durations = pd.read_csv(in_p / "stat_video_durations.csv")
        df_tokens = pd.read_csv(in_p / "stat_conversation_tokens.csv")

        total_convs = df_types['Count'].sum()
        patient_calls = df_types[df_types['Type'] == 'patient_call']['Count'].values[0] if 'patient_call' in df_types['Type'].values else 0
        qa_sessions = df_types[df_types['Type'] == 'host_doctor_qa']['Count'].values[0] if 'host_doctor_qa' in df_types['Type'].values else 0
        total_hours = df_durations['duration_seconds'].sum() / 3600
        total_tokens = df_tokens['total_tokens'].sum()

        pct_patient = (patient_calls / total_convs) * 100 if total_convs else 0
        pct_qa = (qa_sessions / total_convs) * 100 if total_convs else 0

        # Load Advanced CSVs
        f_spec = in_p / "stat_specialties.csv"
        unique_specs = len(pd.read_csv(f_spec)) if f_spec.exists() else 0

        f_turns = in_p / "stat_patient_call_turns_raw.csv"
        if f_turns.exists():
            df_turns = pd.read_csv(f_turns)
            total_turns = df_turns['turns'].sum()
            avg_turns = df_turns['turns'].mean()
            max_turns = df_turns['turns'].max()
        else:
            total_turns, avg_turns, max_turns = 0, 0, 0

        f_qa_turns = in_p / "stat_qa_turns_raw.csv"
        if f_qa_turns.exists():
            df_qa_turns = pd.read_csv(f_qa_turns)
            qa_total_turns = df_qa_turns['turns'].sum()
            qa_avg_turns = df_qa_turns['turns'].mean()
            qa_max_turns = df_qa_turns['turns'].max()
        else:
            qa_total_turns, qa_avg_turns, qa_max_turns = 0, 0, 0

        f_speaker = in_p / "stat_patient_vs_doctor_tokens.csv"
        if f_speaker.exists():
            df_speaker = pd.read_csv(f_speaker)
            total_doc = df_speaker['doctor_tokens'].sum()
            total_pat = df_speaker['patient_tokens'].sum()
            avg_doc = df_speaker['doctor_tokens'].mean()
            avg_pat = df_speaker['patient_tokens'].mean()
        else:
            total_doc, total_pat, avg_doc, avg_pat = 0, 0, 0, 0

        # Math Calculations
        total_patient_call_tokens = total_doc + total_pat
        pct_doc_tokens = (total_doc / total_patient_call_tokens) * 100 if total_patient_call_tokens else 0
        pct_pat_tokens = (total_pat / total_patient_call_tokens) * 100 if total_patient_call_tokens else 0
        avg_tokens_per_pat_turn = total_patient_call_tokens / total_turns if total_turns else 0

        total_qa_tokens = total_tokens - total_patient_call_tokens
        avg_qa_tokens = total_qa_tokens / qa_sessions if qa_sessions > 0 else 0
        avg_tokens_per_qa_turn = total_qa_tokens / qa_total_turns if qa_total_turns else 0

        # Build Dataframes
        df_overall = pd.DataFrame([
            {"Metric": "Total Conversations", "Count": f"{total_convs:,}"},
            {"Metric": "Dataset Duration (Hours)", "Count": f"{total_hours:.2f}"},
            {"Metric": "Total Tokens (Bangla-BERT)", "Count": f"{total_tokens:,}"},
            {"Metric": "Unique Medical Specialties", "Count": f"{unique_specs:,}"},
            {"Metric": "Patient Calls Proportion (%)", "Count": f"{pct_patient:.1f}%"},
            {"Metric": "Host-Doctor QA Proportion (%)", "Count": f"{pct_qa:.1f}%"}
        ])
        
        df_patient = pd.DataFrame([
            {"Metric": "Total Patient-Doctor Calls", "Count": f"{patient_calls:,}"},
            {"Metric": "Total Tokens", "Count": f"{total_patient_call_tokens:,}"},
            {"Metric": "Total Turns", "Count": f"{total_turns:,}"},
            {"Metric": "Avg Turns per Call", "Count": f"{avg_turns:.1f}"},
            {"Metric": "Max Turns in a Call", "Count": f"{max_turns}"},
            {"Metric": "Avg Tokens per Turn", "Count": f"{avg_tokens_per_pat_turn:.1f}"},
            {"Metric": "Total Doctor Tokens", "Count": f"{total_doc:,} ({pct_doc_tokens:.1f}%)"},
            {"Metric": "Total Patient Tokens", "Count": f"{total_pat:,} ({pct_pat_tokens:.1f}%)"},
            {"Metric": "Avg Doctor Tokens / Call", "Count": f"{avg_doc:.1f}"},
            {"Metric": "Avg Patient Tokens / Call", "Count": f"{avg_pat:.1f}"}
        ])
        
        df_qa = pd.DataFrame([
            {"Metric": "Total Host-Doctor QA Sessions", "Count": f"{qa_sessions:,}"},
            {"Metric": "Total Tokens", "Count": f"{total_qa_tokens:,}"},
            {"Metric": "Total Turns", "Count": f"{qa_total_turns:,}"},
            {"Metric": "Avg Turns per QA Session", "Count": f"{qa_avg_turns:.1f}"},
            {"Metric": "Max Turns in a QA Session", "Count": f"{qa_max_turns}"},
            {"Metric": "Avg Tokens per QA Session", "Count": f"{avg_qa_tokens:.1f}"},
            {"Metric": "Avg Tokens per Turn", "Count": f"{avg_tokens_per_qa_turn:.1f}"}
        ])
        
        # Combine and Export
        output_text = (
            "=== OVERALL DATASET STATISTICS ===\n" + df_overall.to_string(index=False) + "\n\n" +
            "=== PATIENT-DOCTOR CALLS ===\n" + df_patient.to_string(index=False) + "\n\n" +
            "=== HOST-DOCTOR QA ===\n" + df_qa.to_string(index=False) + "\n"
        )
        
        print("\n" + output_text)
        
        with open(out_p / "table_core_summary.txt", "w", encoding="utf-8") as f:
            f.write(output_text)
            
        with open(out_p / "table_core_summary.tex", "w", encoding="utf-8") as f:
            f.write("% Overall Stats\n")
            f.write(df_overall.to_latex(index=False))
            f.write("\n% Patient-Doctor Calls\n")
            f.write(df_patient.to_latex(index=False))
            f.write("\n% Host-Doctor QA\n")
            f.write(df_qa.to_latex(index=False))
            
        print(f"\n✓ Saved categorized tables (.txt and .tex) to {out_p.absolute()}")
        
    except Exception as e:
        print(f"Error reading CSVs: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate summary TXT/TEX from CSVs.")
    parser.add_argument("--input-dir", type=str, required=True, help="Directory with the generated CSVs")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory to save the text/tex tables")
    args = parser.parse_args()
    generate_core_summary(args.input_dir, args.output_dir)