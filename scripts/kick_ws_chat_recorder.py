import json
import time
import requests
import websocket
import threading
from pathlib import Path

CHANNEL = "joqnix247"

WORKER = "https://kick-proxy.onaixia.workers.dev/api"

WS_URL = "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=python"

DATA_ROOT = Path("data/live_chat")

BUFFER = []
BUFFER_LOCK = threading.Lock()

seen_ids = set()

FLUSH_INTERVAL = 30


def get_chatroom_id():

    r = requests.get(f"{WORKER}/channel/{CHANNEL}", timeout=10)

    data = r.json()

    return data["chatroom"]["id"]


def get_vod_folder():

    folder = DATA_ROOT / CHANNEL / "live"

    folder.mkdir(parents=True, exist_ok=True)

    return folder


def flush_buffer():

    while True:

        time.sleep(FLUSH_INTERVAL)

        with BUFFER_LOCK:

            if not BUFFER:
                continue

            messages = BUFFER.copy()

            BUFFER.clear()

        folder = get_vod_folder()

        file = folder / "chat_live.json"

        existing = []

        if file.exists():

            try:
                existing = json.loads(file.read_text())
            except:
                existing = []

        existing.extend(messages)

        file.write_text(json.dumps(existing, indent=2))

        print("Flushed", len(messages), "messages")


def on_open(ws):

    chatroom_id = get_chatroom_id()

    channel = f"chatrooms.{chatroom_id}"

    print("Subscribing to", channel)

    sub = {
        "event": "pusher:subscribe",
        "data": {
            "channel": channel
        }
    }

    ws.send(json.dumps(sub))


def on_message(ws, message):

    try:

        msg = json.loads(message)

        if msg.get("event") != "App\\Events\\ChatMessageEvent":
            return

        data = json.loads(msg["data"])

        mid = data["id"]

        if mid in seen_ids:
            return

        seen_ids.add(mid)

        with BUFFER_LOCK:

            BUFFER.append(data)

        print(data["sender"]["username"], ":", data["content"])

    except Exception as e:

        print("Message parse error:", e)


def on_error(ws, error):

    print("WebSocket error:", error)


def on_close(ws, code, reason):

    print("WebSocket closed:", reason)

    time.sleep(5)

    start_ws()


def start_ws():

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever()


def main():

    print("Kick WebSocket Chat Recorder Started")

    threading.Thread(target=flush_buffer, daemon=True).start()

    start_ws()


if __name__ == "__main__":
    main()
