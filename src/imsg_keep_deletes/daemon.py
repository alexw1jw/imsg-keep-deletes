import json
import logging
import time
from datetime import datetime, timezone

from imsg_keep_deletes.cache.message_cache import MessageCache
from imsg_keep_deletes.contacts.resolver import ContactResolver
from imsg_keep_deletes.db.reader import ChatDbReader
from imsg_keep_deletes.db.schema import datetime_to_apple_ts
from imsg_keep_deletes.detector.unsend import UnsendDetector
from imsg_keep_deletes.notifier.factory import build_notifier
from imsg_keep_deletes.notifier.telegram_commands import TelegramCommandHandler
from imsg_keep_deletes.paths import POLL_INTERVAL_SEC, STATE_FILE, ensure_app_support
from imsg_keep_deletes.store.event_store import EventStore

logger = logging.getLogger(__name__)

# A persistent failure (bad permissions, missing DB) repeats every poll; log the
# first one in full, then only occasional reminders.
_FAILURE_REMINDER_EVERY = 200


class Daemon:
    def __init__(self) -> None:
        self._contacts = ContactResolver()
        self._contacts.load()
        self.reader = ChatDbReader(contacts=self._contacts)
        self.cache = MessageCache()
        self.detector = UnsendDetector(self.reader)
        self.notifier = build_notifier()
        self._telegram_commands = TelegramCommandHandler.from_config()
        self._last_rowid = self._load_last_rowid()
        self._last_date_edited = self._load_last_date_edited()
        self._consecutive_failures = 0
        ensure_app_support()
        EventStore().prune_unreferenced_attachments()

    def run_once(self) -> int:
        messages = self.reader.fetch_since_rowid(self._last_rowid)
        for message in messages:
            self._last_rowid = max(self._last_rowid, message.rowid)
            self.cache.add(message)

        for message in self.reader.fetch_edited_since(self._last_date_edited):
            self._last_date_edited = max(
                self._last_date_edited, message.date_edited
            )
            self.cache.add(message)

        events = self.detector.check_many(self.cache.get_all())
        for event in events:
            self.notifier.notify(event)
            self.cache.remove(event.guid)
            logger.info("Unsend detected from %s: %r", event.sender, event.text)

        self.cache.evict_expired()
        self._save_last_rowid()
        if self._telegram_commands is not None:
            self._telegram_commands.poll(
                consecutive_failures=self._consecutive_failures,
            )
        return len(events)

    def run_forever(self) -> None:
        from imsg_keep_deletes.config import load_config

        cfg = load_config()
        tg = "on" if cfg.telegram_enabled else "off"
        contacts = "on" if self._contacts.available else "off"
        logger.info(
            "Daemon started (poll every %ss, telegram=%s, contacts=%s)",
            POLL_INTERVAL_SEC,
            tg,
            contacts,
        )
        if self._telegram_commands is not None:
            self._telegram_commands.skip_pending()
        while True:
            try:
                self.run_once()
            except Exception:
                self._record_failure()
            else:
                self._record_success()
            time.sleep(POLL_INTERVAL_SEC)

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures == 1:
            logger.exception("Poll cycle failed")
        elif self._consecutive_failures % _FAILURE_REMINDER_EVERY == 0:
            logger.error(
                "Poll cycle still failing (%d consecutive failures)",
                self._consecutive_failures,
            )

    def _record_success(self) -> None:
        if self._consecutive_failures:
            logger.info(
                "Recovered after %d failed poll(s)", self._consecutive_failures
            )
            self._consecutive_failures = 0

    def _load_state(self) -> dict:
        if not STATE_FILE.exists():
            return {}
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, ValueError, TypeError):
            return {}

    def _load_last_rowid(self) -> int:
        data = self._load_state()
        if "last_rowid" in data:
            return int(data["last_rowid"])
        return self.reader.max_rowid()

    def _load_last_date_edited(self) -> int:
        data = self._load_state()
        stored = data.get("last_date_edited")
        if stored:
            return int(stored)
        return datetime_to_apple_ts(datetime.now(timezone.utc))

    def _save_last_rowid(self) -> None:
        ensure_app_support()
        STATE_FILE.write_text(
            json.dumps(
                {
                    "last_rowid": self._last_rowid,
                    "last_date_edited": self._last_date_edited,
                }
            ),
            encoding="utf-8",
        )
