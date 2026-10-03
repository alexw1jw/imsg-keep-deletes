from datetime import datetime, timezone

from imsg_keep_deletes.db.reader import DbMessage
from imsg_keep_deletes.detector.unsend import is_unsent
from imsg_keep_deletes.models import MessageSnapshot


def _cached(**kwargs) -> MessageSnapshot:
    defaults = {
        "guid": "g1",
        "rowid": 1,
        "sender": "+15551234567",
        "chat": "+15551234567",
        "text": "hello",
        "sent_at": datetime.now(timezone.utc),
        "attachment_paths": (),
    }
    defaults.update(kwargs)
    return MessageSnapshot(**defaults)


def _current(**kwargs) -> DbMessage:
    defaults = {
        "rowid": 1,
        "guid": "g1",
        "text": "",
        "raw_text": None,
        "has_attributed_body": False,
        "sent_at": datetime.now(timezone.utc),
        "date_edited": 123456,
        "is_empty": 1,
        "sender": "+15551234567",
        "chat": "+15551234567",
        "attachment_paths": (),
    }
    defaults.update(kwargs)
    return DbMessage(**defaults)


def test_unsent_when_is_empty_set() -> None:
    assert is_unsent(_cached(), _current()) is True


def test_unsent_when_attributed_body_blob_remains() -> None:
    assert (
        is_unsent(
            _cached(),
            _current(has_attributed_body=True),
        )
        is True
    )


def test_not_unsent_when_hard_deleted() -> None:
    assert is_unsent(_cached(), None) is False


def test_not_unsent_when_never_had_content() -> None:
    assert is_unsent(_cached(text="", attachment_paths=()), _current()) is False


def test_not_unsent_without_is_empty_flag() -> None:
    assert is_unsent(_cached(), _current(is_empty=0, date_edited=0)) is False


def test_not_unsent_for_normal_edit() -> None:
    assert is_unsent(_cached(), _current(is_empty=0, date_edited=123456)) is False
