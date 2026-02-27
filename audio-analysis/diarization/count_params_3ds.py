#!/usr/bin/env python3
"""
Count parameters in 3D-Speaker diarization pipeline sub-models:
  1. Speaker Embedding: CAM++ (iic/speech_campplus_sv_zh_en_16k-common_advanced)
  2. VAD: FSMN (iic/speech_fsmn_vad_zh-cn-16k-common-pytorch)
"""
import os
import sys
import torch

# Add 3D-Speaker to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, '3D-Speaker'))

from speakerlab.utils.config import Config
from speakerlab.utils.builder import build
from speakerlab.utils.utils import download_model_from_modelscope

def count_params(model, name):
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n  [{name}]")
    print(f"    Total parameters:     {total:>12,}")
    print(f"    Trainable parameters: {trainable:>12,}")
    return total, trainable

print("=" * 70)
print("3D-Speaker Diarization — Parameter Count Report")
print("=" * 70)

grand_total = 0
grand_trainable = 0

# 1. CAM++ Speaker Embedding Model
print("\n--- Loading CAM++ Speaker Embedding Model ---")
try:
    conf = {
        'model_id': 'iic/speech_campplus_sv_zh_en_16k-common_advanced',
        'revision': 'v1.0.0',
        'model_ckpt': 'campplus_cn_en_common.pt',
        'embedding_model': {
            'obj': 'speakerlab.models.campplus.DTDNN.CAMPPlus',
            'args': {
                'feat_dim': 80,
                'embedding_size': 192,
            },
        },
    }
    cache_dir = download_model_from_modelscope(conf['model_id'], conf['revision'])
    pretrained_model_path = os.path.join(cache_dir, conf['model_ckpt'])
    config = Config(conf)
    embedding_model = build('embedding_model', config)
    pretrained_state = torch.load(pretrained_model_path, map_location='cpu')
    embedding_model.load_state_dict(pretrained_state)
    embedding_model.eval()
    t, tr = count_params(embedding_model, "Speaker Embedding: CAM++")
    grand_total += t
    grand_trainable += tr
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# 2. FSMN VAD Model
print("\n--- Loading FSMN VAD Model ---")
try:
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks
    
    vad_conf = {
        'model_id': 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
        'revision': 'v2.0.4',
    }
    vad_cache_dir = download_model_from_modelscope(vad_conf['model_id'], vad_conf['revision'])
    vad_pipeline = pipeline(
        task=Tasks.voice_activity_detection,
        model=vad_cache_dir,
        device='cpu',
        disable_pbar=True,
        disable_update=True,
    )
    
    # Try to find the nn.Module inside the pipeline
    vad_model = None
    for attr_name in dir(vad_pipeline):
        try:
            attr = getattr(vad_pipeline, attr_name)
            if isinstance(attr, torch.nn.Module):
                t, tr = count_params(attr, f"VAD FSMN (attr: {attr_name})")
                if vad_model is None or t > 0:
                    vad_model = attr
                grand_total += t
                grand_trainable += tr
                break
        except:
            pass
    
    if vad_model is None:
        # Try model attribute directly
        if hasattr(vad_pipeline, 'model'):
            model_obj = vad_pipeline.model
            if isinstance(model_obj, torch.nn.Module):
                t, tr = count_params(model_obj, "VAD FSMN (model)")
                grand_total += t
                grand_trainable += tr
            elif hasattr(model_obj, 'model'):
                t, tr = count_params(model_obj.model, "VAD FSMN (model.model)")
                grand_total += t
                grand_trainable += tr
        print("  Could not find VAD nn.Module, trying alternate approaches...")
        # List all attributes for debugging
        for attr_name in sorted(dir(vad_pipeline)):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(vad_pipeline, attr_name)
                print(f"    {attr_name}: {type(attr).__name__}")
            except:
                pass
except Exception as e:
    print(f"  ERROR loading VAD model: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 70}")
print(f"GRAND TOTAL parameters:     {grand_total:>12,}")
print(f"GRAND TOTAL trainable:      {grand_trainable:>12,}")
print(f"{'=' * 70}")
