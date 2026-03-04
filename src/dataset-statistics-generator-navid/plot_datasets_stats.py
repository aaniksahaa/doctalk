import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set paper-friendly plotting style
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

def create_plots(input_dir="statistics-results", output_dir="paper_plots"):
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    if not in_path.exists():
        print(f"Error: Directory '{input_dir}' not found. Run the generator script first!")
        return

    print(f"Reading CSVs from {in_path.absolute()}")
    print(f"Saving figures to {out_path.absolute()}...\n")

# --- 1. Conversation Types (Pie Chart - Better for 2 types) ---
    csv_types = in_path / "stat_conversation_types.csv"
    if csv_types.exists():
        df = pd.read_csv(csv_types)
        plt.figure(figsize=(6, 6)) # Square aspect ratio for the pie
        colors = sns.color_palette("viridis", len(df))
        plt.pie(df['Count'], labels=df['Type'], autopct='%1.1f%%', 
                startangle=140, colors=colors, explode=[0.05, 0])
        plt.title("Proportion of Conversation Types", weight="bold", pad=20)
        plt.tight_layout()
        plt.savefig(out_path / "fig1_conversation_types_pie.png", dpi=300)
        plt.close()
        print("✓ Created fig1_conversation_types_pie.png (Pie Chart)")

    # --- 2. Patient Call Turns (Narrower Bar Chart) ---
# --- 2. Patient Call Turns (Refined Density & Color) ---
# --- 2. Patient Call Turns (Professional Academic Style) ---
    csv_turns = in_path / "stat_patient_call_turns_freq.csv"
    if csv_turns.exists():
        df = pd.read_csv(csv_turns)
        
        plt.figure(figsize=(7, 5)) 
        
        # Filter for non-zero counts and ensure proper ordering
        actual_turns_data = df[df['Frequency'] > 0].copy()
        actual_turns_data['Turns'] = actual_turns_data['Turns'].astype(int)
        actual_turns_data = actual_turns_data.sort_values('Turns')
        actual_turns_data['Turns'] = actual_turns_data['Turns'].astype(str)
        
        # Use 'rocket_r' for a deep, sophisticated dark-purple/red-to-pink gradient
        # or 'flare' for a more muted, professional look.
        ax = sns.barplot(
            x="Turns", 
            y="Frequency", 
            data=actual_turns_data, 
            palette="rocket_r", # Academic and high-contrast
            edgecolor=".2"      # Adds a subtle dark border to bars
        )
        
        # Add exact numbers on top with a slightly smaller font for a cleaner look
        for p in ax.patches:
            height = p.get_height()
            if height > 0:
                ax.annotate(format(height, '.0f'), 
                            (p.get_x() + p.get_width() / 2., height), 
                            ha='center', va='center', xytext=(0, 8), 
                            textcoords='offset points', 
                            fontsize=9, 
                            weight='semibold', 
                            color='#333333')
        
        plt.title("Conversational Turn Distribution (Patient Calls)", weight="bold", pad=15)
        plt.xlabel("Number of Turns")
        plt.ylabel("Count")
        
        # Despine removes the top and right borders for a modern "clean" look
        sns.despine()
        
        plt.tight_layout()
        plt.savefig(out_path / "fig2_turn_distribution.png", dpi=300)
        plt.close()
        print("✓ Created fig2_turn_distribution.png (Rocket Palette)")
    # --- 3. Video Durations (Histogram) ---
    csv_dur = in_path / "stat_video_durations.csv"
    if csv_dur.exists():
        df = pd.read_csv(csv_dur)
        df["mins"] = df["duration_seconds"] / 60
        plt.figure(figsize=(8, 5))
        sns.histplot(df["mins"], bins=30, kde=True, color="coral")
        plt.title("Show Duration Distribution", weight="bold")
        plt.xlabel("Minutes")
        plt.tight_layout()
        plt.savefig(out_path / "fig3_video_durations.png", dpi=300)
        plt.close()
        print("✓ Created fig3_video_durations.png")

    # --- 4. Token Count Distribution (Histogram) ---
    csv_tokens = in_path / "stat_conversation_tokens.csv"
    if csv_tokens.exists():
        df = pd.read_csv(csv_tokens)
        plt.figure(figsize=(8, 5))
        sns.histplot(df["total_tokens"], bins=50, kde=True, color="purple")
        plt.title("Tokens per Conversation (Bangla-BERT)", weight="bold")
        plt.tight_layout()
        plt.savefig(out_path / "fig4_token_counts.png", dpi=300)
        plt.close()
        print("✓ Created fig4_token_counts.png")

    # --- 5. Patient vs. Doctor Tokens (Box Plot) ---
    csv_vs = in_path / "stat_patient_vs_doctor_tokens.csv"
    if csv_vs.exists():
        df = pd.read_csv(csv_vs)
        df_melted = df.melt(var_name="Speaker", value_name="Tokens")
        df_melted["Speaker"] = df_melted["Speaker"].replace({"patient_tokens": "Patient", "doctor_tokens": "Doctor"})
        plt.figure(figsize=(7, 6))
        sns.boxplot(x="Speaker", y="Tokens", data=df_melted, palette="Set2")
        plt.title("Speaker Token Comparison", weight="bold")
        plt.tight_layout()
        plt.savefig(out_path / "fig5_patient_vs_doctor.png", dpi=300)
        plt.close()
        print("✓ Created fig5_patient_vs_doctor.png")

    # --- 6. Specialty Distribution (Horizontal Bar Chart) ---
    csv_spec = in_path / "stat_specialties.csv"
    if csv_spec.exists():
        df = pd.read_csv(csv_spec)
        plt.figure(figsize=(10, 6))
        sns.barplot(x="Count", y="Specialty", data=df, palette="magma")
        plt.title("Medical Specialty Coverage", weight="bold")
        plt.tight_layout()
        plt.savefig(out_path / "fig6_specialty_coverage.png", dpi=300)
        plt.close()
        print("✓ Created fig6_specialty_coverage.png")

    print("\nProcessing complete! Check the 'paper_plots' folder.")

if __name__ == "__main__":
    create_plots()