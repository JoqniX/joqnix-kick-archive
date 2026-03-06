const fs = require("fs")
const fetch = require("node-fetch")

const uuid = process.argv[2]
const output = process.argv[3]

async function downloadChat() {

    let cursor = null
    let messages = []

    while (true) {

        let url = `https://kick.com/api/v2/videos/${uuid}/comments`

        if (cursor) {
            url += `?cursor=${cursor}`
        }

        console.log("Fetching:", url)

        const r = await fetch(url, {
            headers: {
                "User-Agent": "Mozilla/5.0"
            }
        })

        const data = await r.json()

        if (!data.data || data.data.length === 0)
            break

        messages.push(...data.data)

        cursor = data.cursor

        if (!cursor)
            break
    }

    fs.writeFileSync(output, JSON.stringify(messages, null, 2))

    console.log("Saved", messages.length, "messages")
}

downloadChat()
