from typing import Protocol

from imsg_keep_deletes.models import UnsendEvent


class Notifier(Protocol):
    def notify(self, event: UnsendEvent) -> None: ...
