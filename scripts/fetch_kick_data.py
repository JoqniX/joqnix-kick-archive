from curl_cffi import requests
import json
from pathlib import Path

CHANNEL = "joqnix"

DATA_DIR = Path("data/kick")
DATA_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session(impersonate="chrome110")

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# -----------------------------------
# 1. CHANNEL DATA
# -----------------------------------

channel_url = f"https://kick.com/api/v2/channels/{CHANNEL}"

print("Fetching channel:", channel_url)

r = session.get(channel_url)

if r.status_code != 200:
    print("Channel fetch failed:", r.status_code)
    exit(1)

channel_data = r.json()

save_json(DATA_DIR / "channel.json", channel_data)

channel_id = channel_data["id"]

print("Channel ID:", channel_id)

# -----------------------------------
# 2. VIDEOS
# -----------------------------------

videos_url = f"https://kick.com/api/v2/channels/{CHANNEL}/videos"

print("Fetching videos:", videos_url)

r = session.get(videos_url)

if r.status_code == 200:
    videos_data = r.json()
    save_json(DATA_DIR / "videos.json", videos_data)
else:
    print("Videos fetch failed:", r.status_code)

# -----------------------------------
# 3. CHAT MESSAGES
# -----------------------------------

messages_url = f"https://kick.com/api/v2/messages/{channel_id}"

print("Fetching messages:", messages_url)

r = session.get(messages_url)

if r.status_code == 200:
    messages_data = r.json()
    save_json(DATA_DIR / "messages.json", messages_data)
else:
    print("Messages fetch failed:", r.status_code)

print("Done.")
