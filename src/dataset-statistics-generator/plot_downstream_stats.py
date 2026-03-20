import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set paper-friendly plotting style
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

def clean_label(label):
    """Makes ALL_CAPS_LABELS look nice and readable for paper plots."""
    return str(label).replace("_", " ").title()

def create_advanced_plots(input_dir="downstream_results", output_dir="downstream_plots"):
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    
    if not in_path.exists():
        print(f"Error: Directory '{input_dir}' not found. Run the summary script first!")
        return

    print(f"Reading downstream CSVs from {in_path.absolute()}")
    print(f"Building hierarchical plot directories in {out_path.absolute()}...\n")

    overall_dir = out_path / "overall"
    overall_dir.mkdir(parents=True, exist_ok=True)
    
    task_stats = []
    all_labels_data = [] # For macro class plot
    all_items_data = []  # NEW: For macro term distribution plot

    for label_csv in in_path.glob("stat_*_label_dist.csv"):
        task_name = label_csv.name.replace("stat_", "").replace("_label_dist.csv", "")
        
        task_dir = out_path / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Generating plots for: [{task_name}] ...")
        
        df_labels = pd.read_csv(label_csv)
        df_labels['Clean_Label'] = df_labels['Label'].apply(clean_label)
        total_labels = df_labels['Count'].sum()
        
        # Determine the macro task name (combining the Advice tasks)
        macro_task_name = "Advice" if "advice" in task_name else task_name.replace('-', ' ').title()
        
        if task_name != "advice-generation": 
            for _, row in df_labels.iterrows():
                all_labels_data.append({
                    "Task": macro_task_name,
                    "Class": row['Clean_Label'],
                    "Count": row['Count']
                })

        # --- 1. Task-Specific Label Plot ---
        if task_name in ['advice-safety', 'advice-generation']:
            plt.figure(figsize=(6, 6))
            colors = ["#2ecc71", "#e74c3c"] if "SAFE" in df_labels['Label'].values else sns.color_palette("pastel")
            plt.pie(df_labels['Count'], labels=df_labels['Clean_Label'], autopct='%1.1f%%', 
                    startangle=90, colors=colors, wedgeprops=dict(width=0.4, edgecolor='w'))
            plt.title(f"{task_name.replace('-', ' ').title()} - Label Distribution", weight="bold", pad=20)
            plt.tight_layout()
            plt.savefig(task_dir / f"fig1_{task_name}_donut.png", dpi=300)
            plt.close()
        else:
            plt.figure(figsize=(10, 6))
            palette = "viridis" if task_name == "medical-ner" else "flare"
            ax = sns.barplot(x="Count", y="Clean_Label", hue="Clean_Label", legend=False, 
                             data=df_labels, palette=palette, edgecolor=".2")
            
            for p in ax.patches:
                width = p.get_width()
                if width > 0:
                    ax.annotate(f'{int(width):,}', (width, p.get_y() + p.get_height() / 2.), 
                                ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontsize=10)
            
            plt.title(f"{task_name.replace('-', ' ').title()} - Class Distribution", weight="bold", pad=15)
            plt.xlabel("Total Count")
            plt.ylabel("")
            sns.despine()
            plt.tight_layout()
            plt.savefig(task_dir / f"fig1_{task_name}_bar.png", dpi=300)
            plt.close()

        # --- 2. Task-Specific Items Dist Plot ---
        items_csv = in_path / f"stat_{task_name}_items_dist.csv"
        total_samples = 0
        
        if items_csv.exists():
            df_items = pd.read_csv(items_csv)
            total_samples = len(df_items)
            
            # NEW: Collect data for the macro overall term distribution plot
            if task_name != "advice-generation":
                for item_val in df_items['items_per_sample']:
                    all_items_data.append({
                        "Task": macro_task_name,
                        "Terms per Profile": item_val
                    })
            
            if df_items['items_per_sample'].nunique() > 1:
                plt.figure(figsize=(8, 5))
                if task_name == "medical-ner":
                    sns.histplot(df_items["items_per_sample"], bins=30, kde=True, color="#8e44ad", edgecolor=".2")
                    plt.xlabel("Number of Entities Extracted")
                else:
                    item_counts = df_items['items_per_sample'].value_counts().reset_index()
                    item_counts.columns = ['Items', 'Freq']
                    item_counts = item_counts.sort_values('Items')
                    ax = sns.barplot(x="Items", y="Freq", hue="Items", legend=False, data=item_counts, palette="mako", edgecolor=".2")
                    for p in ax.patches:
                        height = p.get_height()
                        if height > 0:
                            ax.annotate(f'{int(height)}', (p.get_x() + p.get_width() / 2., height), 
                                        ha='center', va='center', xytext=(0, 5), textcoords='offset points', fontsize=9)
                    plt.xlabel("Number of Recommendations")
                
                plt.title(f"Items per Profile ({task_name.replace('-', ' ').title()})", weight="bold", pad=15)
                plt.ylabel("Frequency (Profiles)")
                sns.despine()
                plt.tight_layout()
                plt.savefig(task_dir / f"fig2_{task_name}_items_dist.png", dpi=300)
                plt.close()

                plt.figure(figsize=(8, 3))
                sns.boxplot(x=df_items["items_per_sample"], color="#3498db", fliersize=3)
                plt.title(f"Spread and Outliers ({task_name.replace('-', ' ').title()})", weight="bold", pad=15)
                plt.xlabel("Items Count")
                sns.despine()
                plt.tight_layout()
                plt.savefig(task_dir / f"fig3_{task_name}_items_boxplot.png", dpi=300)
                plt.close()

        if task_name != "advice-generation":
            task_stats.append({
                "Task": macro_task_name,
                "Total Patient Profiles": total_samples,
                "Total Granular Items": total_labels
            })

    # --- 3. Accumulated Overall Plots ---
    print("\nGenerating accumulated overall plots in [overall] folder...")
    
    # Plot A: Total Samples
    if task_stats:
        df_overall = pd.DataFrame(task_stats).sort_values(by="Total Patient Profiles", ascending=False)
        plt.figure(figsize=(9, 4))
        ax = sns.barplot(x="Total Patient Profiles", y="Task", hue="Task", legend=False, 
                         data=df_overall, palette="crest", edgecolor=".2")
        for p in ax.patches:
            width = p.get_width()
            if width > 0:
                ax.annotate(f'{int(width):,}', (width, p.get_y() + p.get_height() / 2.), 
                            ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontsize=10, weight="bold")
        plt.title("Total Patient Profiles per Task", weight="bold", pad=15)
        plt.xlabel("Number of Samples")
        plt.ylabel("")
        sns.despine()
        plt.tight_layout()
        plt.savefig(overall_dir / "fig1_overall_samples_comparison.png", dpi=300)
        plt.close()

        # Plot B: Total Items
        df_overall = df_overall.sort_values(by="Total Granular Items", ascending=False)
        plt.figure(figsize=(9, 4))
        ax = sns.barplot(x="Total Granular Items", y="Task", hue="Task", legend=False, 
                         data=df_overall, palette="rocket", edgecolor=".2")
        for p in ax.patches:
            width = p.get_width()
            if width > 0:
                ax.annotate(f'{int(width):,}', (width, p.get_y() + p.get_height() / 2.), 
                            ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontsize=10, weight="bold")
        plt.title("Total Granular Elements (Entities, Labels, Recs)", weight="bold", pad=15)
        plt.xlabel("Total Count")
        plt.ylabel("")
        sns.despine()
        plt.tight_layout()
        plt.savefig(overall_dir / "fig2_overall_items_comparison.png", dpi=300)
        plt.close()

    # Plot C: The Massive Overall Class Distribution
    if all_labels_data:
        df_all_classes = pd.DataFrame(all_labels_data).sort_values(by="Count", ascending=False)
        plt.figure(figsize=(12, 10)) 
        ax = sns.barplot(x="Count", y="Class", hue="Task", dodge=False,
                         data=df_all_classes, palette="deep", edgecolor=".2")
        for p in ax.patches:
            width = p.get_width()
            if width > 0:
                ax.annotate(f'{int(width):,}', (width, p.get_y() + p.get_height() / 2.), 
                            ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontsize=10)
        plt.title("Macro View: All Labels Across the TelemedBN Benchmark", weight="bold", pad=20, fontsize=14)
        plt.xlabel("Total Frequency in Dataset", fontsize=12)
        plt.ylabel("")
        plt.legend(title="Associated Task", loc="lower right", frameon=True)
        sns.despine()
        plt.tight_layout()
        plt.savefig(overall_dir / "fig3_overall_class_distribution.png", dpi=300)
        plt.close()

    # --- NEW: Plot D & E: Overall Term Distributions ---
    if all_items_data:
        df_all_terms = pd.DataFrame(all_items_data)
        
        # We will filter out Triage from the density plot because it's a flat line at "1"
        df_terms_filtered = df_all_terms[df_all_terms["Task"] != "Triage"]
        
        # Plot D: Density / KDE Plot
        plt.figure(figsize=(10, 6))
        sns.kdeplot(data=df_terms_filtered, x="Terms per Profile", hue="Task", fill=True, 
                    common_norm=False, palette="Set2", alpha=0.5, linewidth=2)
        plt.title("Macro View: Density of Terms per Patient Profile", weight="bold", pad=20, fontsize=14)
        plt.xlabel("Number of Terms/Items Extracted", fontsize=12)
        plt.ylabel("Density", fontsize=12)
        sns.despine()
        plt.tight_layout()
        plt.savefig(overall_dir / "fig4_overall_term_distribution_density.png", dpi=300)
        plt.close()
        
        # Plot E: Grouped Boxplot (Academic standard)
        plt.figure(figsize=(10, 5))
        sns.boxplot(x="Terms per Profile", y="Task", hue="Task", legend=False, 
                    data=df_all_terms, palette="Set2", showmeans=True, 
                    meanprops={"marker":"o","markerfacecolor":"white", "markeredgecolor":"black", "markersize": "6"})
        plt.title("Macro View: Spread of Terms per Patient Profile", weight="bold", pad=20, fontsize=14)
        plt.xlabel("Number of Terms/Items Extracted", fontsize=12)
        plt.ylabel("")
        sns.despine()
        plt.tight_layout()
        plt.savefig(overall_dir / "fig5_overall_term_distribution_boxplot.png", dpi=300)
        plt.close()
        print("✓ Created fig4 and fig5 (Overall Term Distributions)")

    print(f"\n✓ Perfection! All plots are cleanly organized inside the '{out_path.absolute()}' folder.")

if __name__ == "__main__":
    create_advanced_plots()