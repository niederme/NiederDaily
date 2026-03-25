import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = str(Path.home() / "Library" / "Messages" / "chat.db")

# Apple's epoch offset: Mac absolute time starts 2001-01-01
APPLE_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01


def _apple_ts_to_unix(apple_ns: int) -> float:
    """Convert Apple nanosecond timestamp to Unix seconds."""
    return (apple_ns / 1_000_000_000) + APPLE_EPOCH_OFFSET


def needs_reply(messages: list) -> bool:
    """True if the last message was from them and >2 hours ago."""
    if not messages:
        return False
    last = max(messages, key=lambda m: m["timestamp"])
    if last["is_from_me"]:
        return False
    unix_ts = _apple_ts_to_unix(last["timestamp"])
    hours_ago = (time.time() - unix_ts) / 3600
    return hours_ago > 2


def resolve_contact(handle_id: str) -> str | None:
    """Resolve a phone number or email to a contact name via AddressBook."""
    try:
        import AddressBook
        book = AddressBook.ABAddressBook.sharedAddressBook()
        if book is None:
            return None
        search = (handle_id
                  .replace("+1", "").replace("-", "")
                  .replace(" ", "").replace("(", "").replace(")", ""))
        for person in book.people():
            phones = person.valueForProperty_(AddressBook.kABPhoneProperty)
            if phones:
                for i in range(phones.count()):
                    val = (phones.valueAtIndex_(i)
                           .replace("+1", "").replace("-", "")
                           .replace(" ", "").replace("(", "").replace(")", ""))
                    if val == search:
                        first = person.valueForProperty_(AddressBook.kABFirstNameProperty) or ""
                        last = person.valueForProperty_(AddressBook.kABLastNameProperty) or ""
                        return f"{first} {last}".strip() or None
            emails = person.valueForProperty_(AddressBook.kABEmailProperty)
            if emails:
                for i in range(emails.count()):
                    if emails.valueAtIndex_(i).lower() == handle_id.lower():
                        first = person.valueForProperty_(AddressBook.kABFirstNameProperty) or ""
                        last = person.valueForProperty_(AddressBook.kABLastNameProperty) or ""
                        return f"{first} {last}".strip() or None
        return None
    except Exception:
        return None


def messages_block() -> list | None:
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except Exception:
        return None

    try:
        cutoff_apple = (time.time() - APPLE_EPOCH_OFFSET - 86400) * 1_000_000_000

        rows = con.execute("""
            SELECT
                c.chat_identifier,
                h.id AS handle_id,
                m.is_from_me,
                m.date AS ts,
                m.text
            FROM message m
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            JOIN chat c ON c.ROWID = cmj.chat_id
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            WHERE m.date > ?
            ORDER BY m.date ASC
        """, (cutoff_apple,)).fetchall()

        threads: dict[str, dict] = {}
        for row in rows:
            chat_id = row["chat_identifier"]
            handle = row["handle_id"] or ""
            if chat_id not in threads:
                threads[chat_id] = {"handle": handle, "messages": [], "count": 0}
            threads[chat_id]["messages"].append({
                "is_from_me": bool(row["is_from_me"]),
                "timestamp": row["ts"],
            })
            threads[chat_id]["count"] += 1

        result = []
        for chat_id, data in threads.items():
            handle = data["handle"]
            name = resolve_contact(handle)
            is_contact = name is not None
            if name is None:
                name = handle if handle else "Unknown"

            last_msg = max(data["messages"], key=lambda m: m["timestamp"])
            last_unix = _apple_ts_to_unix(last_msg["timestamp"])
            last_time = datetime.fromtimestamp(last_unix)

            result.append({
                "name": name,
                "handle": handle,
                "is_contact": is_contact,
                "count": data["count"],
                "last_time": last_time.strftime("%-I:%M%p").lower(),
                "_last_ts": last_unix,
                "needs_reply": needs_reply(data["messages"]),
            })

        # Sort: contacts first, then most recent message first
        result.sort(key=lambda t: (not t["is_contact"], -t["_last_ts"]))
        # Remove the internal sort key before returning
        for t in result:
            t.pop("_last_ts", None)
        return result if result else []

    except Exception:
        return None
    finally:
        con.close()
