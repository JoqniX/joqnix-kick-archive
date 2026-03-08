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


def safe_json(response):
    try:
        return response.json()
    except:
        return None


# ---------------------------------
# CHANNEL INFO
# ---------------------------------

channel_url = f"https://kick.com/api/v2/channels/{CHANNEL}"
print("Fetching channel:", channel_url)

r = session.get(channel_url)

if r.status_code != 200:
    print("Channel fetch failed:", r.status_code)
    exit(1)

channel_data = safe_json(r)

if not channel_data:
    print("Channel JSON parse failed")
    exit(1)

save_json(DATA_DIR / "channel.json", channel_data)

channel_id = channel_data["id"]

print("Channel ID:", channel_id)


# ---------------------------------
# CHANNEL VIDEOS
# ---------------------------------

videos_url = f"https://kick.com/api/v2/channels/{CHANNEL}/videos"

print("Fetching videos:", videos_url)

r = session.get(videos_url)

videos_data = safe_json(r)

if videos_data:
    save_json(DATA_DIR / "videos.json", videos_data)
else:
    print("Videos endpoint returned empty data")


# ---------------------------------
# LIVE CHAT MESSAGES
# ---------------------------------

messages_url = f"https://kick.com/api/v2/channels/{channel_id}/messages"

print("Fetching messages:", messages_url)

r = session.get(messages_url)

messages_data = safe_json(r)

if messages_data:
    save_json(DATA_DIR / "messages.json", messages_data)
else:
    print("Messages endpoint empty (likely no active livestream)")


print("Kick fetch completed.")
