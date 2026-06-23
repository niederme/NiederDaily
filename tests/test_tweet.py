import json
import subprocess
from datetime import date, timedelta
from unittest.mock import patch

from modules import tweet as tweet_mod
from modules.tweet import tweet_block


def _row(text, *, tweet_id="1", handle="someone", display="Someone", created=None,
         likes=0, liked=False, bookmarked=False):
    return {
        "id": tweet_id,
        "accountHandle": "@john",
        "text": text,
        "createdAt": created,
        "likeCount": likes,
        "liked": liked,
        "bookmarked": bookmarked,
        "author": {"handle": handle, "displayName": display},
    }


def _completed(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _iso_on_this_day(years_ago):
    today = date.today()
    # Use a fixed past year to avoid Feb 29 edge cases in tests.
    return f"{today.year - years_ago:04d}-{today.month:02d}-{today.day:02d}T14:30:00.000Z"


def _search_dispatch(responses):
    """Return a fake subprocess.run that keys off the search flags."""
    def fake_run(cmd, **kwargs):
        if "--resource" in cmd and "authored" in cmd:
            return _completed(json.dumps(responses.get("authored", [])))
        if "--bookmarked" in cmd:
            return _completed(json.dumps(responses.get("bookmarked", [])))
        if "--liked" in cmd:
            return _completed(json.dumps(responses.get("liked", [])))
        return _completed("[]")
    return fake_run


def test_prefers_on_this_day_authored_tweet():
    responses = {
        "authored": [
            _row("Off-day rambling", tweet_id="10", handle="john",
                 created="2021-01-02T10:00:00.000Z"),
            _row("Three years ago today", tweet_id="11", handle="john",
                 display="John", created=_iso_on_this_day(3)),
        ],
        "bookmarked": [_row("a save", bookmarked=True, created=_iso_on_this_day(0))],
    }
    with patch("modules.tweet.subprocess.run", side_effect=_search_dispatch(responses)):
        result = tweet_block()
    assert result["source"] == "authored"
    assert result["text"] == "Three years ago today"
    assert result["url"] == "https://twitter.com/john/status/11"
    assert result["year"] == str(date.today().year - 3)


def test_picks_oldest_when_multiple_on_this_day():
    responses = {
        "authored": [
            _row("Two years ago", tweet_id="20", handle="john", created=_iso_on_this_day(2)),
            _row("Five years ago", tweet_id="21", handle="john", created=_iso_on_this_day(5)),
        ],
    }
    with patch("modules.tweet.subprocess.run", side_effect=_search_dispatch(responses)):
        result = tweet_block()
    assert result["text"] == "Five years ago"


def test_falls_back_to_recent_bookmark_when_no_authored_match():
    responses = {
        "authored": [_row("Unrelated day", tweet_id="30", handle="john",
                          created="2020-01-01T00:00:00.000Z")],
        "bookmarked": [
            _row("Older save", tweet_id="31", created="2026-06-01T00:00:00.000Z", bookmarked=True),
            _row("Newest save", tweet_id="32", handle="dhh", display="DHH",
                 created="2026-06-22T00:00:00.000Z", bookmarked=True),
        ],
    }
    with patch("modules.tweet.subprocess.run", side_effect=_search_dispatch(responses)):
        result = tweet_block()
    assert result["source"] == "bookmarked"
    assert result["text"] == "Newest save"
    assert result["display_name"] == "DHH"


def test_falls_back_to_likes_when_no_bookmarks():
    responses = {
        "authored": [],
        "bookmarked": [],
        "liked": [_row("A liked tweet", tweet_id="40", handle="patio11",
                       created="2026-06-20T00:00:00.000Z", liked=True)],
    }
    with patch("modules.tweet.subprocess.run", side_effect=_search_dispatch(responses)):
        result = tweet_block()
    assert result["source"] == "liked"
    assert result["text"] == "A liked tweet"


def test_as_of_overrides_on_this_day_match():
    # An authored tweet whose month/day matches a *chosen* date, not today.
    responses = {
        "authored": [
            _row("Authored on April 1", tweet_id="50", handle="john",
                 created="2019-04-01T09:00:00.000Z"),
        ],
        "bookmarked": [_row("a recent save", tweet_id="51", bookmarked=True,
                            created="2026-06-01T00:00:00.000Z")],
    }
    with patch("modules.tweet.subprocess.run", side_effect=_search_dispatch(responses)):
        result = tweet_block(as_of=date(2026, 4, 1))
    assert result["source"] == "authored"
    assert result["text"] == "Authored on April 1"


def test_returns_none_when_birdclaw_missing():
    with patch("modules.tweet.subprocess.run", side_effect=FileNotFoundError()):
        assert tweet_block() is None


def test_returns_none_on_command_failure():
    with patch("modules.tweet.subprocess.run", return_value=_completed("", returncode=1, stderr="boom")):
        assert tweet_block() is None


def test_returns_none_on_nonjson_output():
    with patch("modules.tweet.subprocess.run", return_value=_completed("not json")):
        assert tweet_block() is None


def test_returns_none_when_store_empty():
    with patch("modules.tweet.subprocess.run", return_value=_completed("[]")):
        assert tweet_block() is None


def test_timeout_is_handled():
    with patch("modules.tweet.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="birdclaw", timeout=30)):
        assert tweet_block() is None
