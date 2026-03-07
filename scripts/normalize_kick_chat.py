import json
import requests
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
LIVE_ROOT = Path("data/live_chat")

USER_CACHE_FILE = Path("cache/kick_users.json")

EMOTE_BASE = "https://files.kick.com/emotes/"
CHANNEL_API = "https://kick.com/api/v2/channels/"


# -----------------------------
# USER CACHE
# -----------------------------

def load_user_cache():

    if USER_CACHE_FILE.exists():
        return json.loads(USER_CACHE_FILE.read_text())

    return {}


def save_user_cache(users):

    USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    USER_CACHE_FILE.write_text(
        json.dumps(users, indent=2, ensure_ascii=False)
    )


# -----------------------------
# FETCH AVATAR
# -----------------------------

def fetch_avatar(username):

    try:

        r = requests.get(
            f"{CHANNEL_API}{username}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            },
            timeout=10
        )

        data = r.json()

        return data["user"]["profile_pic"]

    except:

        return None


# -----------------------------
# MESSAGE PARSER
# -----------------------------

def parse_message(content):

    parts = []

    tokens = content.split()

    for t in tokens:

        if t.startswith("[emote:"):

            try:

                emote_id = t.split(":")[1].split("]")[0]

                parts.append({
                    "type": "emote",
                    "name": emote_id,
                    "url": f"{EMOTE_BASE}{emote_id}.png"
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


# -----------------------------
# BADGE NORMALIZATION
# -----------------------------

def normalize_badges(badges):

    normalized = []

    for b in badges:

        normalized.append({
            "type": b.get("type"),
            "text": b.get("text")
        })

    return normalized


# -----------------------------
# CHAT NORMALIZER
# -----------------------------

def normalize_chat(chat_file):

    normalized_file = chat_file.parent / "chat_normalized.json"

    if normalized_file.exists():
        return

    raw = json.loads(chat_file.read_text())

    users = load_user_cache()

    normalized = []

    for msg in raw:

        sender = msg["sender"]

        uid = str(sender["id"])
        username = sender.get("username")

        avatar = None

        if uid in users:

            avatar = users[uid].get("avatar")

        if not avatar:

            avatar = fetch_avatar(username)

            users[uid] = {
                "username": username,
                "avatar": avatar
            }

        message_parts = parse_message(msg.get("content", ""))

        normalized.append({

            "id": msg["id"],

            "timestamp": msg["created_at"],

            "user": {

                "id": sender["id"],
                "username": username,
                "avatar": avatar,
                "color": sender["identity"].get("color"),
                "badges": normalize_badges(
                    sender["identity"].get("badges", [])
                )

            },

            "message": message_parts,

            "type": msg.get("type")

        })

    normalized_file.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False)
    )

    save_user_cache(users)

    print("Normalized:", chat_file)


# -----------------------------
# SCANNERS
# -----------------------------

def scan_archive():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            chat_file = vod / "chat_raw.json"

            if chat_file.exists():
                normalize_chat(chat_file)


def scan_live_chat():

    if not LIVE_ROOT.exists():
        return

    for channel in LIVE_ROOT.iterdir():

        for vod in channel.iterdir():

            chat_file = vod / "chat_live.json"

            if chat_file.exists():
                normalize_chat(chat_file)


# -----------------------------
# MAIN
# -----------------------------

def main():

    scan_archive()
    scan_live_chat()


if __name__ == "__main__":
    main()
