# imsg-keep-deletes

Monitors your Mac's iMessage database and saves alerts when someone **unsends** a message to you.

## What it does

1. Watches `~/Library/Messages/chat.db` every 3 seconds
2. Remembers recent incoming messages for 5 minutes (Apple only allows 2 minutes to unsend)
3. Detects when a cached message gets wiped (Undo Send)
4. Saves the original text, sender, timestamp, and any attachments
5. Optionally sends an alert to **Telegram**

## One-time setup

### 1. Full Disk Access

macOS blocks access to the Messages database unless you allow it.

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Add **Terminal** (or iTerm / Cursor) for CLI use
3. Also add the **Python** binary you will run as the LaunchAgent (the interpreter inside `.venv/bin/`)
4. Quit and reopen the terminal app



### 2. Install the project

```bash
cd /path/to/imsg-keep-deletes
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```



### 3. Quick test (optional)

```bash
python scripts/check_messages.py
```

You should see recent inbound messages. If you get `unable to open database`, Full Disk Access isn't set up yet.

## Usage

Activate the venv first (`source .venv/bin/activate`). You do **not** need the venv for the background service after `imsg-kd install`.

### Run in the foreground (testing)

```bash
imsg-kd run
```



### View saved unsends

```bash
imsg-kd events
```

Each event has an ID like `[#3]`.

### Open a saved attachment in Preview

```bash
imsg-kd open 3
```



### Watch live

```bash
imsg-kd follow
```



### Background service (starts at login)

```bash
imsg-kd install
imsg-kd status
imsg-kd uninstall    # stop and remove
```

`install` / `uninstall` only affect the LaunchAgent. They do not delete logs, attachments, or your Telegram config.

### Telegram notifications (optional)

1. In Telegram, message **@BotFather** → `/newbot` → copy the bot token
2. Message your new bot once
3. Get your chat ID from `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Save it:

```bash
imsg-kd telegram setup YOUR_BOT_TOKEN YOUR_CHAT_ID
imsg-kd telegram test
imsg-kd uninstall && imsg-kd install
```

Bot commands: `/status`, `/help`.

## Where data is stored


| Path                                                           | What                         |
| -------------------------------------------------------------- | ---------------------------- |
| `~/Library/Application Support/imsg-keep-deletes/events.jsonl` | Human-readable log           |
| `~/Library/Application Support/imsg-keep-deletes/events.db`    | Queryable database           |
| `~/Library/Application Support/imsg-keep-deletes/attachments/` | Copies of unsent attachments |
| `~/Library/Application Support/imsg-keep-deletes/config.json`  | Telegram bot token + chat ID |
| `~/Library/Logs/imsg-keep-deletes.log`                         | Daemon stdout/stderr         |




## Notes

- Only **inbound Undo Send**. Swipe-to-delete and your own unsends are ignored.
- The watcher must see the message **before** it is unsent (poll every 3s, remember for 5 minutes).
- Restarting the service clears the in-memory cache; messages already on disk from before the restart are not recached.
- Attachment copies that are never unsent are deleted after 5 minutes.
- Local log is always saved. Telegram is optional; only unsend alerts leave your Mac.

