import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from imsg_keep_deletes.config import load_config, save_telegram_config
from imsg_keep_deletes.daemon import Daemon
from imsg_keep_deletes.notifier.telegram_notifier import TelegramNotifier
from imsg_keep_deletes.paths import CONFIG_FILE, EVENTS_JSONL
from imsg_keep_deletes.store.event_store import EventStore

PLIST_LABEL = "com.imsg-keep-deletes"
PLIST_PATH = (
    Path.home() / "Library/LaunchAgents" / f"{PLIST_LABEL}.plist"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_PLIST = REPO_ROOT / "launchd" / f"{PLIST_LABEL}.plist"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor iMessage for unsent inbound messages.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Run the daemon in the foreground")
    events_parser = sub.add_parser("events", help="Show recent unsend events")
    events_parser.add_argument("--limit", type=int, default=20)
    open_parser = sub.add_parser(
        "open",
        help="Open a saved attachment in Preview by event ID",
    )
    open_parser.add_argument("id", type=int, help="Event ID from `imsg-kd events`")
    sub.add_parser("follow", help="Tail the unsend log live")
    sub.add_parser("status", help="Show basic daemon status")
    sub.add_parser("install", help="Install LaunchAgent (start at login)")
    sub.add_parser("uninstall", help="Remove LaunchAgent")

    tg = sub.add_parser("telegram", help="Configure Telegram notifications")
    tg_sub = tg.add_subparsers(dest="telegram_command", required=True)
    tg_setup = tg_sub.add_parser("setup", help="Save bot token and chat ID")
    tg_setup.add_argument("token", help="Bot token from @BotFather")
    tg_setup.add_argument("chat_id", help="Your Telegram chat ID")
    tg_sub.add_parser("test", help="Send a test message to Telegram")
    tg_sub.add_parser("status", help="Show Telegram config status")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.command == "run":
        Daemon().run_forever()
    elif args.command == "events":
        _print_events(args.limit)
    elif args.command == "open":
        _open_attachment(args.id)
    elif args.command == "follow":
        _follow_log()
    elif args.command == "status":
        _print_status()
    elif args.command == "install":
        _install()
    elif args.command == "uninstall":
        _uninstall()
    elif args.command == "telegram":
        if args.telegram_command == "setup":
            _telegram_setup(args.token, args.chat_id)
        elif args.telegram_command == "test":
            _telegram_test()
        elif args.telegram_command == "status":
            _telegram_status()


def _print_events(limit: int) -> None:
    events = EventStore().list_recent(limit=limit)
    if not events:
        print("No unsend events yet.")
        return
    for event in reversed(events):
        print("-" * 60)
        print(f"[#{event['id']}] From: {event['sender']} ({event['chat']})")
        print(f"       Sent:     {event['sent_at']}")
        print(f"       Detected: {event['detected_at']}")
        print(f"       Text:     {event['text']}")
        attachments = json.loads(event["attachments_json"])
        if attachments:
            print(f"       Files:    {', '.join(attachments)}")
            print(f"       Open:     imsg-kd open {event['id']}")


def _open_attachment(event_id: int) -> None:
    event = EventStore().get_by_id(event_id)
    if event is None:
        print(f"No event with id {event_id}.", file=sys.stderr)
        sys.exit(1)

    attachments = json.loads(event["attachments_json"])
    if not attachments:
        print(
            f"Event #{event_id} has no saved attachments.",
            file=sys.stderr,
        )
        sys.exit(1)

    path = Path(attachments[0])
    if not path.is_file():
        print(f"Attachment file not found: {path}", file=sys.stderr)
        sys.exit(1)

    subprocess.run(["open", "-a", "Preview", str(path)], check=True)
    if len(attachments) > 1:
        print(
            f"Opened first of {len(attachments)} files in Preview: {path}"
        )
    else:
        print(f"Opened in Preview: {path}")


def _follow_log() -> None:
    EVENTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    if not EVENTS_JSONL.exists():
        EVENTS_JSONL.touch()
    print(f"Following {EVENTS_JSONL} (Ctrl+C to stop)...")
    with EVENTS_JSONL.open("r", encoding="utf-8") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            print(
                f"[{event.get('detected_at')}] "
                f"{event.get('sender')}: {event.get('text')!r}"
            )


def _print_status() -> None:
    loaded = _launchctl_list()
    cfg = load_config()
    print(f"LaunchAgent loaded: {loaded}")
    print(f"Telegram: {'enabled' if cfg.telegram_enabled else 'disabled'}")
    print(f"Log file: {EVENTS_JSONL}")
    print(f"Exists: {EVENTS_JSONL.exists()}")


def _telegram_setup(token: str, chat_id: str) -> None:
    save_telegram_config(token, chat_id)
    print(f"Saved Telegram config to {CONFIG_FILE}")
    print("Run: imsg-kd telegram test")


def _telegram_test() -> None:
    notifier = TelegramNotifier.from_config()
    if notifier is None:
        print(
            "Telegram not configured. Run:\n"
            "  imsg-kd telegram setup <BOT_TOKEN> <CHAT_ID>",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        notifier.send_test()
    except RuntimeError as exc:
        print(f"Telegram test failed: {exc}", file=sys.stderr)
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            print(
                "\nFix (macOS Python): run "
                '"/Applications/Python 3.11/Install Certificates.command"',
                file=sys.stderr,
            )
        sys.exit(1)
    print("Test message sent. Check Telegram.")


def _telegram_status() -> None:
    cfg = load_config()
    if not cfg.telegram_enabled:
        print("Telegram: not configured")
        print("Setup: imsg-kd telegram setup <BOT_TOKEN> <CHAT_ID>")
        return
    token = cfg.telegram_bot_token or ""
    masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "(set)"
    print("Telegram: enabled")
    print(f"Config: {CONFIG_FILE}")
    print(f"Bot token: {masked}")
    print(f"Chat ID: {cfg.telegram_chat_id}")


def _install() -> None:
    if not BUNDLED_PLIST.exists():
        print(f"Missing plist at {BUNDLED_PLIST}", file=sys.stderr)
        sys.exit(1)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable).resolve()
    project_root = REPO_ROOT.resolve()
    content = BUNDLED_PLIST.read_text(encoding="utf-8")
    content = content.replace("{{PYTHON}}", str(python))
    content = content.replace("{{PROJECT_ROOT}}", str(project_root))
    content = content.replace("{{HOME}}", str(Path.home()))
    PLIST_PATH.write_text(content, encoding="utf-8")
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)],
        check=False,
    )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)],
        check=True,
    )
    print(f"Installed and started {PLIST_LABEL}")


def _uninstall() -> None:
    if not PLIST_PATH.exists():
        print("LaunchAgent not installed.")
        return
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)],
        check=False,
    )
    PLIST_PATH.unlink(missing_ok=True)
    print(f"Removed {PLIST_LABEL}")


def _launchctl_list() -> bool:
    if not PLIST_PATH.exists():
        return False
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return PLIST_LABEL in result.stdout


if __name__ == "__main__":
    main()
