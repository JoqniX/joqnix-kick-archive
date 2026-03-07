import json
import requests
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
LIVE_ROOT = Path("data/live_chat")

USER_CACHE_FILE = Path("cache/kick_users.json")

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

EMOTE_BASE = "https://files.kick.com/emotes/"


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
# STREAM STATUS
# -------------------------------------------------

def is_channel_live(channel):

    try:

        url = f"{WORKER}/videos/{channel}"

        print("[STREAM CHECK]", url)

        r = requests.get(url, timeout=15)

        data = r.json()

        for v in data:

            if v.get("is_live"):

                print("[STREAM] LIVE:", channel)

                return True

        print("[STREAM] OFFLINE:", channel)

        return False

    except Exception as e:

        print("[STREAM ERROR]", e)

        return True  # fail-safe (avoid normalizing while unsure)


# -------------------------------------------------
# FETCH AVATAR
# -------------------------------------------------

def fetch_avatar(channel):

    try:

        url = f"{WORKER}/channel/{channel}"

        print("[AVATAR FETCH]", url)

        r = requests.get(url, timeout=15)

        data = r.json()

        avatar = data.get("user", {}).get("profile_pic")

        if avatar:

            print("[AVATAR FOUND]", avatar)

        else:

            print("[AVATAR MISSING]", channel)

        return avatar

    except Exception as e:

        print("[AVATAR ERROR]", e)

        return None


# -------------------------------------------------
# MESSAGE PARSER
# -------------------------------------------------

def parse_message(content):

    parts = []

    if not content:
        return parts

    tokens = content.split(" ")

    for t in tokens:

        if t.startswith("[emote:"):

            try:

                emote_id = t.split(":")[1].split("]")[0]

                parts.append({

                    "type": "emote",
                    "name": emote_id,
                    "url": f"{EMOTE_BASE}{emote_id}/fullsize"

                })

            except:

                parts.append({
                    "type": "text",
                    "text": t
                })

        else:

            parts.append({
                "type": "text",
                "text": t
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

    for msg in raw:

        sender = msg.get("sender", {})

        uid = str(sender.get("id"))

        username = sender.get("username")

        avatar = None

        # --------------------------
        # USER CACHE
        # --------------------------

        if uid in users:

            avatar = users[uid].get("avatar")

            print("[CACHE HIT]", username)

        else:

            print("[CACHE MISS]", username)

            avatar = fetch_avatar(username)

            users[uid] = {

                "username": username,
                "avatar": avatar

            }

        # --------------------------
        # MESSAGE PARTS
        # --------------------------

        message_parts = parse_message(msg.get("content", ""))

        # --------------------------
        # NORMALIZED ENTRY
        # --------------------------

        normalized.append({

            "id": msg.get("id"),

            "timestamp": msg.get("created_at"),

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

        # check if live

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
