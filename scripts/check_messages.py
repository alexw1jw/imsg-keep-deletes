#!/usr/bin/env python3
"""Quick check: read recent inbound messages from chat.db."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from imsg_keep_deletes.contacts.resolver import ContactResolver  # noqa: E402
from imsg_keep_deletes.db.reader import ChatDbReader  # noqa: E402


_FDA_HINT = """
macOS blocked access (Full Disk Access required).

1. Open System Settings → Privacy & Security → Full Disk Access
2. Add Cursor (or Terminal, if you use that)
3. Also add: /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
4. Quit and reopen Cursor, then run this script again.

The background daemon may still work even if this test script fails.
Check: imsg-kd status
"""


def main() -> None:
    contacts = ContactResolver()
    contacts.load()
    print(f"Contacts loaded: {contacts.available}\n")
    reader = ChatDbReader(contacts=contacts)
    try:
        messages = reader.fetch_recent_inbound(seconds=300)
    except Exception as exc:
        if "unable to open database file" in str(exc).lower():
            print(f"Error: {exc}", file=sys.stderr)
            print(_FDA_HINT, file=sys.stderr)
            sys.exit(1)
        raise
    print(f"Found {len(messages)} inbound messages in the last 5 minutes:\n")
    for msg in messages[-10:]:
        print(f"  [{msg.rowid}] {msg.sender} ({msg.chat}): {msg.text!r}")


if __name__ == "__main__":
    main()
