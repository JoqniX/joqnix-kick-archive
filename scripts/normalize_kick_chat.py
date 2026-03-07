import json
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")
USER_CACHE_FILE = Path("cache/kick_users.json")


def normalize_chat(chat_file):

    normalized_file = chat_file.parent / "chat_normalized.json"

    if normalized_file.exists():
        return

    raw = json.loads(chat_file.read_text())

    users = {}

    if USER_CACHE_FILE.exists():
        users = json.loads(USER_CACHE_FILE.read_text())

    normalized = []

    for msg in raw:

        sender = msg["sender"]

        uid = str(sender["id"])

        avatar = None

        if uid in users:

            avatar = users[uid].get("profile_pic")

        normalized.append({
            "id": msg["id"],
            "timestamp": msg["created_at"],
            "user_id": sender["id"],
            "username": sender["username"],
            "color": sender["identity"].get("color"),
            "badges": sender["identity"].get("badges", []),
            "avatar": avatar,
            "content": msg["content"],
            "type": msg["type"]
        })

    normalized_file.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False)
    )

    print("Normalized:", chat_file)


def main():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            chat_file = vod / "chat_raw.json"

            if chat_file.exists():

                normalize_chat(chat_file)


if __name__ == "__main__":
    main()
