# 💊 DocTalkBN: A Multimodal Conversational Medical Dataset in Bengali

**DocTalkBN** is an expert-grounded, multimodal dataset of real-world doctor-patient interactions in Bengali, sourced from health programs on Bengali television and YouTube channels. It captures authentic clinical conversations across 25+ medical specialties and provides curated benchmarks for four downstream medical NLP tasks.

> **Language:** Bengali (Bangla) &nbsp;|&nbsp; **Domain:** Healthcare / Clinical NLP &nbsp;|&nbsp; **Platform:** Linux

---

## Overview

Access to reliable medical information remains a challenge for Bengali-speaking populations. Existing medical NLP resources are predominantly English-centric, text-only, or lack grounding by domain experts. DocTalkBN addresses this gap by:

- Collecting real doctor-patient conversations from **Bengali TV channels** and **health programs**
- Processing audio through automatic speech recognition, speaker diarization, and LLM-based transcription parsing
- Curating **three downstream task datasets** from the resulting conversations
- Benchmarking **LLMs, BERT-based models, and embedding-based classifiers** on each task

The dataset captures code-mixed Bengali, regional medical nuances, and multi-turn conversational dynamics that are absent from synthetic or translated corpora.

---

## Downstream Tasks

| Task | Description | Input | Output |
|------|-------------|-------|--------|
| **Medical NER** | Identify medical entities in clinical text | Text segment | BIO-tagged entities (disease, medicine, symptom, etc.) |
| **Medical Triage** | Classify urgency of a patient case | Patient profile (conversation history) | Home care / Doctor visit / Emergency |
| **Advice Safety** | Detect potentially harmful medical recommendations | (Patient profile, recommendation) pair | Safe / Unsafe |

---

## Repository Structure

```
doctalk/
├── src/                            # Main source code
│   ├── constants.py                # Medical specialties, program names
│   ├── search_yt_videos_*.py       # YouTube video search & scraping
│   ├── filter_healthcare_data.py   # LLM-based healthcare video filtering
│   ├── fetch_metadata_and_process_transcriptions.py
│   ├── extract_tag_and_derived_metadata.py
│   ├── parse_transcriptions.py     # SRT/VTT → structured conversations
│   ├── generate_medical_ner_dataset.py
│   ├── generate_triage_dataset.py
│   ├── generate_advice_safety_dataset.py
│   ├── organize_downstream_datasets.py
│   ├── infer_downstream.py         # Unified inference script (all tasks)
│   ├── run_bulk_inference.py       # Bulk multi-model inference
│   ├── prompts/                    # Prompt templates (28 task-specific dirs)
│   ├── downstream-artifacts/       # Fine-tuning & inference code
│   │   ├── medical-ner/            # BanglaBERT / mmBERT NER fine-tuning
│   │   ├── triage/                 # Triage classification fine-tuning
│   │   └── advice-safety/          # Advice safety fine-tuning
│   ├── evaluation-pipeline/        # Evaluation metrics & analysis
│   ├── dataset-statistics-generator/
│   └── saved-data/                 # Generated datasets & checkpoints
├── audio-analysis/
│   ├── bangla-asr/                 # ASR experiments (Whisper, Wav2Vec2, etc.)
│   └── diarization/                # Speaker diarization (NeMo, PyAnnote, 3D-Speaker)
├── llm-inference/
│   ├── api/                        # Gemini API audio inference
│   └── local/                      # Local model inference
├── examples/                       # Sample conversations & dataset entries
├── workflow/                       # Step-by-step pipeline documentation
└── data/                           # Downloaded video metadata & IDs
```

---

## Prerequisites

```bash
pip install -U yt-dlp
pip install -U torch transformers datasets evaluate seqeval accelerate
pip install -U sentence-transformers
pip install -U scikit-learn
pip install -U git+https://github.com/csebuetnlp/normalizer.git  # BanglaBERT only
```

---

## Pipeline

### Step 1 — Video Search & Metadata Collection

```bash
cd src/

# Search a single program
python search_yt_videos_single_query.py \
  --query "স্বাস্থ্য জিজ্ঞাসা - Bangladesh Television" \
  --channel UClzwimpLoZu9us9MwalLbtA \
  --data-dir saved-data \
  --file results-btv.json

# Bulk search across all configured programs
python search_yt_videos_bulk.py \
  --queries-json search_queries.json \
  --data-dir saved-data
```

### Step 2 — Healthcare Video Filtering

```bash
python filter_healthcare_data.py \
  --folder saved-data \
  --file results.json \
  --model qwen3:30b-instruct
```

### Step 3 — Metadata Extraction & Transcription Fetching

```bash
python fetch_metadata_and_process_transcriptions.py \
  --folder saved-data \
  --file filtered-results.json \
  --lang bn \
  --force-rewrite

python extract_tag_and_derived_metadata.py \
  --folder saved-data \
  --file filtered-results.json \
  --model qwen3:30b-instruct
```

