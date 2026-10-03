from datetime import datetime

from imsg_keep_deletes.paths import POLL_INTERVAL_SEC
from imsg_keep_deletes.store.event_store import EventStore


def _format_local(dt: datetime) -> str:
    if dt.tzinfo is None:
        local = dt.astimezone()
    else:
        local = dt.astimezone()
    return local.strftime("%b %d, %Y %I:%M:%S %p")


def format_status_message(
    *,
    running: bool,
    telegram_enabled: bool,
    consecutive_failures: int = 0,
    store: EventStore | None = None,
) -> str:
    event_store = store or EventStore()
    count = event_store.count()
    latest = event_store.latest_detected_at()

    lines = [
        "imsg-keep-deletes status",
        "",
        f"Watcher: {'running' if running else 'stopped'}",
        f"Telegram alerts: {'on' if telegram_enabled else 'off'}",
        f"Unsends saved: {count}",
    ]
    if latest:
        lines.append(f"Last unsend: {_format_local(latest)}")
    lines.append(f"Poll interval: {POLL_INTERVAL_SEC}s")
    if consecutive_failures:
        lines.append("")
        lines.append(
            f"Warning: {consecutive_failures} recent poll failure(s). "
            "Check Full Disk Access for Python."
        )
    return "\n".join(lines)


HELP_MESSAGE = """imsg-keep-deletes commands

/status — Check if the watcher is running
/help — Show this message

You get an alert here automatically when someone unsends a message to you."""
