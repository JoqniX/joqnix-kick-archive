import json
import time
import requests
import subprocess
from pathlib import Path
import shutil
from datetime import datetime

CHANNELS = [
    "joqnix247", "joqnix"
]

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

DATA_ROOT = Path("data/live_chat")
ARCHIVE_ROOT = Path("data/kick_archive")

STATUS_FILE = Path("data/live_chat/status.json")

LIVE_POLL_INTERVAL = 2
OFFLINE_POLL_INTERVAL = 30

STREAM_CHECK_INTERVAL = 30
COMMIT_INTERVAL = 180
OFFLINE_THRESHOLD = 3

seen_ids = set()
active_streams = {}
stream_start_times = {}
livestream_ids = {}

last_stream_check = {}
offline_counter = {}

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
# STATUS
# -----------------------------

def load_status():

    global active_streams
    global stream_start_times
    global livestream_ids

    if not STATUS_FILE.exists():
        return

    try:

        data = json.loads(STATUS_FILE.read_text())

        active_streams.update(data.get("active_streams", {}))
        stream_start_times.update(data.get("stream_start_times", {}))
        livestream_ids.update(data.get("livestream_ids", {}))

        print("Recovered status:", active_streams, flush=True)

    except Exception as e:
        print("Failed loading status:", e)


def save_status():

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    STATUS_FILE.write_text(json.dumps({
        "active_streams": active_streams,
        "stream_start_times": stream_start_times,
        "livestream_ids": livestream_ids
    }, indent=2))


# -----------------------------
# GIT
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

        subprocess.run("git pull --rebase", shell=True)
        subprocess.run("git push", shell=True)

        last_commit_time = now

        print("Commit successful", flush=True)

    except Exception as e:

        print("Commit failed:", e)


# -----------------------------
# RECOVERY
# -----------------------------

def rebuild_seen_ids(channel, vod_id):

    file = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not file.exists():
        return

    try:

        data = json.loads(file.read_text())

        for m in data:
            seen_ids.add(m["id"])

        print("Recovered", len(data), "messages")

    except:
        pass


# -----------------------------
# API
# -----------------------------

def get_channel_livestream(channel):

    try:

        url = f"{WORKER}/channel/{channel}"

        r = requests.get(url, timeout=10)

        data = r.json()

        livestream = data.get("livestream")

        if livestream and livestream.get("is_live"):

            print("[CHANNEL] LIVE", channel)

            return {
                "livestream_id": livestream["id"],
                "start_ts": parse_time(livestream["created_at"])
            }

        print("[CHANNEL] OFFLINE", channel)

    except Exception as e:

        print("Channel API error:", e)

    return None


def get_vod_uuid(channel, livestream_id):

    try:

        url = f"{WORKER}/videos/{channel}"

        r = requests.get(url, timeout=10)

        data = r.json()

        for v in data:

            if v.get("id") == livestream_id:

                vod = v.get("video")

                if vod:
                    return vod.get("uuid")

            if v.get("video"):

                if v["video"].get("live_stream_id") == livestream_id:
                    return v["video"].get("uuid")

    except Exception as e:

        print("Video API error:", e)

    return None


def fetch_messages(channel):

    try:

        url = f"{WORKER}/messages-live/{channel}"

        r = requests.get(url, timeout=10)

        return r.json().get("messages", [])

    except:
        return []


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
# FINALIZE
# -----------------------------

def finalize_stream(channel, vod_id):

    print("Stream ended:", channel)

    src = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not src.exists():
        return

    dst_folder = ARCHIVE_ROOT / channel / vod_id
    dst_folder.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, dst_folder / "chat_raw.json")

    print("Archived chat:", vod_id)

    git_commit()


# -----------------------------
# PROCESS
# -----------------------------

def process_channel(channel):

    now = time.time()

    stream = get_channel_livestream(channel)

    # ---------------- LIVE ----------------

    if stream:

        offline_counter[channel] = 0

        livestream_id = stream["livestream_id"]
        start_ts = stream["start_ts"]

        vod_id = get_vod_uuid(channel, livestream_id)

        if not vod_id:

            print("Waiting for VOD mapping...")
            return

        if channel not in active_streams:

            print("Stream detected:", channel)
            print("Tracking VOD:", vod_id)

            active_streams[channel] = vod_id
            livestream_ids[channel] = livestream_id
            stream_start_times[channel] = start_ts

            save_status()

            rebuild_seen_ids(channel, vod_id)

        elif livestream_ids.get(channel) != livestream_id:

            print("Livestream rotated → new session")

            finalize_stream(channel, active_streams[channel])

            active_streams[channel] = vod_id
            livestream_ids[channel] = livestream_id
            stream_start_times[channel] = start_ts

            seen_ids.clear()

            save_status()

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

            print("+", len(new_msgs), "messages")

            save_messages(channel, vod_id, new_msgs)

            git_commit()

    # ---------------- OFFLINE ----------------

    else:

        if channel not in active_streams:
            return

        offline_counter[channel] = offline_counter.get(channel, 0) + 1

        print("Offline check:", offline_counter[channel])

        if offline_counter[channel] < OFFLINE_THRESHOLD:
            return

        vod_id = active_streams[channel]

        finalize_stream(channel, vod_id)

        del active_streams[channel]
        del livestream_ids[channel]
        del stream_start_times[channel]

        offline_counter[channel] = 0

        save_status()


# -----------------------------
# SAFETY COMMIT
# -----------------------------

def safety_commit_loop():

    global last_commit_time

    if time.time() - last_commit_time > COMMIT_INTERVAL:

        print("Safety commit triggered")

        git_commit()


# -----------------------------
# MAIN
# -----------------------------

def main():

    print("Kick Chat Recorder Started")

    load_status()

    while True:

        any_live = False

        for channel in CHANNELS:

            try:

                process_channel(channel)

                if channel in active_streams:
                    any_live = True

            except Exception as e:

                print("Recorder error:", e)

        safety_commit_loop()

        time.sleep(LIVE_POLL_INTERVAL if any_live else OFFLINE_POLL_INTERVAL)


if __name__ == "__main__":
    main()
