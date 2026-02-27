#!/usr/bin/env python3
"""
Count trainable parameters in pyannote/speaker-diarization-3.1 pipeline.
"""
import os
import sys
from pathlib import Path

# Load .env for HF_TOKEN
_script_dir = Path(__file__).parent.resolve()
_env_file = _script_dir / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

import torch
from pyannote.audio import Pipeline

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    print("ERROR: HF_TOKEN not found in env or .env file", file=sys.stderr)
    sys.exit(1)

print("Loading pyannote/speaker-diarization-3.1 pipeline...")
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HF_TOKEN,
)

print("\n" + "=" * 70)
print("PyAnnote speaker-diarization-3.1 — Parameter Count Report")
print("=" * 70)

# Print all attributes of the pipeline for debugging
print("\n--- Pipeline attributes ---")
for attr_name in sorted(dir(pipeline)):
    if attr_name.startswith('__'):
        continue
    try:
        attr = getattr(pipeline, attr_name)
        atype = type(attr).__name__
        if isinstance(attr, torch.nn.Module):
            total = sum(p.numel() for p in attr.parameters())
            print(f"  {attr_name}: {atype} ({total:,} params)")
        elif not callable(attr):
            print(f"  {attr_name}: {atype} = {repr(attr)[:100]}")
    except Exception as e:
        print(f"  {attr_name}: ERROR: {e}")

# Try to find sub-models through known pyannote pipeline structure
print("\n--- Searching for nn.Module instances in pipeline ---")
grand_total = 0
grand_trainable = 0
found_models = {}

def find_modules(obj, prefix="pipeline", depth=0):
    """Recursively search for nn.Module instances."""
    if depth > 3:
        return
    for attr_name in dir(obj):
        if attr_name.startswith('__'):
            continue
        try:
            attr = getattr(obj, attr_name)
            full_name = f"{prefix}.{attr_name}"
            if isinstance(attr, torch.nn.Module) and id(attr) not in found_models:
                total = sum(p.numel() for p in attr.parameters())
                trainable = sum(p.numel() for p in attr.parameters() if p.requires_grad)
                found_models[id(attr)] = full_name
                print(f"\n  [{full_name}] ({type(attr).__name__})")
                print(f"    Total parameters:     {total:>12,}")
                print(f"    Trainable parameters: {trainable:>12,}")
        except Exception:
            pass

find_modules(pipeline)

# Also try: the pipeline is a SpeakerDiarization instance
# It typically has:
#   - pipeline._segmentation (segmentation model)
#   - pipeline._embedding (embedding model)
# Let's check the class
print(f"\n--- Pipeline class: {type(pipeline).__name__} ---")
print(f"    MRO: {[c.__name__ for c in type(pipeline).__mro__]}")

# Direct approach: load the sub-models individually
print("\n\n--- Loading sub-models individually ---")

# 1. Segmentation model
print("\n1. Segmentation model (pyannote/segmentation-3.0):")
try:
    from pyannote.audio import Model as PyannoteModel
    seg_model = PyannoteModel.from_pretrained("pyannote/segmentation-3.0", use_auth_token=HF_TOKEN)
    total = sum(p.numel() for p in seg_model.parameters())
    trainable = sum(p.numel() for p in seg_model.parameters() if p.requires_grad)
    print(f"    Model type: {type(seg_model).__name__}")
    print(f"    Total parameters:     {total:>12,}")
    print(f"    Trainable parameters: {trainable:>12,}")
    grand_total += total
    grand_trainable += trainable
except Exception as e:
    print(f"    ERROR: {e}")

# 2. Embedding model (wespeaker via speechbrain)
print("\n2. Embedding model (speechbrain/spkrec-wespeaker-voxceleb-resnet34):")
try:
    # pyannote 3.1 uses wespeaker-voxceleb-resnet34-LM via speechbrain
    from speechbrain.inference.speaker import EncoderClassifier
    emb_model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-resnet-voxceleb",
        run_opts={"device": "cpu"},
    )
    total = sum(p.numel() for p in emb_model.parameters())
    trainable = sum(p.numel() for p in emb_model.parameters() if p.requires_grad)
    print(f"    Model type: {type(emb_model).__name__}")
    print(f"    Total parameters:     {total:>12,}")
    print(f"    Trainable parameters: {trainable:>12,}")
    grand_total += total
    grand_trainable += trainable
except Exception as e:
    print(f"    ERROR: {e}")

# Try the wespeaker model used by pyannote 3.1
print("\n2b. Embedding model (pyannote/wespeaker-voxceleb-resnet34-LM):")
try:
    from pyannote.audio import Model as PyannoteModel
    emb_model2 = PyannoteModel.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=HF_TOKEN)
    total = sum(p.numel() for p in emb_model2.parameters())
    trainable = sum(p.numel() for p in emb_model2.parameters() if p.requires_grad)
    print(f"    Model type: {type(emb_model2).__name__}")
    print(f"    Total parameters:     {total:>12,}")
    print(f"    Trainable parameters: {trainable:>12,}")
except Exception as e:
    print(f"    ERROR: {e}")

# Try loading it via the pipeline's own config
print("\n\n--- Pipeline config/params ---")
try:
    params = pipeline.parameters()
    print(f"  pipeline.parameters(): {type(params)}")
    if hasattr(params, '__iter__'):
        for k, v in params.items() if isinstance(params, dict) else []:
            print(f"    {k}: {v}")
except Exception as e:
    print(f"  pipeline.parameters() error: {e}")

# Print hyperparameters
try:
    hp = pipeline.parameters(instantiated=True)
    print(f"\n  Instantiated params: {hp}")
except Exception as e:
    print(f"  Instantiated params error: {e}")

print(f"\n{'=' * 70}")
print(f"GRAND TOTAL (individual sub-models):     {grand_total:>12,}")
print(f"GRAND TOTAL trainable:                   {grand_trainable:>12,}")
print(f"{'=' * 70}")
