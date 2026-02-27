# Example usage:
# python process-srt-without-timestamp.py input.srt output.txt
# python process-srt-without-timestamp.py RkWh5fOOx9s_transcription.srt RkWh5fOOx9s_transcription-processed-without-timestamp.txt

import re
import argparse

TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$")
INDEX_RE = re.compile(r"^\d+$")
BRACKET_CUE_RE = re.compile(r"^\s*\[.*?\]\s*$")  # e.g. [মিউজিক]

def srt_to_clean_text(srt: str, drop_bracket_cues: bool = True) -> str:
    raw_lines = []
    for line in srt.splitlines():
        line = line.strip()
        if not line:
            continue
        if INDEX_RE.match(line):
            continue
        if TIME_RE.match(line):
            continue
        if drop_bracket_cues and BRACKET_CUE_RE.match(line):
            continue
        raw_lines.append(line)

    cleaned = []
    for line in raw_lines:
        if not cleaned:
            cleaned.append(line)
            continue

        prev = cleaned[-1]

        if line == prev:
            continue

        if line.startswith(prev) and len(line) > len(prev):
            cleaned[-1] = line
            continue

        if prev.startswith(line) and len(prev) > len(line):
            continue

        cleaned.append(line)

    text = " ".join(cleaned)

    text = re.sub(r"\s+([।!?.,:;])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    # force new paragraph before every >>
    text = re.sub(r"\s*>>", "\n\n>>", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # add sequence numbers before every >>
    lines = text.split("\n")
    sequence_num = 1
    for i, line in enumerate(lines):
        if line.startswith(">>"):
            lines[i] = f"{sequence_num}. {line}"
            sequence_num += 1
    text = "\n".join(lines)

    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process SRT file and generate clean text without timestamps"
    )
    parser.add_argument("input_srt", help="Input SRT file (e.g., input.srt)")
    parser.add_argument("output_txt", help="Output text file (e.g., output.txt)")
    args = parser.parse_args()
    
    with open(args.input_srt, "r", encoding="utf-8") as f:
        srt = f.read()
    txt = srt_to_clean_text(srt)
    
    with open(args.output_txt, "w", encoding="utf-8") as f:
        f.write(txt)
    
    print(f"Successfully processed {args.input_srt} -> {args.output_txt}")
