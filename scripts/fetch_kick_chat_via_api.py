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


def fetch_user_profile(user_id, cache):

    if str(user_id) in cache:
        return cache[str(user_id)]

    url = f"https://kick.com/api/v2/users/{user_id}"

    try:

        r = requests.get(url, headers=HEADERS)

        data = r.json()

        cache[str(user_id)] = data

        print(f"Fetched user profile {user_id}")

        time.sleep(0.2)

        return data

    except Exception as e:

        print("User fetch failed:", user_id, e)

        return None


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

            if start_time <= ts <= end_time:
                collected.append(msg)

        cursor = data["data"]["cursor"]

        if not cursor:
            break

        time.sleep(0.4)

    return collected


def process_vod(vod_dir):

    meta_file = vod_dir / "metadata.json"

    if not meta_file.exists():
        return

    meta = json.loads(meta_file.read_text())

    channel_id = meta["channel_id"]
    start = datetime.fromisoformat(meta["created_at"])
    duration = meta["duration"]

    end = start + timedelta(seconds=duration)

    print("Processing VOD:", vod_dir.name)

    messages = fetch_chat(channel_id, start, end)

    user_cache = load_user_cache()

    for msg in messages:

        user_id = msg["sender"]["id"]

        fetch_user_profile(user_id, user_cache)

    save_user_cache(user_cache)

    out_file = vod_dir / "chat_raw.json"

    out_file.write_text(
        json.dumps(messages, indent=2, ensure_ascii=False)
    )

    print("Saved", len(messages), "messages")


def main():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            raw = vod / "chat_raw.json"

            if raw.exists():
                print(vod.name, "chat already exists")
                continue

            process_vod(vod)


if __name__ == "__main__":
    main()
