import json
import requests
import time
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")

WORKER = "https://kick-proxy.onaixia.workers.dev/api/kick/chat"

STEP = 10000  # 10 seconds


def fetch_window(channel, start, end):

    url = f"{WORKER}?channel={channel}&start={start}&end={end}"

    print("Fetching:", url)

    r = requests.get(url)

    data = r.json()

    return data.get("messages", [])


def process_vod(vod_dir):

    meta_file = vod_dir / "metadata.json"

    if not meta_file.exists():
        return

    raw_file = vod_dir / "chat_raw.json"

    if raw_file.exists():
        print("Chat already downloaded:", vod_dir.name)
        return

    meta = json.loads(meta_file.read_text())

    channel = meta["channel"]

    start = meta["timestamp"] * 1000
    end = start + (meta["duration_seconds"] * 1000)

    messages = []

    t = start

    while t < end:

        window_end = t + STEP

        msgs = fetch_window(channel, t, window_end)

        messages.extend(msgs)

        t += STEP

        time.sleep(0.2)

    print("Total messages:", len(messages))

    raw_file.write_text(
        json.dumps(messages, indent=2, ensure_ascii=False)
    )


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
