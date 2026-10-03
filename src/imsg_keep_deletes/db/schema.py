from datetime import datetime, timedelta, timezone

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

# chat.style 43 = group thread in Messages chat.db
GROUP_CHAT_STYLE = 43

RECENT_INBOUND = """
SELECT
    m.ROWID,
    m.guid,
    m.text,
    m.attributedBody,
    m.date,
    m.date_edited,
    m.is_empty,
    COALESCE(h.id, '') AS sender,
    COALESCE(c.chat_identifier, '') AS chat,
    COALESCE(c.display_name, '') AS display_name,
    COALESCE(c.room_name, '') AS room_name,
    COALESCE(c.style, 0) AS chat_style
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
LEFT JOIN chat c ON cmj.chat_id = c.ROWID
WHERE m.is_from_me = 0
  AND m.date > ?
ORDER BY m.ROWID ASC
"""

MESSAGES_SINCE_ROWID = """
SELECT
    m.ROWID,
    m.guid,
    m.text,
    m.attributedBody,
    m.date,
    m.date_edited,
    m.is_empty,
    COALESCE(h.id, '') AS sender,
    COALESCE(c.chat_identifier, '') AS chat,
    COALESCE(c.display_name, '') AS display_name,
    COALESCE(c.room_name, '') AS room_name,
    COALESCE(c.style, 0) AS chat_style
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
LEFT JOIN chat c ON cmj.chat_id = c.ROWID
WHERE m.is_from_me = 0
  AND m.ROWID > ?
ORDER BY m.ROWID ASC
"""

MESSAGE_BY_GUID = """
SELECT
    m.ROWID,
    m.guid,
    m.text,
    m.attributedBody,
    m.date,
    m.date_edited,
    m.is_empty,
    COALESCE(h.id, '') AS sender,
    COALESCE(c.chat_identifier, '') AS chat,
    COALESCE(c.display_name, '') AS display_name,
    COALESCE(c.room_name, '') AS room_name,
    COALESCE(c.style, 0) AS chat_style
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
LEFT JOIN chat c ON cmj.chat_id = c.ROWID
WHERE m.guid = ?
"""

MESSAGES_BY_GUIDS = """
SELECT
    m.ROWID,
    m.guid,
    m.text,
    m.attributedBody,
    m.date,
    m.date_edited,
    m.is_empty,
    COALESCE(h.id, '') AS sender,
    COALESCE(c.chat_identifier, '') AS chat,
    COALESCE(c.display_name, '') AS display_name,
    COALESCE(c.room_name, '') AS room_name,
    COALESCE(c.style, 0) AS chat_style
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
LEFT JOIN chat c ON cmj.chat_id = c.ROWID
WHERE m.guid IN ({placeholders})
"""

ATTACHMENTS_FOR_MESSAGE = """
SELECT a.filename
FROM attachment a
JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
WHERE maj.message_id = ?
"""

MAX_ROWID = "SELECT MAX(ROWID) FROM message"

MESSAGES_EDITED_SINCE = """
SELECT
    m.ROWID,
    m.guid,
    m.text,
    m.attributedBody,
    m.date,
    m.date_edited,
    m.is_empty,
    COALESCE(h.id, '') AS sender,
    COALESCE(c.chat_identifier, '') AS chat,
    COALESCE(c.display_name, '') AS display_name,
    COALESCE(c.room_name, '') AS room_name,
    COALESCE(c.style, 0) AS chat_style
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
LEFT JOIN chat c ON cmj.chat_id = c.ROWID
WHERE m.is_from_me = 0
  AND m.date_edited > ?
  AND m.date_edited > 0
ORDER BY m.date_edited ASC
"""


def messages_by_guids_sql(count: int) -> str:
    return MESSAGES_BY_GUIDS.format(placeholders=",".join("?" * count))


def apple_ts_to_datetime(ts: int) -> datetime:
    if not ts:
        return APPLE_EPOCH
    return APPLE_EPOCH + timedelta(seconds=ts / 1_000_000_000)


def datetime_to_apple_ts(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - APPLE_EPOCH
    return int(delta.total_seconds() * 1_000_000_000)


def cutoff_apple_ts(seconds_ago: int) -> int:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return datetime_to_apple_ts(dt)


def is_group_chat(chat_identifier: str, chat_style: int) -> bool:
    ident = (chat_identifier or "").strip()
    return chat_style == GROUP_CHAT_STYLE or ident.startswith("chat")


def format_chat_label(
    display_name: str,
    chat_identifier: str,
    chat_style: int,
    room_name: str = "",
    contact_name: str | None = None,
) -> str:
    for candidate in (display_name, room_name):
        cleaned = (candidate or "").strip()
        if cleaned:
            return cleaned

    ident = (chat_identifier or "").strip()
    if is_group_chat(ident, chat_style) and ident.startswith("chat"):
        return "Group chat"

    contact = (contact_name or "").strip()
    if contact and not is_group_chat(ident, chat_style):
        return contact

    return ident or "unknown"


def format_sender_label(
    handle_id: str,
    display_name: str,
    chat_style: int,
    chat_identifier: str = "",
    contact_name: str | None = None,
) -> str:
    handle = (handle_id or "").strip() or "unknown"
    contact = (contact_name or "").strip()
    if contact:
        return contact

    if is_group_chat(chat_identifier, chat_style):
        return handle

    name = (display_name or "").strip()
    return name or handle
