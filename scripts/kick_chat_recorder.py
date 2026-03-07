import json
import time
import requests
import subprocess
from pathlib import Path
import shutil

CHANNELS = [
    "joqnix247"
]

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

DATA_ROOT = Path("data/live_chat")
ARCHIVE_ROOT = Path("data/kick_archive")

POLL_INTERVAL = 2
COMMIT_INTERVAL = 180  # seconds safety commit

seen_ids = set()
active_streams = {}

last_commit_time = 0


def git_commit():

    global last_commit_time

    now = time.time()

    if now - last_commit_time < 5:
        return

    try:

        subprocess.run("git add data", shell=True)

        subprocess.run(
            'git commit -m "Update live chat archive" || echo "No changes"',
            shell=True
        )

        subprocess.run("git push", shell=True)

        last_commit_time = now

        print("Commit successful", flush=True)

    except Exception as e:

        print("Commit failed:", e, flush=True)


def rebuild_seen_ids(channel, vod_id):

    folder = DATA_ROOT / channel / vod_id
    file = folder / "chat_live.json"

    if not file.exists():
        return

    try:

        data = json.loads(file.read_text())

        for m in data:
            seen_ids.add(m["id"])

        print("Recovered", len(data), "existing messages", flush=True)

    except:
        pass


def get_live_stream(channel):

    url = f"{WORKER}/videos/{channel}"

    r = requests.get(url)

    try:
        data = r.json()
    except:
        print("Invalid stream response", flush=True)
        return None

    for v in data:

        if v.get("is_live"):
            return v

    return None


def fetch_messages(channel):

    url = f"{WORKER}/messages-live/{channel}"

    r = requests.get(url)

    try:
        data = r.json()
    except:
        print("Invalid message response", flush=True)
        return []

    return data.get("messages", [])


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


def finalize_stream(channel, vod_id):

    print("Stream ended:", channel, flush=True)

    src = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not src.exists():
        return

    dst_folder = ARCHIVE_ROOT / channel / vod_id
    dst_folder.mkdir(parents=True, exist_ok=True)

    dst = dst_folder / "chat_raw.json"

    shutil.copy(src, dst)

    print("Archived chat:", dst, flush=True)

    git_commit()


def process_channel(channel):

    stream = get_live_stream(channel)

    if stream:

        vod_id = stream["video"]["uuid"]

        if channel not in active_streams:

            print("\nStream detected:", channel, flush=True)
            print("Tracking VOD:", vod_id, flush=True)

            active_streams[channel] = vod_id

            rebuild_seen_ids(channel, vod_id)

        msgs = fetch_messages(channel)

        new_msgs = []

        for m in msgs:

            mid = m["id"]

            if mid in seen_ids:
                continue

            seen_ids.add(mid)

            new_msgs.append(m)

        if new_msgs:

            print("+", len(new_msgs), "messages", flush=True)

            save_messages(channel, vod_id, new_msgs)

            git_commit()

    else:

        if channel in active_streams:

            vod_id = active_streams[channel]

            finalize_stream(channel, vod_id)

            del active_streams[channel]


def safety_commit_loop():

    global last_commit_time

    if time.time() - last_commit_time > COMMIT_INTERVAL:

        print("Safety commit triggered", flush=True)

        git_commit()


def main():

    print("Kick Chat Recorder Started", flush=True)

    while True:

        for channel in CHANNELS:

            try:

                process_channel(channel)

            except Exception as e:

                print("Recorder error:", e, flush=True)

        safety_commit_loop()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
