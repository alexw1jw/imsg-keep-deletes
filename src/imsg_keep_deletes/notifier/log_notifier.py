from imsg_keep_deletes.models import UnsendEvent
from imsg_keep_deletes.store.event_store import EventStore


class LogNotifier:
    def __init__(self, store: EventStore | None = None) -> None:
        self.store = store or EventStore()

    def notify(self, event: UnsendEvent) -> None:
        self.store.append(event)
