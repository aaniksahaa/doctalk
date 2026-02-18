# Speaker Diarization

This directory contains three speaker diarization implementations with a unified interface.

## Overview

| Script | Backend | Conda Env | Description |
|--------|---------|-----------|-------------|
| `diapyan.py` | pyannote-audio 3.1 | `pyan` | Hugging Face-based, requires HF token |
| `dianemo.py` | NVIDIA NeMo | `nemo` | NVIDIA's diarization toolkit |
| `dia3ds.py` | 3D-Speaker | `s3d_clean` | Alibaba's speaker diarization |

## Environment Setup

### 1. Create Conda Environments from YAML

```bash
# Create all three environments
conda env create -f envs/pyan.yml
conda env create -f envs/nemo.yml
conda env create -f envs/s3d_clean.yml
```

### 2. Additional Setup

#### pyannote (pyan)

1. Create a `.env` file in this directory with your Hugging Face token:
   ```
   HF_TOKEN=your_huggingface_token_here
   ```

2. Accept the model conditions on Hugging Face:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0

#### 3D-Speaker (s3d_clean)

Ensure the `3D-Speaker` repository is cloned in this directory:
```bash
git clone https://github.com/alibaba-damo-academy/3D-Speaker.git
```

Models are automatically downloaded from ModelScope on first run to `~/.cache/modelscope/hub/models/iic/`.

## Quick Test

Verify all environments work with a test audio file:
```bash
# Test pyannote
conda activate pyan
python diapyan.py -i test_1.wav -o out_pyan.csv

# Test NeMo
conda activate nemo
python dianemo.py -i test_1.wav -o out_nemo.csv

# Test 3D-Speaker
conda activate s3d_clean
python dia3ds.py -i test_1.wav -o out_3ds.csv
```

## Batch Processing

For processing multiple files with evaluation, use the batch runner:

### Dataset Structure

The runner expects this directory structure:
```
data_root/
├── some_split/
│   ├── audio/
│   │   ├── file1.wav
│   │   └── file2.wav
│   └── annotation/
│       ├── file1.csv    # Ground truth
│       └── file2.csv
└── another_split/
    ├── audio/
    └── annotation/
```

After running, predictions are saved to:
```
data_root/
├── some_split/
│   ├── audio/
│   ├── annotation/
│   └── prediction/
│       ├── nemo/
│       │   ├── annotation/
│       │   │   └── file1.csv    # Predicted diarization
│       │   └── metrics/
│       │       └── file1.csv    # DER and inference time
│       ├── pyan/
│       └── 3ds/
```

### Run Batch Diarization

```bash
# Dry run - see what would be processed
python run_diarization.py --data_root dataset --models "nemo;pyan;3ds" --dry_run

# Run all models (skips files that already have predictions)
python run_diarization.py --data_root dataset --models "nemo;pyan;3ds"

# Force re-inference even if output exists
python run_diarization.py --data_root dataset --models "nemo;pyan;3ds" --fresh

# Run specific models only
python run_diarization.py --data_root dataset --models "pyan;nemo"
python run_diarization.py --data_root dataset --models "pyan"
```

### Collect and Aggregate Metrics

After inference completes:
```bash
python collect_metrics.py --data_root dataset

# Or specify output directory
python collect_metrics.py --data_root dataset --output_dir results
```

This produces:
- `all_metrics.csv` - All individual results (one row per file per model)
- `summary.csv` - Model-wise averages (DER, inference time)

## Usage

All scripts use a unified interface:
- `-i` / `--input`: Input audio file (required)
- `-o` / `--output`: Output CSV file (optional, defaults to `<input_stem>.csv`)

### Output Format

All scripts output CSV with the same format:
```csv
start_time,end_time,speaker_id
00:00:13,00:01:13,1
00:01:54,00:02:20,2
00:02:23,00:02:32,1
```

- `start_time`: Segment start in HH:MM:SS format
- `end_time`: Segment end in HH:MM:SS format
- `speaker_id`: Integer speaker ID (1, 2, 3, ...)

### Running Diarization

#### pyannote-audio
```bash
conda activate pyan
python diapyan.py -i input.wav -o output_pyan.csv
```

#### NVIDIA NeMo
```bash
conda activate nemo
python dianemo.py -i input.wav -o output_nemo.csv
```

