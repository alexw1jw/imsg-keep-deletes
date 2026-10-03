import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from imsg_keep_deletes.models import UnsendEvent
from imsg_keep_deletes.paths import (
    ATTACHMENTS_DIR,
    CACHE_TTL_SEC,
    EVENTS_DB,
    EVENTS_JSONL,
    ensure_app_support,
)


class EventStore:
    def __init__(
        self,
        jsonl_path: Path = EVENTS_JSONL,
        db_path: Path = EVENTS_DB,
    ) -> None:
        self.jsonl_path = jsonl_path
        self.db_path = db_path
        ensure_app_support()
        self._init_db()

    def append(self, event: UnsendEvent) -> None:
        payload = self._to_dict(event)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO unsend_events
                (guid, sender, chat, text, sent_at, detected_at, attachments_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.guid,
                    event.sender,
                    event.chat,
                    event.text,
                    event.sent_at.isoformat(),
                    event.detected_at.isoformat(),
                    json.dumps(list(event.attachment_paths)),
                ),
            )
            inserted = cursor.rowcount == 1
        if not inserted:
            return
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def list_recent(self, limit: int = 50) -> list[dict]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, guid, sender, chat, text, sent_at, detected_at, attachments_json
                FROM unsend_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM unsend_events").fetchone()
        return int(row[0] if row else 0)

    def latest_detected_at(self) -> datetime | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT detected_at
                FROM unsend_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if not row or not row[0]:
            return None
        try:
            return datetime.fromisoformat(row[0])
        except ValueError:
            return None

    def get_by_id(self, event_id: int) -> dict | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, guid, sender, chat, text, sent_at, detected_at, attachments_json
                FROM unsend_events
                WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
        return dict(row) if row else None

    def prune_unreferenced_attachments(self) -> int:
        """Remove copied files that are older than the cache TTL and not an unsend."""
        keep: set[Path] = set()
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT attachments_json FROM unsend_events"
            ).fetchall()
        for (raw,) in rows:
            try:
                paths = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(paths, list):
                continue
            for path_str in paths:
                keep.add(Path(path_str).resolve())

        if not ATTACHMENTS_DIR.is_dir():
            return 0

        now = time.time()
        removed = 0
        for path in ATTACHMENTS_DIR.iterdir():
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
                if resolved in keep:
                    continue
                if now - path.stat().st_mtime < CACHE_TTL_SEC:
                    continue
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unsend_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    chat TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    attachments_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                DELETE FROM unsend_events
                WHERE id NOT IN (
                    SELECT MIN(id) FROM unsend_events GROUP BY guid
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unsend_events_guid
                ON unsend_events(guid)
                """
            )

    @staticmethod
    def _to_dict(event: UnsendEvent) -> dict:
        return {
            "type": "unsend",
            "guid": event.guid,
            "sender": event.sender,
            "chat": event.chat,
            "text": event.text,
            "sent_at": event.sent_at.isoformat(),
            "detected_at": event.detected_at.isoformat(),
            "attachments": list(event.attachment_paths),
        }
