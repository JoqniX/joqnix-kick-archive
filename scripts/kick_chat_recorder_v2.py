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
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
)


seen_ids = set()
active_streams = {}
stream_start_times = {}
livestream_ids = {}
channel_ids = {}

offline_counter = {}
last_commit_time = 0


# ------------------------------------------------
# TIME
# ------------------------------------------------

def parse_time(ts):
    try:
        return int(datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp())
    except:
        return 0


# ------------------------------------------------
# SAFE JSON
# ------------------------------------------------

def safe_json(resp):

    try:
        return resp.json()
    except:
        print("[JSON ERROR]")
        return None


# ------------------------------------------------
# STATUS
# ------------------------------------------------

def load_status():

    if not STATUS_FILE.exists():
        return

    data = json.loads(STATUS_FILE.read_text())

    active_streams.update(data.get("active_streams", {}))
    stream_start_times.update(data.get("stream_start_times", {}))
    livestream_ids.update(data.get("livestream_ids", {}))
    channel_ids.update(data.get("channel_ids", {}))

    print("[STATUS] Loaded")


def save_status():

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    STATUS_FILE.write_text(json.dumps({
        "active_streams": active_streams,
        "stream_start_times": stream_start_times,
        "livestream_ids": livestream_ids,
        "channel_ids": channel_ids
    }, indent=2))


# ------------------------------------------------
# GIT
# ------------------------------------------------

def git_commit():

    global last_commit_time

    if time.time() - last_commit_time < 5:
        return

    print("[GIT] committing changes")

    try:

        subprocess.run("git add data", shell=True)

        subprocess.run(
            'git commit -m "Update live chat archive" || echo "No changes"',
            shell=True
        )

        subprocess.run("git pull --rebase origin Main-dayo", shell=True)

        subprocess.run("git push origin Main-dayo", shell=True)

        last_commit_time = time.time()

        print("[GIT] push successful")

    except Exception as e:

        print("[GIT ERROR]", e)


# ------------------------------------------------
# CHANNEL INFO
# ------------------------------------------------

def get_channel_info(channel):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}"

        print("[API] channel:", url)

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):
            return None

        cid = data.get("id")

        if cid:
            channel_ids[channel] = cid

        livestream = data.get("livestream")

        if livestream and livestream.get("is_live"):

            print("[CHANNEL LIVE]", channel)

            return {
                "channel_id": cid,
                "livestream_id": livestream["id"],
                "start_ts": parse_time(livestream["created_at"])
            }

        print("[CHANNEL OFFLINE]", channel)

    except Exception as e:

        print("[CHANNEL ERROR]", e)

    return None


# ------------------------------------------------
# VOD UUID
# ------------------------------------------------

def get_vod_uuid(channel, livestream_id):

    try:

        url = f"https://kick.com/api/v2/channels/{channel}/videos"

        print("[API] videos:", url)

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, list):
            return None

        for v in data:

            if not isinstance(v, dict):
                continue

            if v.get("id") == livestream_id:

                video = v.get("video")

                if video:
                    return video.get("uuid")

            video = v.get("video")

            if video and video.get("live_stream_id") == livestream_id:

                return video.get("uuid")

    except Exception as e:

        print("[VIDEO ERROR]", e)

    return None


# ------------------------------------------------
# MESSAGES
# ------------------------------------------------

def fetch_messages(channel):

    cid = channel_ids.get(channel)

    if not cid:
        print("[MESSAGES] Missing channel_id")
        return []

    url = f"https://kick.com/api/v2/channels/{cid}/messages"

    print("[API] messages:", url)

    try:

        r = session.get(url, timeout=10)

        data = safe_json(r)

        if not isinstance(data, dict):
            print("[MESSAGES ERROR] invalid response")
            return []

        # Case 1
        if isinstance(data.get("messages"), list):
            msgs = data["messages"]

        # Case 2
        elif isinstance(data.get("data"), list):
            msgs = data["data"]

        # Case 3
        elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("messages"), list):
            msgs = data["data"]["messages"]

        else:
            print("[MESSAGES ERROR] unknown format:", data)
            return []

        print("[MESSAGES] received:", len(msgs))

        return msgs

    except Exception as e:

        print("[MESSAGES ERROR]", e)

        return []


# ------------------------------------------------
# SAVE
# ------------------------------------------------

def save_messages(channel, vod_id, messages):

    folder = DATA_ROOT / channel / vod_id
    folder.mkdir(parents=True, exist_ok=True)

    file = folder / "chat_live.json"

    existing = []

    if file.exists():
        existing = json.loads(file.read_text())

    existing.extend(messages)

    file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    print("[SAVE]", len(messages), "messages")


# ------------------------------------------------
# FINALIZE
# ------------------------------------------------

def finalize_stream(channel, vod_id):

    print("[FINALIZE]", channel)

    src = DATA_ROOT / channel / vod_id / "chat_live.json"

    if not src.exists():
        return

    dst = ARCHIVE_ROOT / channel / vod_id
    dst.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, dst / "chat_raw.json")

    git_commit()


# ------------------------------------------------
# PROCESS
# ------------------------------------------------

def process_channel(channel):

    print("\n=== CHANNEL", channel, "===")

    stream = get_channel_info(channel)

    if stream:

        offline_counter[channel] = 0

        cid = stream["channel_id"]
        livestream_id = stream["livestream_id"]
        start_ts = stream["start_ts"]

        vod_id = get_vod_uuid(channel, livestream_id)

        if not vod_id:
            print("[WAIT] VOD mapping")
            return

        if channel not in active_streams:

            print("[STREAM START]")

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

            if msg_ts < stream_start_times[channel]:
                continue

            seen_ids.add(mid)
            new_msgs.append(m)

        print("[NEW MESSAGES]", len(new_msgs))

        if new_msgs:

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


# ------------------------------------------------
# MAIN
# ------------------------------------------------

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