#### 3D-Speaker
```bash
conda activate s3d_clean
python dia3ds.py -i input.wav -o output_3ds.csv
```

## Additional Options

### diapyan.py
- `--cpu`: Force CPU inference (default: CUDA if available)
- `--num_speakers N`: Force exact number of speakers
- `--min_speakers N`: Minimum number of speakers
- `--max_speakers N`: Maximum number of speakers
- `--no_progress`: Disable progress bar

### dianemo.py
- `--cpu`: Force CPU inference (default: CUDA if available)
- `--out_dir DIR`: Working directory for intermediate files
- `--num_speakers N`: Oracle speaker count

### dia3ds.py
- `--cpu`: Force CPU inference (default: GPU if available)
- `--out_dir DIR`: Working directory for intermediate files

## Troubleshooting

### pyannote: "missing Hugging Face token"
- Ensure `.env` file exists with `HF_TOKEN=...`
- Or set environment variable: `export HF_TOKEN=your_token`
- Or pass via CLI: `--hf_token your_token`

### CUDA not available
- All scripts auto-fallback to CPU if CUDA is unavailable
- Use `--cpu` flag to explicitly force CPU inference

### Environment recreation issues
If exact environment recreation fails due to platform differences, install key packages manually using the tested steps below:

#### pyan (pyannote-audio 3.1)
```bash
conda create -n pyan python=3.10 -y
conda activate pyan

python -m pip install -U pip setuptools wheel
pip install "numpy<2"

# PyTorch with CUDA 12.1 support
pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu121

pip install pyannote.audio==3.1.1
pip install "huggingface_hub<1.0" --force-reinstall
pip install python-dotenv

# Verify installation
python -c "import numpy as np; import torch, torchaudio; import huggingface_hub; print('numpy', np.__version__); print('torch', torch.__version__); print('torchaudio', torchaudio.__version__); print('hub', huggingface_hub.__version__); print('cuda?', torch.cuda.is_available())"
```

#### nemo (NVIDIA NeMo)
```bash
conda create -n nemo python=3.10 -y
conda activate nemo

pip install "numpy<2" "packaging<25"
pip install -U "nemo_toolkit[asr]"
pip install "matplotlib<3.9"

# Install librosa dependencies via conda for better compatibility
conda install -y -c conda-forge platformdirs pooch librosa numba soundfile

# Verify installation
python -c "import numpy, packaging; print('numpy', numpy.__version__, 'packaging', packaging.__version__)"
python -c "from nemo.collections.asr.models import ClusteringDiarizer; print('OK')"
```

#### s3d_clean (3D-Speaker)
```bash
conda create -y -n s3d_clean python=3.10
conda activate s3d_clean

# GPU with CUDA 11.8
conda install -y -c pytorch -c nvidia pytorch torchvision torchaudio pytorch-cuda=11.8

# Fix iJIT_NotifyEvent issue by pinning MKL below 2024.1
conda install -y -c conda-forge "mkl<2024.1" intel-openmp

python -m pip install -U pip setuptools wheel

# Clone 3D-Speaker if not already done
git clone https://github.com/alibaba-damo-academy/3D-Speaker.git
cd 3D-Speaker

# Install base requirements
python -m pip install -r requirements.txt

# Install diarization example requirements
python -m pip install -r egs/3dspeaker/speaker-diarization/requirements.txt

# ModelScope extras needed by diarization script
python -m pip install addict oss2

cd ..

# Verify installation
python -c "import torch; print('torch', torch.__version__); print('cuda?', torch.cuda.is_available())"
python -c "import numpy, datasets; print('numpy', numpy.__version__, 'datasets', datasets.__version__)"
python -c "import modelscope; print('modelscope', modelscope.__version__)"
```

## DER Evaluation

A separate minimal environment for computing Diarization Error Rate:

```bash
conda create -y -n der_eval python=3.10
conda activate der_eval

python -m pip install -U pip
python -m pip install pyannote.core pyannote.metrics

# Verify
python -c "from pyannote.core import Annotation, Segment; from pyannote.metrics.diarization import DiarizationErrorRate; print('pyannote metrics OK')"

# Run DER evaluation
python der.py \
  --reference_csv path/to/reference.csv \
  --hypothesis_csv path/to/hypothesis.csv
```

