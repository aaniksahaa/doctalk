import argparse
import json
import os
from pathlib import Path
import pandas as pd
from collections import Counter
from transformers import AutoTokenizer

# ==========================================
# Initialize the Tokenizer (Global)
# ==========================================
print("Loading Bangla-BERT tokenizer for strict token counting...")
try:
    tokenizer = AutoTokenizer.from_pretrained("sagorsarker/bangla-bert-base")
except Exception as e:
    print(f"Error loading tokenizer: {e}")
    print("Please ensure you have run: pip install transformers")
    exit(1)

def get_token_count(text):
    """
    Returns strict token counts using the pre-trained Bengali tokenizer,
    ignoring special classification tokens like [CLS] and [SEP].
    """
    if not text:
        return 0
    tokens = tokenizer.encode(str(text), add_special_tokens=False)
    return len(tokens)

def process_dataset(data_dir, output_dir):
    data_path = Path(data_dir)
    out_path = Path(output_dir)
    
    # Create the output directory if it doesn't exist
    out_path.mkdir(parents=True, exist_ok=True)
    
    # ==========================================
    # 1. Initialize Statistic Trackers
    # ==========================================
    total_parsed_videos = 0
    
    conv_type_counter = Counter()
    patient_call_turns = []
    
    video_durations = []
    specialty_counter = Counter()
    
    total_tokens_per_conv = []
    patient_vs_doctor_tokens = [] # List of dicts
    
    print(f"Scanning dataset directory: {data_path.absolute()}")
    print(f"Output CSVs will be saved to: {out_path.absolute()}")

    # ==========================================
    # 2. Iterate Through the Dataset
    # ==========================================
    for video_folder in data_path.iterdir():
        if not video_folder.is_dir():
            continue
            
        video_id = video_folder.name
        
        # --- Paths based on your dataset structure ---
        json_path = video_folder / "transcribed" / "yt-auto" / "parsed" / "gemini-3-flash-preview" / f"{video_id}_conversation.json"
        yt_metadata_path = video_folder / f"{video_id}_yt-dlp-metadata.json"
        derived_metadata_path = video_folder / f"{video_id}_derived-metadata.json"
        
        # --- Extract Video Metadata (Audio Duration) ---
        if yt_metadata_path.exists():
            try:
                with open(yt_metadata_path, 'r', encoding='utf-8') as f:
                    yt_meta = json.load(f)
                    if 'duration' in yt_meta:
                        video_durations.append(yt_meta['duration'])
            except Exception:
                pass # Silently skip malformed metadata

        # --- Extract Derived Metadata (Specialty Coverage / Tags) ---
        if derived_metadata_path.exists():
            try:
                with open(derived_metadata_path, 'r', encoding='utf-8') as f:
                    derived_meta = json.load(f)
                    # Look for 'tags' list as discovered in the JSON structure
                    if 'tags' in derived_meta and isinstance(derived_meta['tags'], list):
                        for tag in derived_meta['tags']:
                            specialty_counter[tag.capitalize()] += 1
            except Exception:
                pass
        
        # --- Extract Conversation Statistics ---
        if not json_path.exists():
            continue
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            
            total_parsed_videos += 1
                
            for conv in conversations:
                conv_type = conv.get("type", "unknown")
                conv_type_counter[conv_type] += 1
                
                turns = conv.get("turns", [])
                
                # Distribution of number of turns in patient calls
                if conv_type == "patient_call":
                    patient_call_turns.append(len(turns))
                
                # Token counting variables
                conv_total_tokens = 0
                patient_tokens = 0
                doctor_tokens = 0
                
                # Process each turn for strict token counts
                for turn in turns:
                    speaker = turn.get("speaker", "").lower()
                    text = turn.get("text", "")
                    tokens = get_token_count(text)
                    
                    conv_total_tokens += tokens
                    
                    # Track patient vs doctor tokens specifically for patient calls
                    if conv_type == "patient_call":
                        if "patient" in speaker or "caller" in speaker:
                            patient_tokens += tokens
                        elif "doctor" in speaker:
                            doctor_tokens += tokens
                
                total_tokens_per_conv.append(conv_total_tokens)
                
                if conv_type == "patient_call":
                    patient_vs_doctor_tokens.append({
                        'patient_tokens': patient_tokens,
                        'doctor_tokens': doctor_tokens
                    })
                    
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON for {video_id}")
        except Exception as e:
            print(f"Warning: Error processing {video_id}: {e}")

    # ==========================================
    # 3. Export Statistics to CSVs
    # ==========================================
    print(f"\n--- Processed {total_parsed_videos} parsed videos successfully ---")
    
    pd.DataFrame(list(conv_type_counter.items()), columns=["Type", "Count"]).to_csv(out_path / "stat_conversation_types.csv", index=False)
    pd.DataFrame({'turns': patient_call_turns}).to_csv(out_path / "stat_patient_call_turns_raw.csv", index=False)
    
    turn_freq = Counter(patient_call_turns)
    pd.DataFrame(list(turn_freq.items()), columns=["Turns", "Frequency"]).sort_values("Turns").to_csv(out_path / "stat_patient_call_turns_freq.csv", index=False)
    
    pd.DataFrame({'duration_seconds': video_durations}).to_csv(out_path / "stat_video_durations.csv", index=False)
    pd.DataFrame({'total_tokens': total_tokens_per_conv}).to_csv(out_path / "stat_conversation_tokens.csv", index=False)
    
    if patient_vs_doctor_tokens:
        pd.DataFrame(patient_vs_doctor_tokens).to_csv(out_path / "stat_patient_vs_doctor_tokens.csv", index=False)
    
    if specialty_counter:
        pd.DataFrame(list(specialty_counter.items()), columns=["Specialty", "Count"]).sort_values("Count", ascending=False).to_csv(out_path / "stat_specialties.csv", index=False)
        print(f"✓ Successfully generated stat_specialties.csv!")
    else:
        print("⚠ No tags/specialties found in derived metadata.")
    
    print(f"All CSVs generated successfully in the '{output_dir}' directory!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate strict dataset statistics for the TelemedBN paper.")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to the dataset directory")
    parser.add_argument("--output-dir", type=str, default="statistics-results", help="Directory to save the generated CSV files")
    
    args = parser.parse_args()
    process_dataset(args.data_dir, args.output_dir)