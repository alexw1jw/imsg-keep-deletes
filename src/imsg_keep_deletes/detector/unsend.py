from datetime import datetime, timezone

from imsg_keep_deletes.db.reader import ChatDbReader, DbMessage
from imsg_keep_deletes.models import MessageSnapshot, UnsendEvent


def is_unsent(cached: MessageSnapshot, current: DbMessage | None) -> bool:
    if current is None:
        # Hard delete — not an unsend.
        return False
    cached_had = bool((cached.text or "").strip()) or bool(cached.attachment_paths)
    if not cached_had:
        return False
    # Trust Apple's unsend flags once we've cached the original content.
    # Don't require attributedBody to be NULL — on some builds the blob
    # remains even after text is wiped, which blocked detection.
    return current.is_empty == 1 and current.date_edited > 0


class UnsendDetector:
    def __init__(self, reader: ChatDbReader | None = None) -> None:
        self.reader = reader or ChatDbReader()

    def check(self, cached: MessageSnapshot) -> UnsendEvent | None:
        current = self.reader.fetch_by_guid(cached.guid)
        if not is_unsent(cached, current):
            return None
        return self._to_event(cached)

    def check_many(self, cached: list[MessageSnapshot]) -> list[UnsendEvent]:
        if not cached:
            return []
        states = self.reader.fetch_states_by_guids([snap.guid for snap in cached])
        return [
            self._to_event(snap)
            for snap in cached
            if is_unsent(snap, states.get(snap.guid))
        ]

    @staticmethod
    def _to_event(cached: MessageSnapshot) -> UnsendEvent:
        return UnsendEvent(
            guid=cached.guid,
            sender=cached.sender,
            chat=cached.chat,
            text=cached.text,
            sent_at=cached.sent_at,
            detected_at=datetime.now(timezone.utc),
            attachment_paths=cached.attachment_paths,
        )
