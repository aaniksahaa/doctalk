#!/usr/bin/env python3
import argparse
from pathlib import Path

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


MODEL_ID_DEFAULT = "anuragshas/whisper-large-v2-bn"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-filepath", required=True)
    ap.add_argument("--output-filepath", required=True)
    ap.add_argument("--model-id", default=MODEL_ID_DEFAULT)
    args = ap.parse_args()

    in_path = Path(args.input_filepath)
    out_path = Path(args.output_filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        args.model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    ).to(device)

    processor = AutoProcessor.from_pretrained(args.model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )

    result = pipe(str(in_path), generate_kwargs={"language": "bn"})
    text = result["text"].strip()

    out_path.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