### Step 4 — Transcription Parsing (SRT → Structured Conversations)

```bash
python parse_transcriptions.py \
  --folder saved-data \
  --file filtered-results.json \
  --model gemini-3-flash-preview

# Test on a single video
python parse_transcriptions.py \
  --folder saved-data \
  --file filtered-results.json \
  --model gemini-3-flash-preview \
  --test-video-id RkWh5fOOx9s
```

### Step 5 — Downstream Dataset Generation

```bash
# Medical NER
python generate_medical_ner_dataset.py --model gemini-3-flash-preview --batch-size 5

# Triage Classification
python generate_triage_dataset.py

# Advice Safety
python generate_advice_safety_dataset.py
```

### Step 6 — Organize into Train / Val / Test Splits

```bash
# All tasks with default 80/10/10 split
python organize_downstream_datasets.py

# Custom split
python organize_downstream_datasets.py --train-pct 80 --val-pct 10

# Single task
python organize_downstream_datasets.py --tasks medical-ner

# Multiple tasks (semicolon-separated)
python organize_downstream_datasets.py --tasks "medical-ner;advice-safety;triage"
```

---

## Inference

### LLM Inference (Zero-Shot / Few-Shot / Chain-of-Thought)

```bash
cd src/

# Zero-shot inference
python infer_downstream.py \
  --tasks triage \
  --split test \
  --model gemini-2.5-flash \
  --setting zero-shot \
  --batch-size 3

# Chain-of-Thought (CoT) inference
python infer_downstream.py \
  --tasks triage \
  --split test \
  --model gemini-2.5-flash \
  --setting cot \
  --batch-size 3

# Multiple tasks in one run (semicolon-separated)
python infer_downstream.py \
  --tasks "medical-ner;advice-safety;triage" \
  --split test \
  --model gemini-2.5-flash \
  --setting zero-shot \
  --batch-size 3

# OpenAI GPT-4O
python infer_downstream.py \
  --tasks advice-safety \
  --split test \
  --model gpt-4o \
  --provider openai \
  --setting zero-shot \
  --batch-size 3

# OpenRouter (Qwen, LLaMA, etc.)
python infer_downstream.py \
  --tasks medical-ner \
  --split test \
  --model qwen/qwen3-32b \
  --provider openrouter \
  --setting zero-shot \
  --batch-size 3
```

### Bulk Inference (Multiple Models)

```bash
python run_bulk_inference.py --tasks medical-ner --split test --batch-size 3
python run_bulk_inference.py --tasks "medical-ner;advice-safety;triage" --split test --batch-size 3
```

#### `infer_downstream.py` — Key Parameters

| Flag | Description | Default |
|------|-------------|---------|
| `--tasks` | Task(s) to run, semicolon-separated (`medical-ner`, `triage`, `advice-safety`) | — |
| `--split` | Dataset split (`train`, `val`, `test`) | `test` |
| `--model` | Model name or path | — |
| `--provider` | API provider (`openai`, `openrouter`, `gemini`) | auto-detected |
| `--setting` | Inference mode (`zero-shot`, `few-shot`, `cot`, `finetuned`) | `zero-shot` |
| `--batch-size` | Number of samples per API call | `3` |
| `-s` | Standard model name for unified output dirs across providers | — |
| `--first-n` | Only process first N samples (for testing) | all |
| `--force-rewrite` | Overwrite existing inference outputs | off |

---

## Fine-Tuning

### Medical NER — BanglaBERT / mmBERT

```bash
cd src/downstream-artifacts/medical-ner/ner-finetuning

# BanglaBERT (~110M parameters)
python train_ner.py --model banglabert

# BanglaBERT — small dataset config (~38 samples)
python train_ner.py --model banglabert \
  --epochs 30 --train-batch 4 --grad-accum 2 \
  --warmup-steps 20 --early-stopping 7 --logging-steps 10

# mmBERT (~307M parameters)
python train_ner.py --model mmbert

# mmBERT — small dataset config with FP16
python train_ner.py --model mmbert \
  --epochs 30 --train-batch 2 --grad-accum 4 \
  --warmup-steps 20 --early-stopping 7 --fp16

# Standalone NER inference
python infer_ner.py --model banglabert --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"
python infer_ner.py --model mmbert    --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"
```

### Triage Classification — BERT-based & Embedding-based

```bash
cd src/downstream-artifacts/triage/triage-finetuning

# BERT sequence classifiers
python train_triage.py --model banglabert
python train_triage.py --model mmbert --fp16

# Embedding + MLP classifiers (frozen encoder)
python train_triage_embed.py --model multilingual-minilm
python train_triage_embed.py --model multilingual-e5-small

# Standalone inference
python infer_triage.py --model banglabert --text "রোগীর হিট স্ট্রোক, জ্বর এবং সর্দি আছে।"
python infer_triage.py --model multilingual-minilm --json-input input.json --json-output preds.json
```

