import json
import os
from dataclasses import dataclass

from imsg_keep_deletes.paths import CONFIG_FILE, ensure_app_support


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def load_config() -> AppConfig:
    ensure_app_support()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}

    tg = data.get("telegram") or {}
    token = os.environ.get("IMSG_KD_TELEGRAM_TOKEN") or tg.get("bot_token")
    chat_id = os.environ.get("IMSG_KD_TELEGRAM_CHAT_ID") or tg.get("chat_id")
    return AppConfig(
        telegram_bot_token=str(token).strip() if token else None,
        telegram_chat_id=str(chat_id).strip() if chat_id else None,
    )


def save_telegram_config(bot_token: str, chat_id: str) -> None:
    ensure_app_support()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data["telegram"] = {
        "bot_token": bot_token.strip(),
        "chat_id": chat_id.strip(),
    }
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    ensure_app_support()
