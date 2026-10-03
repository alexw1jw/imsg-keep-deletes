import time
from datetime import datetime, timezone
from pathlib import Path

from imsg_keep_deletes.cache.message_cache import MessageCache
from imsg_keep_deletes.db.reader import DbMessage


def _message(tmp_path: Path, guid: str = "g1") -> DbMessage:
    src = tmp_path / "orig.jpg"
    src.write_bytes(b"img")
    return DbMessage(
        rowid=1,
        guid=guid,
        text="hello",
        raw_text="hello",
        has_attributed_body=False,
        sent_at=datetime.now(timezone.utc),
        date_edited=0,
        is_empty=0,
        sender="+15551234567",
        chat="+15551234567",
        attachment_paths=(str(src),),
    )


def test_evict_deletes_copied_files(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    monkeypatch.setattr(
        "imsg_keep_deletes.cache.message_cache.ATTACHMENTS_DIR", attachments
    )
    cache = MessageCache(ttl_sec=60)
    snapshot = cache.add(_message(tmp_path))
    assert snapshot is not None
    copied = Path(snapshot.attachment_paths[0])
    assert copied.is_file()

    guid = snapshot.guid
    snap, _ = cache._entries[guid]
    cache._entries[guid] = (snap, time.monotonic() - 120)
    cache.evict_expired()

    assert guid not in cache._entries
    assert not copied.exists()


def test_remove_keeps_copied_files(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    monkeypatch.setattr(
        "imsg_keep_deletes.cache.message_cache.ATTACHMENTS_DIR", attachments
    )
    cache = MessageCache()
    snapshot = cache.add(_message(tmp_path))
    assert snapshot is not None
    copied = Path(snapshot.attachment_paths[0])
    cache.remove(snapshot.guid)
    assert copied.is_file()
