import sqlite3
import time as time_module

from modules.messages import (
    _fallback_summary,
    _merge_threads,
    messages_block,
    needs_reply,
)


APPLE_EPOCH_OFFSET = 978307200


def apple_ts(unix_seconds: float) -> int:
    return int((unix_seconds - APPLE_EPOCH_OFFSET) * 1_000_000_000)


def test_needs_reply_true_when_last_is_from_them():
    now = time_module.time()
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
    assert messages_block() is None


def test_merge_threads_collapses_same_handle():
    merged = _merge_threads([
        {
            "name": "Gary Schwend",
            "handle": "+15555550101",
            "count": 6,
            "last_time": "7:04pm",
            "_last_ts": 10,
            "needs_reply": False,
            "snippet": "Old thread",
        },
        {
            "name": "Gary Schwend",
            "handle": "+15555550101",
            "count": 4,
            "last_time": "11:20am",
            "_last_ts": 5,
            "needs_reply": True,
            "snippet": "Newer logistics",
        },
    ])
    assert len(merged) == 1
    assert merged[0]["count"] == 10
    assert merged[0]["needs_reply"] is True


def test_fallback_summary_mentions_reply_count():
    summary = _fallback_summary([
        {"needs_reply": True},
        {"needs_reply": False},
        {"needs_reply": True},
    ])
    assert "loose ends" in summary
    assert "active conversations" not in summary


def test_messages_block_returns_summary_dict(mocker, tmp_path):
    db = tmp_path / "chat.db"
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
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
        INSERT INTO message VALUES (1, 1, 0, {now_apple}, 'Hey, can you call me back?', NULL);
        INSERT INTO chat_message_join VALUES (1, 1);
    """)
    con.close()

    mocker.patch("modules.messages.DB_PATH", str(db))
    mocker.patch("modules.messages.resolve_contact", return_value="Mom")
    mocker.patch("modules.messages._summarize_threads", return_value="Yesterday was mostly quick check-ins and one callback waiting in the wings.")

    result = messages_block("fake-key")

    assert result == {
        "summary": "Yesterday was mostly quick check-ins and one callback waiting in the wings.",
        "thread_count": 1,
        "needs_reply_count": 0,
    }
