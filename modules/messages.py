from __future__ import annotations

import anthropic
import logging
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

DB_PATH = str(Path.home() / "Library" / "Messages" / "chat.db")
log = logging.getLogger(__name__)

# Apple's epoch offset: Mac absolute time starts 2001-01-01
APPLE_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01
MESSAGE_SYSTEM_PROMPT = (
    "You write a short, witty summary of the last day's conversations for a private personal newsletter. "
    "Two sentences max. Focus on themes, logistics, mood, or social texture rather than listing every thread. "
    "Do not over-index on message volume. Do not foreground unknown numbers unless they are clearly central. "
    "Do not invent facts, relationships, ages, or backstory. If labels seem stale or ambiguous, stay generic."
)


def contacts_access_granted(prompt: bool = False) -> bool:
    try:
        import Contacts
    except Exception:
        return False

    store = Contacts.CNContactStore.alloc().init()
    status = Contacts.CNContactStore.authorizationStatusForEntityType_(Contacts.CNEntityTypeContacts)
    if status == Contacts.CNAuthorizationStatusAuthorized:
        return True

    if not prompt or status == Contacts.CNAuthorizationStatusDenied:
        return False

    if hasattr(Contacts, "CNAuthorizationStatusLimited") and status == Contacts.CNAuthorizationStatusLimited:
        return True

    granted_holder = {"value": False}
    finished = threading.Event()

    def completion(granted, error):
        granted_holder["value"] = bool(granted)
        finished.set()

    store.requestAccessForEntityType_completionHandler_(Contacts.CNEntityTypeContacts, completion)
    finished.wait(timeout=10)
    return granted_holder["value"]


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
    """Resolve a phone number or email to a contact name."""
    try:
        import Contacts

        if contacts_access_granted(prompt=False):
            store = Contacts.CNContactStore.alloc().init()
            keys = [
                Contacts.CNContactGivenNameKey,
                Contacts.CNContactFamilyNameKey,
                Contacts.CNContactPhoneNumbersKey,
                Contacts.CNContactEmailAddressesKey,
            ]
            request = Contacts.CNContactFetchRequest.alloc().initWithKeysToFetch_(keys)
            normalized = (
                handle_id.replace("+1", "")
                .replace("-", "")
                .replace(" ", "")
                .replace("(", "")
                .replace(")", "")
            )
            match = {"name": None}

            def visit(contact, stop_ptr):
                for labeled_value in contact.phoneNumbers() or []:
                    value = str(labeled_value.value().stringValue())
                    candidate = (
                        value.replace("+1", "")
                        .replace("-", "")
                        .replace(" ", "")
                        .replace("(", "")
                        .replace(")", "")
                    )
                    if candidate == normalized:
                        first = contact.givenName() or ""
                        last = contact.familyName() or ""
                        match["name"] = f"{first} {last}".strip() or None
                        stop_ptr[0] = True
                        return
                for email in contact.emailAddresses() or []:
                    if str(email.value()).lower() == handle_id.lower():
                        first = contact.givenName() or ""
                        last = contact.familyName() or ""
                        match["name"] = f"{first} {last}".strip() or None
                        stop_ptr[0] = True
                        return

            store.enumerateContactsWithFetchRequest_error_usingBlock_(request, None, visit)
            if match["name"]:
                return match["name"]
    except Exception:
        log.warning("Failed to resolve contact via Contacts for handle %r", handle_id, exc_info=True)

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
        log.warning("Failed to resolve contact for handle %r", handle_id, exc_info=True)
        return None


def _clean_snippet(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    return cleaned[:140] if cleaned else None


def _chat_has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row["name"] for row in rows}
    return column in names


