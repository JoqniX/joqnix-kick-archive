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


session = requests.Session(
    impersonate="chrome110",
    headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
)


seen_ids = set()
active_streams = {}
stream_start_times = {}
livestream_ids = {}

offline_counter = {}

last_commit_time = 0


# -----------------------------
# TIME
# -----------------------------

def parse_time(ts):

    try:
        return int(datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp())
    except:
        return 0


# -----------------------------
# SAFE JSON
# -----------------------------

def safe_json(resp):

    try:
        return resp.json()
    except:
        print("[JSON ERROR] Could not decode response")
        return None


# -----------------------------
# STATUS
# -----------------------------

def load_status():

    if not STATUS_FILE.exists():
        print("[STATUS] No previous status file")
        return

    try:

        data = json.loads(STATUS_FILE.read_text())

        active_streams.update(data.get("active_streams", {}))
        stream_start_times.update(data.get("stream_start_times", {}))
        livestream_ids.update(data.get("livestream_ids", {}))

        print("[STATUS] Recovered:", active_streams)

    except Exception as e:
        print("[STATUS ERROR]", e)


def save_status():

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    STATUS_FILE.write_text(json.dumps({
        "active_streams": active_streams,
        "stream_start_times": stream_start_times,
        "livestream_ids": livestream_ids
    }, indent=2))

    print("[STATUS] Saved")


# -----------------------------
# GIT
# -----------------------------

def git_commit():

    global last_commit_time

    now = time.time()

    if now - last_commit_time < 5:
        return

    print("[GIT] Attempting commit")

    try:

        subprocess.run("git pull --rebase", shell=True)

        subprocess.run("git add data", shell=True)

        subprocess.run(
            'git commit -m "Update live chat archive" || echo "No changes"',
            shell=True
        )

        subprocess.run("git push", shell=True)

        last_commit_time = now

        print("[GIT] Commit successful")

    except Exception as e:

        print("[GIT ERROR]", e)


# -----------------------------
# CHANNEL STATUS
# -----------------------------

def get_channel_livestream(channel):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}"

        print("[API] Fetch channel:", url)

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):
            print("[CHANNEL ERROR] Invalid response")
            return None

        livestream = data.get("livestream")

        if livestream and livestream.get("is_live"):

            print("[CHANNEL] LIVE", channel)

            return {
                "livestream_id": livestream["id"],
                "start_ts": parse_time(livestream["created_at"])
            }

        print("[CHANNEL] OFFLINE", channel)

    except Exception as e:

        print("[CHANNEL API ERROR]", e)

    return None


# -----------------------------
# VOD UUID
# -----------------------------

def get_vod_uuid(channel, livestream_id):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}/videos"

        print("[API] Fetch videos:", url)

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, list):

            print("[VIDEO ERROR] Not a list")

            return None

        for v in data:

            if not isinstance(v, dict):
                continue

            if v.get("id") == livestream_id:

                video = v.get("video")

                if video:

                    uuid = video.get("uuid")

                    print("[VIDEO] Found VOD UUID:", uuid)

                    return uuid

            video = v.get("video")

            if video and video.get("live_stream_id") == livestream_id:

                uuid = video.get("uuid")

                print("[VIDEO] Found VOD UUID:", uuid)

                return uuid

        print("[VIDEO] VOD mapping not found yet")

    except Exception as e:

        print("[VIDEO API ERROR]", e)

    return None


# -----------------------------
# FETCH MESSAGES
# -----------------------------

def fetch_messages(channel):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}/messages"

        print("[API] Fetch messages:", url)

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):

            print("[MESSAGES ERROR] Response not dict")

            return []

        msgs = data.get("data") or data.get("messages")

        if not isinstance(msgs, list):

            print("[MESSAGES ERROR] Not list")

            return []

        print("[MESSAGES] Received:", len(msgs))

        return msgs

    except Exception as e:

        print("[MESSAGES ERROR]", e)

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
            pass

    existing.extend(messages)

    file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    print("[SAVE] Wrote", len(messages), "messages")


# -----------------------------
# FINALIZE
# -----------------------------

def finalize_stream(channel, vod_id):

    print("[FINALIZE] Stream ended:", channel)

    src = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not src.exists():

        print("[FINALIZE] No chat file")

        return

    dst_folder = ARCHIVE_ROOT / channel / vod_id

    dst_folder.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, dst_folder / "chat_raw.json")

    print("[FINALIZE] Archived:", vod_id)

    git_commit()


# -----------------------------
# PROCESS CHANNEL
# -----------------------------

def process_channel(channel):

    print("\n=== PROCESS CHANNEL:", channel, "===")

    stream = get_channel_livestream(channel)

    if stream:

        offline_counter[channel] = 0

        livestream_id = stream["livestream_id"]
        start_ts = stream["start_ts"]

        print("[STREAM] livestream_id:", livestream_id)

        vod_id = get_vod_uuid(channel, livestream_id)

        if not vod_id:

            print("[STREAM] Waiting for VOD mapping")

            return

        if channel not in active_streams:

            print("[STREAM] New stream detected")

            active_streams[channel] = vod_id
            livestream_ids[channel] = livestream_id
            stream_start_times[channel] = start_ts

            save_status()

        msgs = fetch_messages(channel)

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

        print("[FILTER] New messages:", len(new_msgs))

        if new_msgs:

            save_messages(channel, vod_id, new_msgs)

            git_commit()

    else:

        if channel not in active_streams:
            return

        offline_counter[channel] = offline_counter.get(channel, 0) + 1

        print("[OFFLINE CHECK]", offline_counter[channel])

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

                print("[PROCESS ERROR]", e)

        time.sleep(LIVE_POLL_INTERVAL if any_live else OFFLINE_POLL_INTERVAL)


if __name__ == "__main__":
    main()
