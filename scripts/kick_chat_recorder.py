import json
import time
import requests
from pathlib import Path

CHANNELS = [
    "joqnix",
    "theburntpeanut",
    "joqnix247"
]

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

DATA_ROOT = Path("data/live_chat")

POLL_INTERVAL = 4
COMMIT_INTERVAL = 60


seen_ids = set()


def get_channel(channel):

    url = f"{WORKER}/channel/{channel}"

    r = requests.get(url)

    return r.json()


def get_live_stream(channel):

    url = f"{WORKER}/videos/{channel}"

    r = requests.get(url)

    data = r.json()

    for v in data:

        if v.get("is_live"):

            return v

    return None


def fetch_messages(channel):

    url = f"{WORKER}/messages/{channel}"

    r = requests.get(url)

    data = r.json()

    return data.get("messages", [])


def save_messages(channel, vod_id, messages):

    folder = DATA_ROOT / channel / vod_id
    folder.mkdir(parents=True, exist_ok=True)

    file = folder / "chat_live.json"

    existing = []

    if file.exists():

        existing = json.loads(file.read_text())

    existing.extend(messages)

    file.write_text(json.dumps(existing, indent=2))


def process_channel(channel):

    stream = get_live_stream(channel)

    if not stream:

        return

    vod_id = stream["video"]["uuid"]

    msgs = fetch_messages(channel)

    new_msgs = []

    for m in msgs:

        mid = m["id"]

        if mid in seen_ids:
            continue

        seen_ids.add(mid)

        new_msgs.append(m)

    if new_msgs:

        print(channel, "new messages:", len(new_msgs))

        save_messages(channel, vod_id, new_msgs)


def main():

    start = time.time()
    last_commit = start

    while True:

        for channel in CHANNELS:

            try:

                process_channel(channel)

            except Exception as e:

                print("Error:", e)

        now = time.time()

        if now - last_commit > COMMIT_INTERVAL:

            print("checkpoint commit")

            last_commit = now

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
