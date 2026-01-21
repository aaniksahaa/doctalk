#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


MODEL_ID_DEFAULT = "bengaliAI/tugstugi_bengaliai-asr_whisper-medium"
TARGET_SR = 16000


def load_audio_mono_resample(path: str, target_sr: int = TARGET_SR) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)  # stereo -> mono

    audio = audio.astype(np.float32, copy=False)

    if sr != target_sr:
        wav = torch.from_numpy(audio).unsqueeze(0)  # [1, T]
        wav = torchaudio.functional.resample(wav, orig_freq=sr, new_freq=target_sr)
        audio = wav.squeeze(0).cpu().numpy()
        sr = target_sr

    return audio, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-filepath", required=True)
    ap.add_argument("--output-filepath", required=True)
    ap.add_argument("--model-id", default=MODEL_ID_DEFAULT)
    ap.add_argument("--chunk-length-s", type=float, default=30.0, help="Chunking for long audio.")
    ap.add_argument("--stride-length-s", type=float, default=5.0, help="Overlap between chunks.")
    ap.add_argument("--cpu", action="store_true", help="Force CPU even if CUDA is available.")
    args = ap.parse_args()

    in_path = Path(args.input_filepath)
    out_path = Path(args.output_filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    audio, sr = load_audio_mono_resample(str(in_path), TARGET_SR)

    use_cuda = torch.cuda.is_available() and not args.cpu
    device = "cuda:0" if use_cuda else "cpu"
    dtype = torch.float16 if use_cuda else torch.float32

    # Load model and processor directly to fix generation config issues
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        args.model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    
    processor = AutoProcessor.from_pretrained(args.model_id)

    asr = pipeline(
        task="automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        device=device,
        torch_dtype=dtype,
    )

    result = asr(
        {"array": audio, "sampling_rate": sr},
        chunk_length_s=args.chunk_length_s,
        stride_length_s=args.stride_length_s,
        return_timestamps=False,
    )

    text = (result.get("text") or "").strip()

    out_path.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
