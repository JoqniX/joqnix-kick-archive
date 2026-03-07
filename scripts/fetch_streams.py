def fetch_channel_vods(channel):

    print(f"\nFetching Kick VOD list for {channel}")

    url = f"https://kick-proxy.onaixia.workers.dev/api/videos/{channel}"

    cmd = f'curl -s -L -H "User-Agent: Mozilla/5.0" "{url}"'
    output = run(cmd)

    if not output:
        print("No response from curl")
        return []

    print("\n--- RAW RESPONSE (first 500 chars) ---")
    print(output[:500])
    print("-------------------------------------")

    try:
        data = json.loads(output)
    except Exception as e:
        print("JSON parse failed:", e)
        return []

    vod_list = data if isinstance(data, list) else data.get("data", [])

    print("VOD count detected:", len(vod_list))

    vods = []

    for v in vod_list:

        if not isinstance(v, dict):
            continue

        # skip currently live streams
        if v.get("is_live"):
            print("Skipping live stream")
            continue

        video = v.get("video")

        if not isinstance(video, dict):
            continue

        uuid = video.get("uuid")

        if not uuid:
            continue

        try:
            timestamp = int(
                datetime.strptime(
                    v["created_at"], "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            )
        except:
            continue

        thumbnail_url = None
        if isinstance(v.get("thumbnail"), dict):
            thumbnail_url = v["thumbnail"].get("src")

        vods.append({
            "id": uuid,
            "title": v.get("session_title"),
            "timestamp": timestamp,
            "duration": v.get("duration"),
            "thumbnail": thumbnail_url,
            "webpage_url": f"https://kick.com/{channel}/videos/{uuid}",
            "channel_id": v.get("channel_id")
        })

    print(f"{channel} returned {len(vods)} usable entries")

    return vods
