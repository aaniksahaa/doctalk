#!/usr/bin/env python3
"""
Titu ASR Model - Bengali Speech Recognition using NeMo FastConformer

Supports long audio files by chunking into smaller segments with overlap.
"""

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import nemo.collections.asr as nemo_asr


MODEL_ID_DEFAULT = "hishab/titu_stt_bn_fastconformer"
TARGET_SR = 16000

# Chunking parameters for long audio
DEFAULT_CHUNK_DURATION_S = 300  # 5 minutes per chunk
DEFAULT_OVERLAP_S = 10  # 10 seconds overlap between chunks


def load_audio(path: str, target_sr: int = TARGET_SR) -> tuple[np.ndarray, int]:
    """Load audio file and resample to target sample rate."""
    audio, sr = sf.read(path, always_2d=False)
    
    # Convert stereo to mono
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    
    audio = audio.astype(np.float32, copy=False)
    
    # Resample if needed
    if sr != target_sr:
        import torchaudio
        wav = torch.from_numpy(audio).unsqueeze(0)
        wav = torchaudio.functional.resample(wav, orig_freq=sr, new_freq=target_sr)
        audio = wav.squeeze(0).numpy()
        sr = target_sr
    
    return audio, sr


def get_audio_duration(audio: np.ndarray, sr: int) -> float:
    """Get audio duration in seconds."""
    return len(audio) / sr


def chunk_audio(audio: np.ndarray, sr: int, 
                chunk_duration_s: float, overlap_s: float) -> list[tuple[np.ndarray, int, int]]:
    """Split audio into overlapping chunks.
    
    Returns list of (chunk_audio, start_sample, end_sample) tuples.
    """
    chunk_samples = int(chunk_duration_s * sr)
    overlap_samples = int(overlap_s * sr)
    step_samples = chunk_samples - overlap_samples
    
    chunks = []
    start = 0
    
    while start < len(audio):
        end = min(start + chunk_samples, len(audio))
        chunk = audio[start:end]
        chunks.append((chunk, start, end))
        
        if end >= len(audio):
            break
        start += step_samples
    
    return chunks


def save_temp_chunk(chunk: np.ndarray, sr: int, temp_dir: Path, idx: int) -> Path:
    """Save audio chunk to temporary file."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"chunk_{idx:04d}.wav"
    sf.write(temp_path, chunk, sr)
    return temp_path


def transcribe_with_chunking(asr_model, audio_path: str, 
                             chunk_duration_s: float = DEFAULT_CHUNK_DURATION_S,
                             overlap_s: float = DEFAULT_OVERLAP_S) -> str:
    """Transcribe audio file, using chunking for long files."""
    
    audio, sr = load_audio(audio_path)
    duration = get_audio_duration(audio, sr)
    
    # If audio is short enough, transcribe directly (with some margin)
    if duration <= chunk_duration_s + 60:  # Add 1 min margin
        result = asr_model.transcribe([audio_path])
        return result[0].text.strip()
    
    # Long audio - use chunking
    print(f"  Long audio detected ({duration:.1f}s), using chunking...")
    
    chunks = chunk_audio(audio, sr, chunk_duration_s, overlap_s)
    print(f"  Split into {len(chunks)} chunks")
    
    # Create temp directory for chunks
    temp_dir = Path(audio_path).parent / ".temp_chunks"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        transcriptions = []
        
        for i, (chunk_data, start, end) in enumerate(chunks):
            # Save chunk to temp file
            temp_path = save_temp_chunk(chunk_data, sr, temp_dir, i)
            
            # Transcribe chunk
            print(f"  Transcribing chunk {i+1}/{len(chunks)} ({start/sr:.1f}s - {end/sr:.1f}s)...")
            result = asr_model.transcribe([str(temp_path)])
            text = result[0].text.strip()
            transcriptions.append(text)
            
            # Clean up temp file
            temp_path.unlink()
        
        # Merge transcriptions
        # Simple merge: join with space (works well for most cases)
        # The overlap helps avoid cutting words, so we don't need complex merging
        merged = " ".join(t for t in transcriptions if t)
        
        return merged
        
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            for f in temp_dir.iterdir():
                f.unlink()
            temp_dir.rmdir()


def main():
    ap = argparse.ArgumentParser(
        description="Bengali ASR using Titu FastConformer (NeMo)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input-filepath", required=True,
                    help="Input audio file path")
    ap.add_argument("--output-filepath", required=True,
                    help="Output transcript file path")
    ap.add_argument("--model-id", default=MODEL_ID_DEFAULT,
                    help=f"Model ID (default: {MODEL_ID_DEFAULT})")
    ap.add_argument("--chunk-duration", type=float, default=DEFAULT_CHUNK_DURATION_S,
                    help=f"Chunk duration in seconds for long audio (default: {DEFAULT_CHUNK_DURATION_S})")
    ap.add_argument("--overlap", type=float, default=DEFAULT_OVERLAP_S,
                    help=f"Overlap between chunks in seconds (default: {DEFAULT_OVERLAP_S})")
    args = ap.parse_args()

    in_path = Path(args.input_filepath)
    out_path = Path(args.output_filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load model
    asr_model = nemo_asr.models.ASRModel.from_pretrained(args.model_id)
    
    # Transcribe with chunking support
    transcription = transcribe_with_chunking(
        asr_model, 
        str(in_path),
        chunk_duration_s=args.chunk_duration,
        overlap_s=args.overlap
    )

    out_path.write_text(transcription + "\n", encoding="utf-8")
    print(transcription)


if __name__ == "__main__":
    main()
