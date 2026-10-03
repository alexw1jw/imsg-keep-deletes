import os
from datetime import datetime, timezone
from pathlib import Path

from imsg_keep_deletes.models import UnsendEvent
from imsg_keep_deletes.store.event_store import EventStore


def _event(guid: str = "g1", attachments: tuple[str, ...] = ()) -> UnsendEvent:
    now = datetime.now(timezone.utc)
    return UnsendEvent(
        guid=guid,
        sender="+15551234567",
        chat="+15551234567",
        text="hello",
        sent_at=now,
        detected_at=now,
        attachment_paths=attachments,
    )


def test_append_ignores_duplicate_guid(tmp_path) -> None:
    store = EventStore(
        jsonl_path=tmp_path / "events.jsonl",
        db_path=tmp_path / "events.db",
    )
    store.append(_event())
    store.append(_event())
    assert store.count() == 1
    jsonl = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl) == 1


def test_prune_keeps_unsend_and_recent_copies(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    monkeypatch.setattr(
        "imsg_keep_deletes.store.event_store.ATTACHMENTS_DIR", attachments
    )
    monkeypatch.setattr("imsg_keep_deletes.store.event_store.CACHE_TTL_SEC", 60)

    keep = attachments / "keep.jpg"
    keep.write_bytes(b"keep")
    recent = attachments / "recent.jpg"
    recent.write_bytes(b"recent")
    old = attachments / "old.jpg"
    old.write_bytes(b"old")
    os.utime(old, (old.stat().st_atime, old.stat().st_mtime - 120))

    store = EventStore(
        jsonl_path=tmp_path / "events.jsonl",
        db_path=tmp_path / "events.db",
    )
    store.append(_event(attachments=(str(keep.resolve()),)))
    removed = store.prune_unreferenced_attachments()

    assert keep.is_file()
    assert recent.is_file()
    assert not old.exists()
    assert removed == 1