def _threads_from_db() -> list | None:
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except Exception:
        log.warning("Unable to open Messages database at %s", DB_PATH, exc_info=True)
        return None

    try:
        cutoff_apple = (time.time() - APPLE_EPOCH_OFFSET - 86400) * 1_000_000_000
        chat_name_select = "c.display_name AS chat_name," if _chat_has_column(con, "chat", "display_name") else "NULL AS chat_name,"

        rows = con.execute(f"""
            SELECT
                c.chat_identifier,
                {chat_name_select}
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
                threads[chat_id] = {
                    "handle": handle,
                    "chat_name": (row["chat_name"] or "").strip(),
                    "messages": [],
                    "count": 0,
                    "snippet": None,
                }
            threads[chat_id]["messages"].append({
                "is_from_me": bool(row["is_from_me"]),
                "timestamp": row["ts"],
            })
            threads[chat_id]["count"] += 1
            snippet = _clean_snippet(row["text"])
            if snippet:
                threads[chat_id]["snippet"] = snippet

        result = []
        for chat_id, data in threads.items():
            handle = data["handle"]
            chat_name = data["chat_name"]
            name = chat_name or resolve_contact(handle)
            is_contact = bool(chat_name or name is not None)
            if not name:
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
                "snippet": data["snippet"],
            })

        # Sort: contacts first, then most recent message first
        result.sort(key=lambda t: (not t["is_contact"], -t["_last_ts"]))
        # Remove the internal sort key before returning
        for t in result:
            t.pop("_last_ts", None)
        return result if result else []

    except Exception:
        log.warning("Failed to build messages block from %s", DB_PATH, exc_info=True)
        return None
    finally:
        con.close()


def _merge_threads(threads: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for thread in threads:
        key = (thread.get("handle") or thread.get("name") or "").strip().lower()
        if not key:
            key = f"unknown:{thread.get('last_time','')}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = {
                "name": thread["name"],
                "count": thread["count"],
                "last_time": thread["last_time"],
                "_last_ts": thread.get("_last_ts", 0),
                "needs_reply": thread["needs_reply"],
                "snippets": [thread["snippet"]] if thread.get("snippet") else [],
            }
            continue
        existing["count"] += thread["count"]
        existing["needs_reply"] = existing["needs_reply"] or thread["needs_reply"]
        if thread.get("_last_ts", 0) > existing["_last_ts"]:
            existing["_last_ts"] = thread["_last_ts"]
            existing["last_time"] = thread["last_time"]
            existing["name"] = thread["name"]
        if thread.get("snippet") and thread["snippet"] not in existing["snippets"]:
            existing["snippets"].append(thread["snippet"])

    result = list(merged.values())
    result.sort(key=lambda t: -t["_last_ts"])
    for thread in result:
        thread.pop("_last_ts", None)
    return result


def _fallback_summary(threads: list[dict]) -> str:
    needs_reply_count = sum(1 for thread in threads if thread["needs_reply"])
    if needs_reply_count:
        return "Yesterday's conversations were mostly logistics and check-ins, with a couple of loose ends still waiting on you."
    return "Yesterday's conversations were mostly the usual swirl of logistics, check-ins, and background social weather."


def _summarize_threads(api_key: str | None, threads: list[dict]) -> str | None:
    if not threads:
        return None
    if not api_key:
        return _fallback_summary(threads)

    lines = []
    for thread in threads[:8]:
        flags = []
        if thread["needs_reply"]:
            flags.append("needs reply")
        if not thread.get("handle") and thread["name"] == "Unknown":
            flags.append("ambiguous label")
        snippet = thread.get("snippet")
        snippet_text = f" snippet: {snippet}" if snippet else ""
        flag_text = f" ({', '.join(flags)})" if flags else ""
        lines.append(
            f"- {thread['name']}: last active {thread['last_time']}{flag_text}.{snippet_text}"
        )

    prompt = (
        "Summarize these message threads from the last 24 hours for a private personal morning email. "
        "Keep it to one or two witty sentences. Prefer themes over exhaustive detail. "
        "Use message counts only if they materially change the interpretation of the day.\n\n"
        + "\n".join(lines)
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=MESSAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        log.warning("Failed to summarize message threads with Anthropic", exc_info=True)
        return _fallback_summary(threads)


def messages_block(api_key: str | None = None) -> dict | None:
    threads = _threads_from_db()
    if threads is None:
        return None
    merged = _merge_threads(threads)
    if not merged:
        return {"summary": "No meaningful conversation traffic in the last day.", "thread_count": 0, "needs_reply_count": 0}
    return {
        "summary": _summarize_threads(api_key, merged),
        "thread_count": len(merged),
        "needs_reply_count": sum(1 for thread in merged if thread["needs_reply"]),
    }
