import json
import subprocess
import time
from pathlib import Path

ARCHIVE_ROOT = Path("data/kick_archive")

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        return None
    return result.stdout


def fetch_chat(uuid):

    messages = []
    cursor = None

    while True:

        url = f"https://kick.com/api/v2/videos/{uuid}/comments"

        if cursor:
            url += f"?cursor={cursor}"

        cmd = f'curl -s -L -H "User-Agent: Mozilla/5.0" "{url}"'
        output = run(cmd)
        print(output[:500])

        if not output:
            break

        data = json.loads(output)

        batch = data.get("data", [])

        if not batch:
            break

        messages.extend(batch)

        cursor = data.get("cursor")

        if not cursor:
            break

        time.sleep(1)

    return messages


def main():

    for channel in ARCHIVE_ROOT.iterdir():

        if not channel.is_dir():
            continue

        for vod in channel.iterdir():

            if not vod.is_dir():
                continue

            uuid = vod.name
            chat_file = vod / "chat_raw.json"

            if chat_file.exists():
                print(f"{uuid} chat already exists")
                continue

            print(f"Downloading chat for {uuid}")

            messages = fetch_chat(uuid)

            if messages:

                chat_file.write_text(
                    json.dumps(messages, indent=2, ensure_ascii=False)
                )

                print(f"Saved {len(messages)} messages")

            else:
                print(f"No chat messages found for {uuid}")


if __name__ == "__main__":
    main()
