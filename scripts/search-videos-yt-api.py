# this is just a basic test, we need to handle pagination etc many things...

import http.client

conn = http.client.HTTPSConnection("yt-api.p.rapidapi.com")

KEY=None

headers = {
    'x-rapidapi-key': KEY,
    'x-rapidapi-host': "yt-api.p.rapidapi.com"
}

conn.request("GET", "/search?query=Sustho%20Thakun%20-%20Rtv%20Health&geo=BD&duration=long&sort_by=date", headers=headers)

res = conn.getresponse()
data = res.read()

# data as json
import json
data_json = json.loads(data.decode("utf-8"))

# pretty print the json
import json
print(json.dumps(data_json, indent=4))