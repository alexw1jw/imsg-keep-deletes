import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

logger = logging.getLogger(__name__)

def _phone_keys(value: str) -> list[str]:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return []
    keys = {digits}
    if len(digits) == 11 and digits.startswith("1"):
        keys.add(digits[1:])
    if len(digits) >= 10:
        keys.add(digits[-10:])
    return list(keys)


def _full_name(first: str | None, last: str | None) -> str:
    parts = [(first or "").strip(), (last or "").strip()]
    return " ".join(part for part in parts if part)


class ContactResolver:
    """Resolve phone numbers and emails to contact names via AddressBook SQLite."""

    def __init__(self) -> None:
        self._phones: dict[str, str] = {}
        self._emails: dict[str, str] = {}
        self._loaded = False
        self.available = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        paths = sorted(Path.home().glob(
            "Library/Application Support/AddressBook/Sources/*/AddressBook-*.abcddb"
        ))
        if not paths:
            logger.debug("No AddressBook databases found")
            return

        for path in paths:
            self._load_database(path)

        self.available = bool(self._phones or self._emails)
        if self.available:
            logger.info(
                "Loaded %d phone(s) and %d email(s) from Contacts",
                len(self._phones),
                len(self._emails),
            )

    def resolve(self, handle: str) -> str | None:
        if not handle:
            return None
        if not self._loaded:
            self.load()

        handle = handle.strip()
        if "@" in handle:
            return self._emails.get(handle.lower())

        for key in _phone_keys(handle):
            name = self._phones.get(key)
            if name:
                return name
        return None

    def _load_database(self, path: Path) -> None:
        try:
            with closing(
                sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            ) as conn:
                self._load_phones(conn)
                self._load_emails(conn)
        except sqlite3.Error as exc:
            logger.debug("Could not read AddressBook %s: %s", path, exc)

    def _load_phones(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT r.ZFIRSTNAME, r.ZLASTNAME, p.ZFULLNUMBER
            FROM ZABCDPHONENUMBER p
            JOIN ZABCDRECORD r ON p.ZOWNER = r.Z_PK
            WHERE p.ZFULLNUMBER IS NOT NULL
            """
        ).fetchall()
        for first, last, number in rows:
            name = _full_name(first, last)
            if not name:
                continue
            for key in _phone_keys(str(number)):
                self._phones.setdefault(key, name)

    def _load_emails(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT r.ZFIRSTNAME, r.ZLASTNAME, e.ZADDRESS
            FROM ZABCDEMAILADDRESS e
            JOIN ZABCDRECORD r ON e.ZOWNER = r.Z_PK
            WHERE e.ZADDRESS IS NOT NULL
            """
        ).fetchall()
        for first, last, address in rows:
            name = _full_name(first, last)
            email = (str(address) if address else "").strip().lower()
            if name and email:
                self._emails.setdefault(email, name)
