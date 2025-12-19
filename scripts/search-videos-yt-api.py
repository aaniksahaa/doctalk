# this is just a basic test, we need to handle pagination etc many things...
# search-videos-yt-api.py

import json
import http.client

conn = http.client.HTTPSConnection("yt-api.p.rapidapi.com")

KEY = "683351e6d6msh5280d130f8100c4p1b86d2jsn83e8d30556e0"

headers = {
    'x-rapidapi-key': KEY,
    'x-rapidapi-host': "yt-api.p.rapidapi.com"
}

conn.request(
    "GET", "/search?query=Sustho%20Thakun%20-%20Rtv%20Health&geo=BD&duration=long&sort_by=date", headers=headers)

res = conn.getresponse()
data = res.read()

# data as json
data_json = json.loads(data.decode("utf-8"))

# pretty print the json
print(json.dumps(data_json, indent=4))
