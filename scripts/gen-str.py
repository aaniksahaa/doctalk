import json

with open("metadata.json") as f:
    data = json.load(f)

caps = data.get("automatic_captions", {})

def find_srt(caps):
    for lang in ["bn-orig", "bn"]:
        if lang in caps:
            for item in caps[lang]:
                if item.get("ext") == "srt":
                    return item["url"]
    return None

srt_url = find_srt(caps)

if srt_url:
    print(srt_url)
else:
    print("No Bangla SRT found")
