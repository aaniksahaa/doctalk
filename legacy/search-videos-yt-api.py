"""
search_videos_yt_api.py

Basic YouTube search using yt-api (RapidAPI)
- Clean parameter handling
- No manual URL encoding
- Pretty JSON output
"""

import json
import http.client
import os
from urllib.parse import urlencode


# -----------------------
# Configuration
# -----------------------

API_HOST = "yt-api.p.rapidapi.com"
API_KEY = os.getenv("RAPIDAPI_KEY", "683351e6d6msh5280d130f8100c4p1b86d2jsn83e8d30556e0")

OUTPUT_FILE = "search_results.json"


# -----------------------
# Search Parameters
# -----------------------

params = {
    "query": "Sustho Thakun - Rtv Health",
    "geo": "BD",
    "duration": "long",
    "sort_by": "date",
    # pagination-ready 👇
    # "continuation": None,
}


# -----------------------
# Request Setup
# -----------------------

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST,
}

query_string = urlencode(params)
endpoint = f"/search?{query_string}"


# -----------------------
# Make Request
# -----------------------

conn = http.client.HTTPSConnection(API_HOST)
conn.request("GET", endpoint, headers=headers)

response = conn.getresponse()
raw_data = response.read()

conn.close()


# -----------------------
# Parse & Save JSON
# -----------------------

data_json = json.loads(raw_data.decode("utf-8"))

# Pretty print to console
print(json.dumps(data_json, indent=4, ensure_ascii=False))

# Save nicely to file
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data_json, f, indent=4, ensure_ascii=False)

print(f"\n✅ Results saved to: {OUTPUT_FILE}")
