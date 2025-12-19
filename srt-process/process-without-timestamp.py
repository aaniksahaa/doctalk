import re

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

    return text


# Example usage:
with open("child-dengue.srt", "r", encoding="utf-8") as f:
    srt = f.read()
txt = srt_to_clean_text(srt)

# write to a txt file
with open("child-dengue.txt", "w", encoding="utf-8") as f:
    f.write(txt)
