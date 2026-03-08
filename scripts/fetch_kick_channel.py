from curl_cffi import requests
import json
from pathlib import Path

CHANNEL = "joqnix"
OUTPUT = Path("data/kick_channel.json")

url = f"https://kick.com/api/v2/channels/{CHANNEL}"

print("Fetching:", url)

r = requests.get(
    url,
    impersonate="chrome110"
)

if r.status_code != 200:
    print("Failed:", r.status_code)
    print(r.text[:500])
    exit(1)

data = r.json()

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Saved:", OUTPUT)
