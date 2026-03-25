import pytest
from unittest.mock import patch, MagicMock
import sqlite3
import time as time_module

from modules.messages import messages_block, resolve_contact, needs_reply

# Apple's epoch: Mac absolute time starts 2001-01-01
APPLE_EPOCH_OFFSET = 978307200

def apple_ts(unix_seconds: float) -> int:
    """Convert Unix seconds to Apple nanoseconds."""
    return int((unix_seconds - APPLE_EPOCH_OFFSET) * 1_000_000_000)


def test_needs_reply_true_when_last_is_from_them():
    now = time_module.time()
    # Last message from them, 3 hours ago
    messages = [{"is_from_me": False, "timestamp": apple_ts(now - 10800)}]
    assert needs_reply(messages) is True

def test_needs_reply_false_when_last_is_from_me():
    now = time_module.time()
    messages = [
        {"is_from_me": False, "timestamp": apple_ts(now - 10800)},
        {"is_from_me": True, "timestamp": apple_ts(now - 3600)},
    ]
    assert needs_reply(messages) is False

def test_needs_reply_false_within_2_hours():
    now = time_module.time()
    messages = [{"is_from_me": False, "timestamp": apple_ts(now - 3600)}]
    assert needs_reply(messages) is False

def test_messages_block_returns_none_when_db_missing(mocker):
    mocker.patch("modules.messages.DB_PATH", "/nonexistent/chat.db")
    result = messages_block()
    assert result is None

def test_messages_block_filters_to_contacts_and_shows_raw_handle_fallback(mocker, tmp_path):
    db = tmp_path / "chat.db"
    con = sqlite3.connect(str(db))
    now_apple = apple_ts(time_module.time() - 3600)
    con.executescript(f"""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, handle_id INTEGER,
            is_from_me INTEGER, date INTEGER, text TEXT, cache_roomnames TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        INSERT INTO handle VALUES (1, '+15555550101');
        INSERT INTO chat VALUES (1, 'iMessage;-;+15555550101');
        INSERT INTO chat_handle_join VALUES (1, 1);
        INSERT INTO message VALUES (1, 1, 0, {now_apple}, 'Hey!', NULL);
        INSERT INTO chat_message_join VALUES (1, 1);
    """)
    con.close()

    mocker.patch("modules.messages.DB_PATH", str(db))
    # resolve_contact returns "Mom" for this handle
    mocker.patch("modules.messages.resolve_contact", return_value="Mom")

    result = messages_block()
    assert result is not None
    assert len(result) == 1
    assert result[0]["name"] == "Mom"
    assert result[0]["needs_reply"] is False  # only 1 hour ago
    assert result[0]["count"] == 1

def test_messages_block_needs_reply_flag(mocker, tmp_path):
    db = tmp_path / "chat.db"
    con = sqlite3.connect(str(db))
    # Message from 4 hours ago (needs reply)
    old_apple = apple_ts(time_module.time() - 14400)
    con.executescript(f"""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, handle_id INTEGER,
            is_from_me INTEGER, date INTEGER, text TEXT, cache_roomnames TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        INSERT INTO handle VALUES (1, '+15555550101');
        INSERT INTO chat VALUES (1, 'iMessage;-;+15555550101');
        INSERT INTO chat_handle_join VALUES (1, 1);
        INSERT INTO message VALUES (1, 1, 0, {old_apple}, 'Call me', NULL);
        INSERT INTO chat_message_join VALUES (1, 1);
    """)
    con.close()

    mocker.patch("modules.messages.DB_PATH", str(db))
    mocker.patch("modules.messages.resolve_contact", return_value="Dad")

    result = messages_block()
    assert result[0]["needs_reply"] is True
    assert result[0]["name"] == "Dad"
