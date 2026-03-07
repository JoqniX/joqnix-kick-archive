import json
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
USER_CACHE_FILE = Path("cache/kick_users.json")

WORKER_BASE = "https://kick-proxy.onaixia.workers.dev/api/kick"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ------------------------------
# USER CACHE
# ------------------------------

def load_user_cache():

    if USER_CACHE_FILE.exists():
        try:
            return json.loads(USER_CACHE_FILE.read_text())
        except:
            return {}

    USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    return {}


def save_user_cache(cache):

    USER_CACHE_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False)
    )


# ------------------------------
# CHANNEL ID
# ------------------------------

def get_channel_id(channel):

    url = f"{WORKER_BASE}/channel?channel={channel}"

    r = requests.get(url, headers=HEADERS)

    data = r.json()

    if "id" in data:
        return data["id"]

    raise Exception(f"Invalid channel response: {data}")


# ------------------------------
# USER PROFILE
# ------------------------------

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

        time.sleep(0.1)

    except Exception as e:

        print("User fetch failed:", user_id, e)


# ------------------------------
# CHAT FETCH
# ------------------------------

def fetch_chat(channel_id, start_time, end_time):

    collected = []
    seen_ids = set()

    # cursor jump trick
    cursor = int(start_time.timestamp() * 1000)

    print("Cursor jump start:", cursor)

    while True:

        url = f"{WORKER_BASE}/chat?channel_id={channel_id}&cursor={cursor}"

        print("Fetching:", url)

        r = requests.get(url, headers=HEADERS)

        try:
            data = r.json()
        except:
            print("Invalid JSON")
            break

        if "data" not in data:
            print("Invalid response:", data)
            break

        messages = data["data"].get("messages", [])

        if not messages:
            break

        for msg in messages:

            msg_id = msg.get("id")

            if msg_id in seen_ids:
                continue

            seen_ids.add(msg_id)

            ts = datetime.fromisoformat(
                msg["created_at"].replace("Z", "+00:00")
            )

            if ts > end_time:
                continue

            if ts < start_time:
                print("Reached stream start")
                return collected

            collected.append(msg)

        cursor = data["data"].get("cursor")

        if not cursor:
            break

        time.sleep(0.2)

    return collected


# ------------------------------
# VOD PROCESSOR
# ------------------------------

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

        print("Fetching channel id")

        channel_id = get_channel_id(channel)

    start = datetime.utcfromtimestamp(meta["timestamp"])

    duration = meta.get("duration_seconds", 0)

    end = start + timedelta(seconds=duration)

    print("Processing:", vod_dir.name)

    messages = fetch_chat(channel_id, start, end)

    print("Messages collected:", len(messages))

    if not messages:
        print("No chat messages found")
        raw_file.write_text("[]")
        return

    unique = {}

    for msg in messages:
        unique[msg["id"]] = msg

    messages = list(unique.values())

    user_cache = load_user_cache()

    for msg in messages:

        sender = msg.get("sender")

        if not sender:
            continue

        uid = sender.get("id")

        if uid:
            fetch_user_profile(uid, user_cache)

    save_user_cache(user_cache)

    raw_file.write_text(
        json.dumps(messages, indent=2, ensure_ascii=False)
    )

    print("Saved chat:", raw_file)


# ------------------------------
# MAIN
# ------------------------------

def main():

    if not ARCHIVE_ROOT.exists():
        print("Archive missing")
        return

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            process_vod(vod)


if __name__ == "__main__":
    main()
