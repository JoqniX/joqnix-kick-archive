import json
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
LIVE_ROOT = Path("data/live_chat")

USER_CACHE_FILE = Path("cache/kick_users.json")

EMOTE_BASE = "https://files.kick.com/emotes/"


def load_user_cache():

    if USER_CACHE_FILE.exists():
        return json.loads(USER_CACHE_FILE.read_text())

    return {}


def save_user_cache(users):

    USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    USER_CACHE_FILE.write_text(
        json.dumps(users, indent=2, ensure_ascii=False)
    )


def parse_message(content):

    """
    Converts Kick message string into
    renderable fragments (text + emotes)
    """

    parts = []

    tokens = content.split()

    for t in tokens:

        if t.startswith("[emote:"):

            try:

                name = t.split(":")[1].split("]")[0]

                parts.append({
                    "type": "emote",
                    "name": name,
                    "url": f"{EMOTE_BASE}{name}.png"
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

        avatar = None

        if uid in users:

            avatar = users[uid].get("avatar")

        else:

            avatar = sender.get("profile_pic")

            users[uid] = {
                "username": sender.get("username"),
                "avatar": avatar
            }

        message_parts = parse_message(msg.get("content", ""))

        normalized.append({

            "id": msg["id"],

            "timestamp": msg["created_at"],

            "user": {

                "id": sender["id"],
                "username": sender.get("username"),
                "avatar": avatar,
                "color": sender["identity"].get("color"),
                "badges": sender["identity"].get("badges", [])

            },

            "message": message_parts,

            "type": msg.get("type")

        })

    normalized_file.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False)
    )

    save_user_cache(users)

    print("Normalized:", chat_file)


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


def main():

    scan_archive()

    scan_live_chat()


if __name__ == "__main__":
    main()
