import json
import time
import subprocess
from pathlib import Path
import shutil
from datetime import datetime
from curl_cffi import requests


CHANNELS = [
    "joqnix247",
    "joqnix"
]


DATA_ROOT = Path("data/live_chat")
ARCHIVE_ROOT = Path("data/kick_archive")

STATUS_FILE = Path("data/live_chat/status.json")


LIVE_POLL_INTERVAL = 5
OFFLINE_POLL_INTERVAL = 60

COMMIT_INTERVAL = 180
OFFLINE_THRESHOLD = 3


session = requests.Session(impersonate="chrome110")


seen_ids = set()
active_streams = {}
stream_start_times = {}
livestream_ids = {}

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

        subprocess.run("git pull --rebase", shell=True)

        subprocess.run("git add data", shell=True)

        subprocess.run(
            'git commit -m "Update live chat archive" || echo "No changes"',
            shell=True
        )

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
# SAFE JSON
# -----------------------------

def safe_json(resp):

    try:
        return resp.json()
    except:
        return None


# -----------------------------
# CHANNEL STATUS
# -----------------------------

def get_channel_livestream(channel):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}"

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):
            return None

        livestream = data.get("livestream")

        if isinstance(livestream, dict) and livestream.get("is_live"):

            print("[CHANNEL] LIVE", channel)

            return {
                "livestream_id": livestream.get("id"),
                "start_ts": parse_time(livestream.get("created_at"))
            }

        print("[CHANNEL] OFFLINE", channel)

    except Exception as e:

        print("Channel API error:", e)

    return None


# -----------------------------
# VOD UUID RESOLUTION
# -----------------------------

def get_vod_uuid(channel, livestream_id):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}/videos"

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, list):
            return None

        for v in data:

            if not isinstance(v, dict):
                continue

            if v.get("id") == livestream_id:

                video = v.get("video")

                if isinstance(video, dict):
                    return video.get("uuid")

            video = v.get("video")

            if isinstance(video, dict):

                if video.get("live_stream_id") == livestream_id:
                    return video.get("uuid")

    except Exception as e:

        print("Video API error:", e)

    return None


# -----------------------------
# FETCH MESSAGES
# -----------------------------

def fetch_messages(channel_id):

    try:

        url = f"https://kick.com/api/v2/channels/{channel_id}/messages"

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):
            return []

        msgs = data.get("data")

        if not isinstance(msgs, list):
            return []

        return msgs

    except Exception as e:

        print("Message API error:", e)

        return []


# -----------------------------
# SAVE CHAT
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
# FINALIZE STREAM
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
# PROCESS CHANNEL
# -----------------------------

def process_channel(channel):

    stream = get_channel_livestream(channel)

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

            active_streams[channel] = vod_id
            livestream_ids[channel] = livestream_id
            stream_start_times[channel] = start_ts

            save_status()

            rebuild_seen_ids(channel, vod_id)

        msgs = fetch_messages(livestream_id)

        new_msgs = []

        for m in msgs:

            mid = m.get("id")

            if not mid:
                continue

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

    else:

        if channel not in active_streams:
            return

        offline_counter[channel] = offline_counter.get(channel, 0) + 1

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
# MAIN LOOP
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

        time.sleep(LIVE_POLL_INTERVAL if any_live else OFFLINE_POLL_INTERVAL)


if __name__ == "__main__":
    main()
