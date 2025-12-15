#!/usr/bin/env python3
import json
import sys
from pathlib import Path

input_file = Path(sys.argv[1])
output_file = Path(sys.argv[2])

with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

video_ids = []

for item in data.get("data", []):
    if item.get("type") == "video" and "videoId" in item:
        video_ids.append(item["videoId"])

with open(output_file, "w", encoding="utf-8") as f:
    for vid in video_ids:
        f.write(vid + "\n")

print(f"Extracted {len(video_ids)} video IDs → {output_file}")
