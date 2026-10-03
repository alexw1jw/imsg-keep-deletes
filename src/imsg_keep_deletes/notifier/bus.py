import logging

from imsg_keep_deletes.models import UnsendEvent

logger = logging.getLogger(__name__)


class NotifierBus:
    def __init__(self, notifiers: list) -> None:
        self.notifiers = notifiers

    def notify(self, event: UnsendEvent) -> None:
        for notifier in self.notifiers:
            try:
                notifier.notify(event)
            except Exception:
                logger.exception(
                    "Notifier %s failed for guid=%s",
                    type(notifier).__name__,
                    event.guid,
                )
