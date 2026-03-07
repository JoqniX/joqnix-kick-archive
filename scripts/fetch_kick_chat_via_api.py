import json
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ARCHIVE_ROOT = Path("data/kick_archive")

WORKER = "https://kick-proxy.onaixia.workers.dev/api/messages"

STEP = 30000      # 30 seconds window
THREADS = 8       # parallel workers


def fetch_window(channel, start, end):

    url = f"{WORKER}/{channel}?start={start}&end={end}"

    print("Fetching:", url)

    try:
        r = requests.get(url, timeout=20)
        data = r.json()
        return data.get("messages", [])
    except Exception as e:
        print("Fetch failed:", e)
        return []


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

    print("\nProcessing VOD:", vod_dir.name)
    print("Start:", start)
    print("End:", end)

    windows = []

    t = start

    while t < end:
        windows.append((channel, t, t + STEP))
        t += STEP

    messages = []

    with ThreadPoolExecutor(max_workers=THREADS) as exe:

        results = exe.map(lambda w: fetch_window(*w), windows)

        for r in results:
            messages.extend(r)

    # remove duplicates
    unique = {}
    for m in messages:
        unique[m["id"]] = m

    messages = list(unique.values())

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
