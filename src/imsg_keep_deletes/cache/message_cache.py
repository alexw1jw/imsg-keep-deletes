import shutil
import time
from pathlib import Path

from imsg_keep_deletes.db.reader import DbMessage
from imsg_keep_deletes.models import MessageSnapshot
from imsg_keep_deletes.paths import ATTACHMENTS_DIR, CACHE_TTL_SEC, ensure_app_support


class MessageCache:
    def __init__(self, ttl_sec: int = CACHE_TTL_SEC) -> None:
        self.ttl_sec = ttl_sec
        self._entries: dict[str, tuple[MessageSnapshot, float]] = {}

    def add(self, message: DbMessage) -> MessageSnapshot | None:
        if not message.text and not message.attachment_paths:
            return None
        if message.guid in self._entries:
            return self._entries[message.guid][0]

        attachments = tuple(
            copied
            for path in message.attachment_paths
            if (copied := self._copy_attachment(message.guid, path))
        )
        snapshot = MessageSnapshot(
            guid=message.guid,
            rowid=message.rowid,
            sender=message.sender,
            chat=message.chat,
            text=message.text,
            sent_at=message.sent_at,
            attachment_paths=attachments,
        )
        self._entries[message.guid] = (snapshot, time.monotonic())
        return snapshot

    def get_all(self) -> list[MessageSnapshot]:
        self.evict_expired()
        return [entry[0] for entry in self._entries.values()]

    def remove(self, guid: str) -> None:
        self._entries.pop(guid, None)

    def evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            guid
            for guid, (_, cached_at) in self._entries.items()
            if now - cached_at > self.ttl_sec
        ]
        for guid in expired:
            snapshot, _ = self._entries.pop(guid)
            self._delete_copies(snapshot.attachment_paths)

    @staticmethod
    def _delete_copies(paths: tuple[str, ...]) -> None:
        attachments_root = ATTACHMENTS_DIR.resolve()
        for path_str in paths:
            path = Path(path_str)
            try:
                if path.resolve().parent != attachments_root:
                    continue
                path.unlink(missing_ok=True)
            except OSError:
                continue

    @staticmethod
    def _copy_attachment(guid: str, source: str) -> str | None:
        src = Path(source)
        if not src.is_file():
            return None
        ensure_app_support()
        ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = ATTACHMENTS_DIR / f"{guid}_{src.name}"
        if not dest.exists():
            shutil.copy2(src, dest)
        return str(dest)
