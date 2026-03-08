import requests
import json
from pathlib import Path

CHANNEL = "joqnix"   # change to your channel
OUTPUT = Path("data/kick_channel.json")

url = f"https://kick.com/api/v2/channels/{CHANNEL}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Accept": "application/json",
    "Referer": f"https://kick.com/{CHANNEL}"
}

print("Fetching:", url)

r = requests.get(url, headers=headers)

if r.status_code != 200:
    print("Failed:", r.status_code)
    exit(1)

data = r.json()

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Saved to", OUTPUT)
