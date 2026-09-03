import pytest
import requests
from unittest.mock import patch

from modules.nyt import nyt_block, NYT_URL

NYT_RESPONSE = {
    "section": "home",
    "results": [
        {
            "section": "world",
            "title": "Big Story One",
            "abstract": "Something important happened.",
            "byline": "By Reporter One",
            "published_date": "2026-06-21T06:30:12-04:00",
            "url": "https://nytimes.com/story1",
            "multimedia": [{"url": "https://static.nyt.com/img1.jpg", "format": "threeByTwoSmallAt2X"}],
        },
        {
            "section": "business",
            "title": "Big Story Two",
            "abstract": "Something else happened.",
            "byline": "By Reporter Two",
            "published_date": "2026-06-20T18:00:00-04:00",
            "url": "https://nytimes.com/story2",
            "multimedia": {
                "caption": "A photo.",
                "default": {"url": "https://static.nyt.com/img2-default.jpg", "height": 400, "width": 600},
                "thumbnail": {"url": "https://static.nyt.com/img2-thumb.jpg", "height": 75, "width": 75},
            },
        },
        {
            "section": "opinion",
            "title": "Big Story Three",
            "abstract": "No art on this one.",
            "byline": "",
            "published_date": "2026-06-20T12:00:00-04:00",
            "url": "https://nytimes.com/story3",
            "multimedia": None,
        },
    ] + [
        {
            "title": f"Story {i}",
            "abstract": "...",
            "byline": "",
            "published_date": "2026-06-20T09:00:00-04:00",
            "url": f"https://nytimes.com/{i}",
            "multimedia": [],
        }
        for i in range(10)
    ]
}

def test_nyt_block_returns_top_5(requests_mock):
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert len(result) == 5
    assert result[0]["title"] == "Big Story One"

def test_nyt_block_hits_top_stories_endpoint(requests_mock):
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    nyt_block("test-key")
    assert requests_mock.last_request.path == "/svc/topstories/v2/home.json"

def test_nyt_block_includes_thumbnail_url(requests_mock):
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[0]["thumbnail"] == "https://static.nyt.com/img1.jpg"
    assert result[0]["byline"] == "By Reporter One"

def test_nyt_block_normalizes_published_timestamp_to_a_date(requests_mock):
    """Top Stories returns full ISO timestamps; the renderer ages a plain date."""
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[0]["published_date"] == "2026-06-21"

def test_nyt_block_reads_object_shaped_multimedia(requests_mock):
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[1]["thumbnail"] == "https://static.nyt.com/img2-default.jpg"

def test_nyt_block_tolerates_missing_multimedia(requests_mock):
    requests_mock.get(NYT_URL, json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[2]["thumbnail"] is None

def test_nyt_block_skips_entries_without_a_title_or_url(requests_mock):
    """Top Stories mixes in promo/placeholder rows that render as empty cards."""
    requests_mock.get(NYT_URL, json={"results": [
        {"title": "", "url": "https://nytimes.com/blank", "multimedia": []},
        {"title": "No link", "url": "", "multimedia": []},
        {"title": "Real Story", "abstract": "a", "url": "https://nytimes.com/real", "multimedia": []},
    ]})
    result = nyt_block("test-key")
    assert [s["title"] for s in result] == ["Real Story"]

def test_nyt_block_retries_on_transient_error(requests_mock):
    """A connection blip on the first attempt must not silently drop the section."""
    requests_mock.get(NYT_URL, [
        {"exc": requests.exceptions.ConnectionError},
        {"json": NYT_RESPONSE},
    ])
    with patch("modules.nyt.time.sleep"):
        result = nyt_block("test-key")
    assert len(result) == 5
    assert requests_mock.call_count == 2

def test_nyt_block_retries_on_retryable_status(requests_mock):
    requests_mock.get(NYT_URL, [
        {"status_code": 429},
        {"json": NYT_RESPONSE},
    ])
    with patch("modules.nyt.time.sleep"):
        result = nyt_block("test-key")
    assert len(result) == 5
    assert requests_mock.call_count == 2

def test_nyt_block_raises_after_retries_exhausted(requests_mock):
    """Persistent failure must raise so _safe() logs it — never vanish silently."""
    requests_mock.get(NYT_URL, status_code=503)
    with patch("modules.nyt.time.sleep"):
        with pytest.raises(requests.HTTPError):
            nyt_block("test-key")
    assert requests_mock.call_count == 3

def test_nyt_block_raises_immediately_on_non_retryable_status(requests_mock):
    requests_mock.get(NYT_URL, status_code=401)
    with pytest.raises(requests.HTTPError):
        nyt_block("test-key")
    assert requests_mock.call_count == 1

def test_nyt_block_returns_none_with_no_key():
    result = nyt_block(None)
    assert result is None
