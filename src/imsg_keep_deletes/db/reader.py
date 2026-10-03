import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from imsg_keep_deletes.db.attributed_body import message_text
from imsg_keep_deletes.contacts.resolver import ContactResolver
from imsg_keep_deletes.db.schema import (
    ATTACHMENTS_FOR_MESSAGE,
    MAX_ROWID,
    MESSAGE_BY_GUID,
    MESSAGES_EDITED_SINCE,
    MESSAGES_SINCE_ROWID,
    RECENT_INBOUND,
    apple_ts_to_datetime,
    cutoff_apple_ts,
    format_chat_label,
    format_sender_label,
    messages_by_guids_sql,
)
from imsg_keep_deletes.paths import CACHE_TTL_SEC, CHAT_DB

# SQLite allows far more, but chunking keeps us clear of SQLITE_MAX_VARIABLE_NUMBER
# on older builds.
_GUID_CHUNK_SIZE = 400


@dataclass(frozen=True)
class DbMessage:
    rowid: int
    guid: str
    text: str
    raw_text: str | None
    has_attributed_body: bool
    sent_at: object
    date_edited: int
    is_empty: int
    sender: str
    chat: str
    attachment_paths: tuple[str, ...]


class ChatDbReader:
    def __init__(
        self,
        db_path: Path = CHAT_DB,
        contacts: ContactResolver | None = None,
    ) -> None:
        self.db_path = db_path
        self.contacts = contacts or ContactResolver()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_recent_inbound(self, seconds: int = CACHE_TTL_SEC) -> list[DbMessage]:
        with closing(self.connect()) as conn:
            rows = conn.execute(RECENT_INBOUND, (cutoff_apple_ts(seconds),)).fetchall()
            return [self._row_to_message(conn, row) for row in rows]

    def fetch_since_rowid(self, rowid: int) -> list[DbMessage]:
        with closing(self.connect()) as conn:
            rows = conn.execute(MESSAGES_SINCE_ROWID, (rowid,)).fetchall()
            return [self._row_to_message(conn, row) for row in rows]

    def fetch_edited_since(self, date_edited_after: int) -> list[DbMessage]:
        """Inbound messages whose date_edited advanced (includes unsends)."""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                MESSAGES_EDITED_SINCE, (date_edited_after,)
            ).fetchall()
            return [self._row_to_message(conn, row) for row in rows]

    def fetch_by_guid(self, guid: str) -> DbMessage | None:
        with closing(self.connect()) as conn:
            row = conn.execute(MESSAGE_BY_GUID, (guid,)).fetchone()
            if row is None:
                return None
            return self._row_to_message(conn, row)

    def fetch_states_by_guids(self, guids: list[str]) -> dict[str, DbMessage]:
        """Current DB state for many messages in one connection.

        Attachments are skipped: unsend detection only needs the content and
        edit flags, and callers already hold their own copies.
        """
        if not guids:
            return {}
        states: dict[str, DbMessage] = {}
        with closing(self.connect()) as conn:
            for start in range(0, len(guids), _GUID_CHUNK_SIZE):
                chunk = guids[start : start + _GUID_CHUNK_SIZE]
                rows = conn.execute(messages_by_guids_sql(len(chunk)), chunk).fetchall()
                for row in rows:
                    states[row["guid"]] = self._row_to_message(
                        conn, row, with_attachments=False
                    )
        return states

    def max_rowid(self) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute(MAX_ROWID).fetchone()
        return int(row[0] or 0)

    def _row_to_message(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        with_attachments: bool = True,
    ) -> DbMessage:
        raw_text = row["text"]
        attributed = row["attributedBody"]
        attachments: tuple[str, ...] = ()
        if with_attachments:
            attachments = tuple(
                self._resolve_attachment_path(att_row[0])
                for att_row in conn.execute(
                    ATTACHMENTS_FOR_MESSAGE, (row["ROWID"],)
                ).fetchall()
                if att_row[0]
            )
        handle_id = row["sender"] or ""
        chat_identifier = row["chat"] or ""
        display_name = row["display_name"] or ""
        room_name = row["room_name"] or ""
        chat_style = int(row["chat_style"] or 0)
        contact_name = self.contacts.resolve(handle_id)
        return DbMessage(
            rowid=row["ROWID"],
            guid=row["guid"],
            text=message_text(raw_text, attributed),
            raw_text=raw_text,
            has_attributed_body=bool(attributed),
            sent_at=apple_ts_to_datetime(row["date"]),
            date_edited=row["date_edited"] or 0,
            is_empty=row["is_empty"] or 0,
            sender=format_sender_label(
                handle_id,
                display_name,
                chat_style,
                chat_identifier,
                contact_name,
            ),
            chat=format_chat_label(
                display_name,
                chat_identifier,
                chat_style,
                room_name,
                contact_name,
            ),
            attachment_paths=attachments,
        )

    @staticmethod
    def _resolve_attachment_path(filename: str) -> str:
        path = Path(filename).expanduser()
        if path.is_file():
            return str(path)
        # chat.db often stores paths relative to ~/Library/Messages/
        fallback = Path.home() / "Library/Messages" / filename
        return str(fallback) if fallback.is_file() else filename
