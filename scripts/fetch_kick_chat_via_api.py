import json
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
USER_CACHE_FILE = Path("cache/kick_users.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_user_cache():

    if USER_CACHE_FILE.exists():
        return json.loads(USER_CACHE_FILE.read_text())

    USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    return {}


def save_user_cache(cache):

    USER_CACHE_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False)
    )


def get_channel_id(channel):

    url = f"https://kick.com/api/v2/channels/{channel}"

    r = requests.get(url, headers=HEADERS)

    data = r.json()

    return data["id"]


def fetch_user_profile(user_id, cache):

    uid = str(user_id)

    if uid in cache:
        return

    try:

        url = f"https://kick.com/api/v2/users/{user_id}"

        r = requests.get(url, headers=HEADERS)

        data = r.json()

        cache[uid] = data

        print("Cached user:", user_id)

        time.sleep(0.15)

    except Exception as e:

        print("User fetch failed:", user_id, e)


def fetch_chat(channel_id, start_time, end_time):

    cursor = None
    collected = []

    while True:

        url = f"https://kick.com/api/v2/channels/{channel_id}/messages"

        if cursor:
            url += f"?cursor={cursor}"

        print("Fetching:", url)

        r = requests.get(url, headers=HEADERS)

        data = r.json()

        messages = data["data"]["messages"]

        if not messages:
            break

        for msg in messages:

            ts = datetime.fromisoformat(
                msg["created_at"].replace("Z", "+00:00")
            )

            # stop scanning once we reach before the stream
            if ts < start_time:
                print("Reached stream start — stopping")
                return collected

            if start_time <= ts <= end_time:
                collected.append(msg)

        cursor = data["data"]["cursor"]

        if not cursor:
            break

        time.sleep(0.35)

    return collected


def process_vod(vod_dir):

    meta_file = vod_dir / "metadata.json"

    if not meta_file.exists():
        return

    raw_file = vod_dir / "chat_raw.json"

    if raw_file.exists():
        print(vod_dir.name, "chat already downloaded")
        return

    meta = json.loads(meta_file.read_text())

    channel = meta["channel"]

    channel_id = meta.get("channel_id")

if not channel_id:
    print("channel_id missing in metadata — fetching dynamically")

    url = f"https://kick.com/api/v2/channels/{meta['channel']}"

    r = requests.get(url, headers=HEADERS)

    data = r.json()

    channel_id = data["id"]

    start = datetime.utcfromtimestamp(meta["timestamp"])

    duration = meta.get("duration_seconds", 0)

    end = start + timedelta(seconds=duration)

    print("Processing:", vod_dir.name)

    messages = fetch_chat(channel_id, start, end)

    print("Messages collected:", len(messages))

    unique = {}

    for msg in messages:
        unique[msg["id"]] = msg

    messages = list(unique.values())

    user_cache = load_user_cache()

    for msg in messages:

        fetch_user_profile(msg["sender"]["id"], user_cache)

    save_user_cache(user_cache)

    raw_file.write_text(
        json.dumps(messages, indent=2, ensure_ascii=False)
    )

    print("Saved chat:", raw_file)


def main():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            process_vod(vod)


if __name__ == "__main__":
    main()
