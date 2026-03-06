import subprocess
from pathlib import Path
import json

ARCHIVE_ROOT = Path("data/kick_archive")

def download_chat(uuid, folder):

    output_file = folder / "chat_raw.json"

    if output_file.exists():
        print(f"{uuid} chat already downloaded")
        return

    print(f"Downloading Kick chat for {uuid}")

    cmd = [
        "node",
        "kick-chat-downloader.js",
        uuid,
        str(output_file)
    ]

    subprocess.run(cmd)


def main():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            uuid = vod.name

            download_chat(uuid, vod)


if __name__ == "__main__":
    main()
