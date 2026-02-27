#!/usr/bin/env python3
"""
Count parameters in NeMo ClusteringDiarizer sub-models:
  1. VAD model  (vad_multilingual_marblenet)
  2. Speaker embedding model (titanet_large)
  3. MSDD model (diar_msdd_telephonic)

We load each model individually and count parameters.
"""
import torch


def count_params(model, name):
    """Count and print parameters for a model."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n  [{name}]")
    print(f"    Total parameters:     {total:>12,}")
    print(f"    Trainable parameters: {trainable:>12,}")
    return total, trainable


print("=" * 70)
print("NeMo ClusteringDiarizer — Parameter Count Report")
print("=" * 70)

grand_total = 0
grand_trainable = 0

# 1. VAD Model
print("\n--- Loading VAD model (vad_multilingual_marblenet) ---")
try:
    from nemo.collections.asr.models import EncDecClassificationModel
    vad_model = EncDecClassificationModel.from_pretrained("vad_multilingual_marblenet")
    t, tr = count_params(vad_model, "VAD: vad_multilingual_marblenet")
    grand_total += t
    grand_trainable += tr
except Exception as e:
    print(f"  ERROR loading VAD model: {e}")

# 2. Speaker Embedding Model
print("\n--- Loading Speaker Embedding model (titanet_large) ---")
try:
    from nemo.collections.asr.models import EncDecSpeakerLabelModel
    spk_model = EncDecSpeakerLabelModel.from_pretrained("titanet_large")
    t, tr = count_params(spk_model, "Speaker Embedding: titanet_large")
    grand_total += t
    grand_trainable += tr
except Exception as e:
    print(f"  ERROR loading Speaker model: {e}")

# 3. MSDD Model
print("\n--- Loading MSDD model (diar_msdd_telephonic) ---")
try:
    from nemo.collections.asr.models import EncDecDiarLabelModel
    msdd_model = EncDecDiarLabelModel.from_pretrained("diar_msdd_telephonic")
    t, tr = count_params(msdd_model, "MSDD: diar_msdd_telephonic")
    grand_total += t
    grand_trainable += tr
except Exception as e:
    # Try alternative import
    try:
        from nemo.collections.asr.models.msdd_models import EncDecDiarLabelModel
        msdd_model = EncDecDiarLabelModel.from_pretrained("diar_msdd_telephonic")
        t, tr = count_params(msdd_model, "MSDD: diar_msdd_telephonic")
        grand_total += t
        grand_trainable += tr
    except Exception as e2:
        # Try yet another way
        try:
            from nemo.collections.asr.models import NeuralDiarizer
            # The NeuralDiarizer might wrap MSDD
            print(f"  Could not load MSDD standalone ({e}), trying NeuralDiarizer...")
            print(f"  Also tried msdd_models import: {e2}")
        except Exception as e3:
            print(f"  ERROR loading MSDD model: {e}")
            print(f"  All fallback attempts failed: {e2}, {e3}")

print(f"\n{'=' * 70}")
print(f"GRAND TOTAL parameters:     {grand_total:>12,}")
print(f"GRAND TOTAL trainable:      {grand_trainable:>12,}")
print(f"{'=' * 70}")

# Also show individual NeMo model card info if available
print("\n\nNeMo model info (for reference):")
try:
    listed = EncDecClassificationModel.list_available_models()
    for m in listed:
        if 'marblenet' in m.pretrained_model_name.lower():
            print(f"  VAD: {m.pretrained_model_name}")
except Exception:
    pass

try:
    listed = EncDecSpeakerLabelModel.list_available_models()
    for m in listed:
        if 'titanet' in m.pretrained_model_name.lower():
            print(f"  Speaker: {m.pretrained_model_name}")
except Exception:
    pass
