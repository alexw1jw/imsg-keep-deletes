import json
import logging

from imsg_keep_deletes.config import load_config
from imsg_keep_deletes.notifier.telegram_notifier import TelegramNotifier
from imsg_keep_deletes.paths import APP_SUPPORT, ensure_app_support
from imsg_keep_deletes.status_report import HELP_MESSAGE, format_status_message

logger = logging.getLogger(__name__)

_OFFSET_FILE = APP_SUPPORT / "telegram_offset.json"


class TelegramCommandHandler:
    def __init__(self, notifier: TelegramNotifier) -> None:
        self.notifier = notifier
        self._offset = self._load_offset()

    @classmethod
    def from_config(cls) -> "TelegramCommandHandler | None":
        notifier = TelegramNotifier.from_config()
        if notifier is None:
            return None
        return cls(notifier)

    def skip_pending(self) -> None:
        """Ignore queued messages from before this daemon run."""
        try:
            updates = self.notifier.get_updates(offset=self._offset, timeout=0)
        except Exception:
            logger.warning("Telegram skip-pending failed", exc_info=True)
            return
        if not updates:
            return
        self._offset = max(int(u["update_id"]) for u in updates) + 1
        self._save_offset()

    def poll(self, consecutive_failures: int = 0) -> None:
        try:
            updates = self.notifier.get_updates(
                offset=self._offset,
                timeout=0,
            )
        except Exception:
            logger.warning("Telegram command poll failed", exc_info=True)
            return

        changed = False
        for update in updates:
            update_id = int(update["update_id"])
            if update_id >= self._offset:
                self._offset = update_id + 1
                changed = True
            self._handle_update(update, consecutive_failures)

        if changed:
            self._save_offset()

    def _handle_update(self, update: dict, consecutive_failures: int) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat = message.get("chat") or {}
        if str(chat.get("id")) != str(self.notifier.chat_id):
            return

        text = (message.get("text") or "").strip()
        if not text.startswith("/"):
            return

        command = text.split()[0].split("@")[0].lower()
        cfg = load_config()

        if command == "/help":
            self.notifier.send_message(HELP_MESSAGE)
        elif command == "/status":
            self.notifier.send_message(
                format_status_message(
                    running=True,
                    telegram_enabled=cfg.telegram_enabled,
                    consecutive_failures=consecutive_failures,
                )
            )
        else:
            self.notifier.send_message(
                "Unknown command. Try /help"
            )

    @staticmethod
    def _load_offset() -> int:
        if not _OFFSET_FILE.exists():
            return 0
        try:
            data = json.loads(_OFFSET_FILE.read_text(encoding="utf-8"))
            return int(data.get("offset", 0))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return 0

    def _save_offset(self) -> None:
        ensure_app_support()
        _OFFSET_FILE.write_text(
            json.dumps({"offset": self._offset}) + "\n",
            encoding="utf-8",
        )
