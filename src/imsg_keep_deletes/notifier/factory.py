from imsg_keep_deletes.config import load_config
from imsg_keep_deletes.notifier.bus import NotifierBus
from imsg_keep_deletes.notifier.log_notifier import LogNotifier
from imsg_keep_deletes.notifier.telegram_notifier import TelegramNotifier
from imsg_keep_deletes.store.event_store import EventStore


def build_notifier() -> NotifierBus:
    store = EventStore()
    notifiers: list = [LogNotifier(store)]

    cfg = load_config()
    if cfg.telegram_enabled:
        notifiers.append(
            TelegramNotifier(cfg.telegram_bot_token, cfg.telegram_chat_id)
        )

    return NotifierBus(notifiers)
