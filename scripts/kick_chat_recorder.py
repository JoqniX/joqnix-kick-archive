import json
import time
import requests
import subprocess
from pathlib import Path
import shutil
from datetime import datetime

CHANNELS = [
    "joqnix247"
]

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

DATA_ROOT = Path("data/live_chat")
ARCHIVE_ROOT = Path("data/kick_archive")

STATUS_FILE = Path("data/live_chat/status.json")

LIVE_POLL_INTERVAL = 2
OFFLINE_POLL_INTERVAL = 30

STREAM_CHECK_INTERVAL = 30
COMMIT_INTERVAL = 180


seen_ids = set()
active_streams = {}
stream_start_times = {}
last_stream_check = {}
last_commit_time = 0


# -----------------------------
# TIME PARSER
# -----------------------------

def parse_time(ts):

    try:
        return int(datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp())
    except:
        return 0


# -----------------------------
# STATUS PERSISTENCE
# -----------------------------

def load_status():

    global active_streams
    global stream_start_times

    if not STATUS_FILE.exists():
        return

    try:

        data = json.loads(STATUS_FILE.read_text())

        active_streams.update(data.get("active_streams", {}))
        stream_start_times.update(data.get("stream_start_times", {}))

        print("Recovered status:", active_streams, flush=True)

    except Exception as e:

        print("Failed loading status:", e, flush=True)


def save_status():

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "active_streams": active_streams,
        "stream_start_times": stream_start_times
    }

    STATUS_FILE.write_text(json.dumps(data, indent=2))


# -----------------------------
# GIT COMMIT
# -----------------------------

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


# -----------------------------
# RECOVERY
# -----------------------------

def rebuild_seen_ids(channel, vod_id):

    folder = DATA_ROOT / channel / vod_id
    file = folder / "chat_live.json"

    if not file.exists():
        return

    try:

        data = json.loads(file.read_text())

        for m in data:
            seen_ids.add(m["id"])

        print("Recovered", len(data), "messages", flush=True)

    except:
        pass


# -----------------------------
# API
# -----------------------------

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

            start_ts = parse_time(v.get("created_at"))

            return {
                "vod_id": v["video"]["uuid"],
                "start_ts": start_ts
            }

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


# -----------------------------
# CHAT STORAGE
# -----------------------------

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


# -----------------------------
# STREAM FINALIZE
# -----------------------------

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


# -----------------------------
# PROCESS CHANNEL
# -----------------------------

def process_channel(channel):

    now = time.time()

    stream = None

    if channel not in active_streams:

        stream = get_live_stream(channel)

    else:

        if now - last_stream_check.get(channel, 0) > STREAM_CHECK_INTERVAL:

            stream = get_live_stream(channel)

            last_stream_check[channel] = now


    # ---------------------
    # STREAM START
    # ---------------------

    if stream:

        vod_id = stream["vod_id"]
        start_ts = stream["start_ts"]

        if channel not in active_streams:

            print("\nStream detected:", channel, flush=True)
            print("Tracking VOD:", vod_id, flush=True)

            active_streams[channel] = vod_id
            stream_start_times[channel] = start_ts

            save_status()

            rebuild_seen_ids(channel, vod_id)

        msgs = fetch_messages(channel)

        new_msgs = []

        for m in msgs:

            mid = m["id"]

            if mid in seen_ids:
                continue

            msg_ts = parse_time(m.get("created_at"))

            if msg_ts < stream_start_times.get(channel, 0):
                continue

            seen_ids.add(mid)
            new_msgs.append(m)

        if new_msgs:

            print("+", len(new_msgs), "messages", flush=True)

            save_messages(channel, vod_id, new_msgs)

            git_commit()


    # ---------------------
    # STREAM END
    # ---------------------

    else:

        if channel in active_streams:

            vod_id = active_streams[channel]

            finalize_stream(channel, vod_id)

            del active_streams[channel]

            if channel in stream_start_times:
                del stream_start_times[channel]

            save_status()


# -----------------------------
# SAFETY COMMIT
# -----------------------------

def safety_commit_loop():

    global last_commit_time

    if time.time() - last_commit_time > COMMIT_INTERVAL:

        print("Safety commit triggered", flush=True)

        git_commit()


# -----------------------------
# MAIN
# -----------------------------

def main():

    print("Kick Chat Recorder Started", flush=True)

    load_status()

    while True:

        any_live = False

        for channel in CHANNELS:

            try:

                process_channel(channel)

                if channel in active_streams:
                    any_live = True

            except Exception as e:

                print("Recorder error:", e, flush=True)

        safety_commit_loop()

        if any_live:
            time.sleep(LIVE_POLL_INTERVAL)
        else:
            time.sleep(OFFLINE_POLL_INTERVAL)


if __name__ == "__main__":
    main()
