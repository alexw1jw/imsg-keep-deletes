from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MessageSnapshot:
    guid: str
    rowid: int
    sender: str
    chat: str
    text: str
    sent_at: datetime
    attachment_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnsendEvent:
    guid: str
    sender: str
    chat: str
    text: str
    sent_at: datetime
    detected_at: datetime
    attachment_paths: tuple[str, ...] = ()
