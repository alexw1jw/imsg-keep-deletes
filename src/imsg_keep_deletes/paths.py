from pathlib import Path

CHAT_DB = Path.home() / "Library/Messages/chat.db"
APP_SUPPORT = Path.home() / "Library/Application Support/imsg-keep-deletes"
ATTACHMENTS_DIR = APP_SUPPORT / "attachments"
EVENTS_JSONL = APP_SUPPORT / "events.jsonl"
EVENTS_DB = APP_SUPPORT / "events.db"
STATE_FILE = APP_SUPPORT / "state.json"
CONFIG_FILE = APP_SUPPORT / "config.json"

POLL_INTERVAL_SEC = 3
CACHE_TTL_SEC = 5 * 60  # 5 minutes — covers the 2-minute unsend window

_DIR_MODE = 0o700
_FILE_MODE = 0o600


def ensure_app_support() -> None:
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    try:
        APP_SUPPORT.chmod(_DIR_MODE)
    except OSError:
        pass
    if CONFIG_FILE.exists():
        try:
            CONFIG_FILE.chmod(_FILE_MODE)
        except OSError:
            pass