### Advice Safety — Embedding-based Pair Classifier

```bash
cd src/downstream-artifacts/advice-safety/advice-safety-finetuning

python train_advice_safety_embed.py --model multilingual-minilm
python train_advice_safety_embed.py --model multilingual-e5-small

# Standalone inference
python infer_advice_safety.py --model multilingual-minilm \
  --json-input input.json --json-output preds.json
```

### Fine-Tuned Model Evaluation via Unified Pipeline

```bash
cd src/

# Medical NER
python infer_downstream.py --tasks medical-ner --split test --model banglabert --setting finetuned
python infer_downstream.py --tasks medical-ner --split test --model mmbert      --setting finetuned

# Triage
python infer_downstream.py --tasks triage --split test --model banglabert            --setting finetuned
python infer_downstream.py --tasks triage --split test --model multilingual-minilm   --setting finetuned
python infer_downstream.py --tasks triage --split test --model multilingual-e5-small --setting finetuned

# Advice Safety
python infer_downstream.py --tasks advice-safety --split test --model multilingual-minilm   --setting finetuned
python infer_downstream.py --tasks advice-safety --split test --model multilingual-e5-small --setting finetuned
```

---

## Models & Baselines

### Closed-Source LLMs

| Model | Provider |
|-------|----------|
| GPT-4O | OpenAI |
| Gemini 2.5 Flash | Google |
| Gemini 3 Flash Preview | Google |

### Open-Source LLMs (via OpenRouter / Local)

| Model | Parameters |
|-------|-----------|
| Qwen3-32B | 32B |
| Qwen3-30B-Instruct | 30B |

### BERT-type & Embedding Models

| Model | HuggingFace ID | Size | Tasks |
|-------|----------------|------|-------|
| BanglaBERT | `csebuetnlp/banglabert` | ~110M | NER, Triage |
| mmBERT | `jhu-clsp/mmBERT-base` | ~307M | NER, Triage |
| multilingual-MiniLM | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Compact | Triage, Advice Safety |
| multilingual-E5-small | `intfloat/multilingual-e5-small` | Compact | Triage, Advice Safety |

---

## Data Sources

DocTalkBN aggregates health program content from **14 major Bengali TV channels**:

| Channel | Program(s) |
|---------|-----------|
| BTV | স্বাস্থ্য জিজ্ঞাসা |
| ATN Bangla | Sustho Thakun |
| NTV | Shastho Protidin |
| RTV | Sustho Thakun |
| MyTV | My Health |
| GTV | Doctor's Chamber |
| DBC News | স্বাস্থ্যকথা |
| Channel 24 | সুরক্ষায় প্রতিদিন, Sustho Merudondo |
| Jamuna TV | Doctors On Call |
| Maasranga TV | Doctor's Chamber |
| Deepto | Sustha Jibon |
| Banglavision | Shastha Katha |
| Boishakhi TV | Boishakhi Health |
| News24 | Health Tips |

Medical specialties covered include cardiology, neurology, gastroenterology, pediatrics, psychiatry, orthopedics, dermatology, endocrinology, and 17 others.

---

## Dataset Format

Each processed video is stored as a structured JSON file:

```json
{
  "id": "video_id",
  "yt-source": "https://www.youtube.com/watch?v=...",
  "date": "YYYY-MM-DD",
  "topic_of_disease": ["cardiology", "neurology"],
  "person_data": { "doctor_info": "..." },
  "messages": [
    {
      "id": "msg_1",
      "reply_to_id": null,
      "sender": "interviewer",
      "text": "...",
      "start": 12.5,
      "end": 24.3
    },
    {
      "id": "msg_2",
      "reply_to_id": "msg_1",
      "sender": "doctor",
      "text": "...",
      "start": 25.0,
      "end": 45.7
    }
  ]
}
```

---

## Evaluation

Evaluation scripts are in [src/evaluation-pipeline/](src/evaluation-pipeline/).

```bash
cd src/evaluation-pipeline/

# Triage classification metrics (per-class + macro/micro F1)
python triage-results.py

# NER evaluation (BIO format, seqeval-compatible)
python ner-eval.py

# Advice safety metrics
python main.py
```

See [src/evaluation-pipeline/EVALUATION_METRICS.md](src/evaluation-pipeline/EVALUATION_METRICS.md) for detailed metric definitions.

---

## Future Works

We are actively working on the **Advice Generation** task, where a model receives only the patient profile and generates a free-text medical recommendation. This will include LLM-as-a-judge evaluation alongside automatic metrics (BLEU, token overlap). Stay tuned for updates.

---


<!--
## Citation

If you use DocTalkBN in your research, please cite:

```bibtex
@article{doctalk2025,
  title   = {DocTalkBN: A Multimodal Conversational Medical Dataset in Bengali},
  year    = {2025}
}
```
-->

---

## License

Please refer to the repository for license information.
