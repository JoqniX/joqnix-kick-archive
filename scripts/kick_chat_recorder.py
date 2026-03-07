import json
import time
import requests
from pathlib import Path
import shutil

CHANNELS = [
    "joqnix247"
]

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

DATA_ROOT = Path("data/live_chat")
ARCHIVE_ROOT = Path("data/kick_archive")

POLL_INTERVAL = 2

# track seen messages
seen_ids = set()

# track active streams
active_streams = {}


def get_live_stream(channel):

    url = f"{WORKER}/videos/{channel}"

    print("Checking streams:", url, flush=True)

    r = requests.get(url)

    try:
        data = r.json()
    except:
        print("Invalid response:", r.text, flush=True)
        return None

    for v in data:

        if v.get("is_live"):
            print("LIVE STREAM FOUND:", channel, flush=True)
            return v

    return None


def fetch_messages(channel):

    url = f"{WORKER}/messages/{channel}"

    r = requests.get(url)

    try:
        data = r.json()
    except:
        print("Invalid message response:", r.text, flush=True)
        return []

    msgs = data.get("messages", [])

    print("Messages returned:", len(msgs), flush=True)

    return msgs


def save_messages(channel, vod_id, messages):

    folder = DATA_ROOT / channel / vod_id
    folder.mkdir(parents=True, exist_ok=True)

    file = folder / "chat_live.json"

    existing = []

    if file.exists():

        try:
            existing = json.loads(file.read_text())
        except:
            existing = []

    existing.extend(messages)

    file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    print("Saved messages:", len(messages), flush=True)


def finalize_stream(channel, vod_id):

    print("Stream ended, finalizing:", channel, vod_id, flush=True)

    src = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not src.exists():
        print("No chat file found to finalize", flush=True)
        return

    dst_folder = ARCHIVE_ROOT / channel / vod_id
    dst_folder.mkdir(parents=True, exist_ok=True)

    dst = dst_folder / "chat_raw.json"

    shutil.copy(src, dst)

    print("Chat copied to archive:", dst, flush=True)


def process_channel(channel):

    print("\nProcessing channel:", channel, flush=True)

    stream = get_live_stream(channel)

    # STREAM START
    if stream:

        vod_id = stream["video"]["uuid"]

        if channel not in active_streams:
            print("Tracking new stream:", vod_id, flush=True)
            active_streams[channel] = vod_id

        msgs = fetch_messages(channel)

        new_msgs = []

        for m in msgs:

            mid = m["id"]

            if mid in seen_ids:
                continue

            seen_ids.add(mid)

            new_msgs.append(m)

        if new_msgs:

            print("New messages detected:", len(new_msgs), flush=True)

            save_messages(channel, vod_id, new_msgs)

    # STREAM END
    else:

        if channel in active_streams:

            vod_id = active_streams[channel]

            finalize_stream(channel, vod_id)

            del active_streams[channel]


def main():

    print("Kick Chat Recorder Started", flush=True)

    while True:

        for channel in CHANNELS:

            try:

                process_channel(channel)

            except Exception as e:

                print("Error:", e, flush=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
