import json
import time
import urllib.request
import subprocess
from pathlib import Path
from datetime import datetime

CHANNELS = ["joqnix"]

ARCHIVE_ROOT = Path("data/kick_archive")
INDEX_FILE = ARCHIVE_ROOT / "index.json"
METADATA_INDEX_FILE = ARCHIVE_ROOT / "metadata_index.json"

MINIMUM_AGE_SECONDS = 1800


def load_index():
    if not INDEX_FILE.exists():
        return {"channels": {ch: {"vod_ids": []} for ch in CHANNELS}}
    return json.loads(INDEX_FILE.read_text())


def save_index(data):
    INDEX_FILE.write_text(json.dumps(data, indent=2))


def load_metadata_index():
    if not METADATA_INDEX_FILE.exists():
        return {}
    return json.loads(METADATA_INDEX_FILE.read_text())


def save_metadata_index(data):
    METADATA_INDEX_FILE.write_text(json.dumps(data, indent=2))


def fetch_channel_vods(channel):

    print(f"\nFetching Kick VOD list for {channel}")

    url = f"https://kick.com/api/v2/channels/{channel}/videos"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print("API request failed:", e)
        return []

    vods = []

    for v in data.get("data", []):

        timestamp = int(
            datetime.fromisoformat(
                v["created_at"].replace("Z", "+00:00")
            ).timestamp()
        )

        vods.append({
            "id": str(v["id"]),
            "title": v.get("session_title"),
            "timestamp": timestamp,
            "duration": v.get("duration"),
            "thumbnail": v.get("thumbnail"),
            "webpage_url": f"https://kick.com/video/{v['id']}"
        })

    print(f"{channel} returned {len(vods)} entries")

    return vods


def download_thumbnail(url, folder):

    try:
        subprocess.run(
            f'curl -L "{url}" -o "{folder}/thumbnail.jpg"',
            shell=True,
            check=True
        )
    except:
        print("Thumbnail download failed")


def is_valid_archive(vod):

    vod_id = vod.get("id")

    if not vod_id:
        return False

    timestamp = vod.get("timestamp")

    if timestamp:
        if time.time() - timestamp < MINIMUM_AGE_SECONDS:
            print(f"Skipping too recent VOD: {vod_id}")
            return False

    return True


def archive_metadata(channel, vod, folder):

    metadata = {
        "id": vod["id"],
        "title": vod.get("title"),
        "created_at": vod.get("timestamp"),
        "timestamp": vod.get("timestamp"),
        "duration_seconds": vod.get("duration"),
        "webpage_url": vod.get("webpage_url"),
        "thumbnail": vod.get("thumbnail"),
        "channel": channel,
        "platform": "kick"
    }

    (folder / "metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )


def update_metadata_index(index, vod_id, channel, vod):

    index[vod_id] = {
        "platform": "kick",
        "channel": channel,
        "timestamp": vod.get("timestamp"),
        "duration_seconds": vod.get("duration"),
        "title": vod.get("title")
    }


def rebuild_metadata_from_file(metadata_index, vod_id, folder):

    metadata_file = folder / "metadata.json"

    if not metadata_file.exists():
        return

    data = json.loads(metadata_file.read_text())

    metadata_index[vod_id] = {
        "platform": "kick",
        "channel": data.get("channel"),
        "timestamp": data.get("timestamp"),
        "duration_seconds": data.get("duration_seconds"),
        "title": data.get("title")
    }

    print(f"[metadata_index] Rebuilt entry for {vod_id}")


def main():

    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

    index_data = load_index()
    metadata_index = load_metadata_index()

    for channel in CHANNELS:

        channel_root = ARCHIVE_ROOT / channel
        channel_root.mkdir(parents=True, exist_ok=True)

        existing_ids = set(index_data["channels"][channel]["vod_ids"])

        vods = fetch_channel_vods(channel)

        for vod in vods:

            vod_id = vod["id"]

            if not is_valid_archive(vod):
                continue

            folder = channel_root / vod_id
            folder.mkdir(parents=True, exist_ok=True)

            if vod_id not in existing_ids:

                print(f"\nArchiving metadata for {channel} VOD: {vod_id}")

                archive_metadata(channel, vod, folder)

                if vod.get("thumbnail"):
                    download_thumbnail(vod["thumbnail"], folder)

                index_data["channels"][channel]["vod_ids"].append(vod_id)

                update_metadata_index(metadata_index, vod_id, channel, vod)

            else:
                if vod_id not in metadata_index:
                    rebuild_metadata_from_file(metadata_index, vod_id, folder)

    save_index(index_data)
    save_metadata_index(metadata_index)


if __name__ == "__main__":
    main()
