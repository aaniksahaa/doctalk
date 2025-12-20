# Example usage:
# python process-srt-with-timestamp.py input.srt output.txt
# python process-srt-with-timestamp.py RkWh5fOOx9s_yt-auto-transcription.srt RkWh5fOOx9s_transcription-processed-with-timestamp.txt


import re
import argparse
from dataclasses import dataclass
from typing import List, Tuple

TIME_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2},\d{3})$"
)
INDEX_RE = re.compile(r"^\d+$")
BRACKET_CUE_RE = re.compile(r"^\s*\[.*?\]\s*$")  # e.g. [মিউজিক]

def _comma_to_dot(ts: str) -> str:
    # "00:00:37,120" -> "00:00:37.120"
    return ts.replace(",", ".", 1)

@dataclass
class Cue:
    start: str  # "00:00:37,120"
    text: str

def parse_srt_blocks(srt: str, drop_bracket_cues: bool = True) -> List[Cue]:
    lines = srt.splitlines()
    i = 0
    cues: List[Cue] = []

    while i < len(lines):
        line = lines[i].strip()

        # skip empties
        if not line:
            i += 1
            continue

        # optional index line
        if INDEX_RE.match(line):
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()

        # timestamp line
        m = TIME_RE.match(line)
        if not m:
            # not a valid block start; skip
            i += 1
            continue

        start = m.group("start")
        i += 1

        # collect text lines until blank
        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            t = lines[i].strip()
            if not (drop_bracket_cues and BRACKET_CUE_RE.match(t)):
                text_lines.append(t)
            i += 1

        # join block text
        block_text = " ".join(text_lines).strip()
        if block_text:
            cues.append(Cue(start=start, text=block_text))

        # skip trailing blank(s)
        while i < len(lines) and not lines[i].strip():
            i += 1

    return cues

import re
from typing import List

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")  # common ZW chars
_WS_RE = re.compile(r"\s+")
_PUNC_SPACE_RE = re.compile(r"\s+([।!?.,:;])")

def _norm_for_match(s: str) -> str:
    """
    Normalize for robust duplicate/overlap detection.
    Keeps content, just removes annoying formatting differences.
    """
    s = _ZERO_WIDTH_RE.sub("", s)
    s = s.strip()
    s = _WS_RE.sub(" ", s)
    s = _PUNC_SPACE_RE.sub(r"\1", s)
    return s

def _find_suffix_prefix_overlap(a: str, b: str, *, min_chars: int = 18) -> int:
    """
    Returns length (in characters) of the longest suffix of a that is a prefix of b.
    Uses normalized strings.
    """
    a_n = _norm_for_match(a)
    b_n = _norm_for_match(b)

    max_k = min(len(a_n), len(b_n))
    # try longest first
    for k in range(max_k, min_chars - 1, -1):
        if a_n[-k:] == b_n[:k]:
            return k
    return 0

def dedupe_and_merge_cues(cues: List["Cue"]) -> List["Cue"]:
    """
    - Drops exact duplicates
    - Merges rolling captions (next cue repeats previous as prefix)
    - Also merges when there's a strong suffix/prefix overlap
    Keeps the earlier cue's timestamp.
    """
    cleaned: List["Cue"] = []

    for cue in cues:
        line = cue.text
        if not cleaned:
            cleaned.append(cue)
            continue

        prev_text = cleaned[-1].text

        line_n = _norm_for_match(line)
        prev_n = _norm_for_match(prev_text)

        # exact duplicate (after normalization)
        if line_n == prev_n:
            continue

        # current extends previous (rolling caption) => keep earlier ts, take longer text
        if line_n.startswith(prev_n) and len(line_n) > len(prev_n):
            cleaned[-1].text = line  # keep the richer/original text from current
            continue

        # previous extends current => drop current
        if prev_n.startswith(line_n) and len(prev_n) > len(line_n):
            continue

        # NEW: suffix/prefix overlap merge (handles "minor doubling" not caught by startswith)
        overlap_len = _find_suffix_prefix_overlap(prev_text, line, min_chars=18)
        if overlap_len > 0:
            # We want: prev + (line minus the overlapping prefix)
            # But overlap_len computed on normalized text, so remove overlap approximately:
            # Use word-based trimming to stay safe.
            prev_words = _norm_for_match(prev_text).split()
            line_words = _norm_for_match(line).split()

            # Find longest word overlap
            best = 0
            max_w = min(len(prev_words), len(line_words))
            for w in range(max_w, 2, -1):  # require at least 3 words overlap
                if prev_words[-w:] == line_words[:w]:
                    best = w
                    break

            if best > 0:
                # rebuild by taking original prev_text + remainder of *normalized* line
                remainder = " ".join(line_words[best:]).strip()
                merged = _norm_for_match(prev_text)
                if remainder:
                    merged = f"{merged} {remainder}"
                cleaned[-1].text = merged
                continue

        cleaned.append(cue)

    return cleaned


