import json
import requests
import re
import time
from pathlib import Path
from datetime import datetime

ARCHIVE_ROOT = Path("data/kick_archive")
LIVE_ROOT = Path("data/live_chat")

USER_CACHE_FILE = Path("cache/kick_users.json")

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

EMOTE_BASE = "https://files.kick.com/emotes/"

CACHE_REFRESH_SECONDS = 60 * 60 * 24 * 7


# -------------------------------------------------
# USER CACHE
# -------------------------------------------------

def load_user_cache():

    if USER_CACHE_FILE.exists():

        try:
            return json.loads(USER_CACHE_FILE.read_text())
        except:
            return {}

    return {}


def save_user_cache(users):

    USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    USER_CACHE_FILE.write_text(
        json.dumps(users, indent=2, ensure_ascii=False)
    )


# -------------------------------------------------
# USERNAME SLUG NORMALIZATION
# -------------------------------------------------

def normalize_slug(username):

    if not username:
        return username

    return username.lower().replace("_", "-")


# -------------------------------------------------
# STREAM STATUS
# -------------------------------------------------

def is_channel_live(channel):

    try:

        url = f"{WORKER}/videos/{channel}"

        print("[STREAM CHECK]", url)

        r = requests.get(url, timeout=15)

        data = r.json()

        if not isinstance(data, list):
            return True

        for v in data:

            if isinstance(v, dict) and v.get("is_live"):

                print("[STREAM] LIVE:", channel)

                return True

        print("[STREAM] OFFLINE:", channel)

        return False

    except Exception as e:

        print("[STREAM ERROR]", e)

        return True


# -------------------------------------------------
# FETCH AVATAR
# -------------------------------------------------

def fetch_avatar(username):

    try:

        slug = normalize_slug(username)

        url = f"{WORKER}/channel/{slug}"

        print("[AVATAR FETCH]", url)

        r = requests.get(url, timeout=15)

        data = r.json()

        avatar = data.get("user", {}).get("profile_pic")

        if avatar:
            print("[AVATAR FOUND]", avatar)

        return avatar

    except Exception as e:

        print("[AVATAR ERROR]", e)

        return None


# -------------------------------------------------
# VOD OFFSET
# -------------------------------------------------

def compute_vod_offset(stream_start, message_time):

    try:

        start = datetime.fromisoformat(stream_start.replace("Z", "+00:00"))
        msg = datetime.fromisoformat(message_time.replace("Z", "+00:00"))

        diff = int((msg - start).total_seconds())

        if diff < 0:
            diff = 0

        return diff

    except:
        return None


def format_vod_timestamp(seconds):

    if seconds is None:
        return None

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    return f"{h:02}:{m:02}:{s:02}"


# -------------------------------------------------
# MESSAGE PARSER (FIXED)
# -------------------------------------------------

EMOTE_PATTERN = re.compile(r"\[emote:(\d+)\]")


def parse_message(content):

    parts = []

    if not content:
        return parts

    last = 0

    for match in EMOTE_PATTERN.finditer(content):

        start, end = match.span()

        emote_id = match.group(1)

        if start > last:

            parts.append({
                "type": "text",
                "text": content[last:start]
            })

        parts.append({
            "type": "emote",
            "name": emote_id,
            "url": f"{EMOTE_BASE}{emote_id}/fullsize"
        })

        last = end

    if last < len(content):

        parts.append({
            "type": "text",
            "text": content[last:]
        })

    return parts


# -------------------------------------------------
# BADGE NORMALIZATION
# -------------------------------------------------

def normalize_badges(badges):

    result = []

    for b in badges:

        result.append({
            "type": b.get("type"),
            "text": b.get("text")
        })

    return result


# -------------------------------------------------
# CHAT NORMALIZER
# -------------------------------------------------

def normalize_chat(chat_file, channel):

    normalized_file = chat_file.parent / "chat_normalized.json"

    if normalized_file.exists():

        print("[SKIP] already normalized:", normalized_file)

        return

    print("[NORMALIZE]", chat_file)

    raw = json.loads(chat_file.read_text())

    users = load_user_cache()

    normalized = []

    stream_start = raw[0].get("created_at") if raw else None

    for msg in raw:

        sender = msg.get("sender", {})

        uid = str(sender.get("id"))

        username = sender.get("username")

        avatar = None

        # --------------------------
        # CACHE LOGIC
        # --------------------------

        cache = users.get(uid)

        if cache:

            avatar = cache.get("avatar")

            checked = cache.get("checked_at", 0)

            if time.time() - checked > CACHE_REFRESH_SECONDS:

                avatar = fetch_avatar(username)

                users[uid]["avatar"] = avatar
                users[uid]["checked_at"] = time.time()

        else:

            avatar = fetch_avatar(username)

            users[uid] = {
                "username": username,
                "avatar": avatar,
                "checked_at": time.time()
            }

        # --------------------------
        # MESSAGE
        # --------------------------

        message_parts = parse_message(msg.get("content", ""))

        # --------------------------
        # VOD TIMESTAMP
        # --------------------------

        msg_time = msg.get("created_at")

        offset = compute_vod_offset(stream_start, msg_time)

        vod_timestamp = format_vod_timestamp(offset)

        # --------------------------
        # OUTPUT
        # --------------------------

        normalized.append({

            "id": msg.get("id"),

            "timestamp": msg_time,

            "vod_offset": offset,
            "vod_timestamp": vod_timestamp,

            "user": {

                "id": sender.get("id"),
                "username": username,
                "avatar": avatar,
                "color": sender.get("identity", {}).get("color"),
                "badges": normalize_badges(
                    sender.get("identity", {}).get("badges", [])
                )

            },

            "message": message_parts,

            "type": msg.get("type")

        })

    normalized_file.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False)
    )

    save_user_cache(users)

    print("[NORMALIZED]", normalized_file)


# -------------------------------------------------
# SCAN FOLDER
# -------------------------------------------------

def scan_folder(root):

    if not root.exists():
        return

    for channel in root.iterdir():

        if not channel.is_dir():
            continue

        channel_name = channel.name

        print("\n[CHANNEL]", channel_name)

        if is_channel_live(channel_name):

            print("[SKIP LIVE CHANNEL]", channel_name)

            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            raw_archive = vod / "chat_raw.json"
            raw_live = vod / "chat_live.json"

            if raw_archive.exists():

                normalize_chat(raw_archive, channel_name)

            elif raw_live.exists():

                normalize_chat(raw_live, channel_name)


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():

    print("Kick Chat Normalizer Started")

    print("\nScanning archive folder")

    scan_folder(ARCHIVE_ROOT)

    print("\nScanning live chat folder")

    scan_folder(LIVE_ROOT)


if __name__ == "__main__":
    main()