# def dedupe_and_merge_cues(cues: List[Cue]) -> List[Cue]:
#     """
#     Same logic you had, but keeps the original (earlier) start time
#     when the next line is just an extension (line.startswith(prev)).
#     """
#     cleaned: List[Cue] = []

#     for cue in cues:
#         line = cue.text
#         if not cleaned:
#             cleaned.append(cue)
#             continue

#         prev = cleaned[-1].text

#         # exact duplicate
#         if line == prev:
#             continue

#         # current extends previous => replace text, keep earlier timestamp
#         if line.startswith(prev) and len(line) > len(prev):
#             cleaned[-1].text = line
#             continue

#         # previous extends current => drop current
#         if prev.startswith(line) and len(prev) > len(line):
#             continue

#         cleaned.append(cue)

#     return cleaned

def _format_cue_with_turn_timestamps(start_ts: str, text: str) -> str:
    """
    If the cue contains speaker markers (>>), prefix each speaker turn with the
    cue's start timestamp:
        00:00:37.120 >> ...
    Keeps narration (text before first >>) without timestamp.
    """
    start_dot = _comma_to_dot(start_ts)
    s = text.strip()

    # Split on occurrences of >> (allow whitespace around it)
    parts = re.split(r"\s*>>\s*", s)
    starts_with_turn = s.startswith(">>")

    out_chunks: List[str] = []
    for idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        # idx==0 is narration if the original didn't start with >>
        if idx == 0 and not starts_with_turn:
            out_chunks.append(part)
        else:
            out_chunks.append(f"{start_dot} >> {part}")

    return "\n\n".join(out_chunks)

def srt_to_clean_text_with_turn_timestamps(
    srt: str,
    drop_bracket_cues: bool = True,
) -> str:
    cues = parse_srt_blocks(srt, drop_bracket_cues=drop_bracket_cues)
    cues = dedupe_and_merge_cues(cues)

    rendered_parts: List[str] = []
    for cue in cues:
        rendered_parts.append(_format_cue_with_turn_timestamps(cue.start, cue.text))

    text = " ".join(rendered_parts)

    # Punctuation spacing cleanup
    text = re.sub(r"\s+([।!?.,:;])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    # Restore paragraph breaks we intentionally inserted (they became spaces above)
    # Convert " <timestamp> >> " patterns back into paragraph starts
    text = re.sub(r"\s*(\d{2}:\d{2}:\d{2}\.\d{3}\s+>>)", r"\n\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process SRT file and generate clean text with speaker turn timestamps"
    )
    parser.add_argument("input_srt", help="Input SRT file (e.g., input.srt)")
    parser.add_argument("output_txt", help="Output text file (e.g., output.txt)")
    args = parser.parse_args()
    
    with open(args.input_srt, "r", encoding="utf-8") as f:
        srt = f.read()
    txt = srt_to_clean_text_with_turn_timestamps(srt)
    with open(args.output_txt, "w", encoding="utf-8") as f:
        f.write(txt)
    
    print(f"Successfully processed {args.input_srt} -> {args.output_txt}")
