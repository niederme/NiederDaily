import pytest

from modules.nyt import nyt_block

NYT_RESPONSE = {
    "results": [
        {
            "title": "Big Story One",
            "abstract": "Something important happened.",
            "url": "https://nytimes.com/story1",
            "multimedia": [{"url": "https://static.nyt.com/img1.jpg", "format": "threeByTwoSmallAt2X"}],
        },
        {
            "title": "Big Story Two",
            "abstract": "Something else happened.",
            "url": "https://nytimes.com/story2",
            "multimedia": [],
        },
    ] + [{"title": f"Story {i}", "abstract": "...", "url": f"https://nytimes.com/{i}", "multimedia": []} for i in range(10)]
}

def test_nyt_block_returns_top_5(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert len(result) == 5

def test_nyt_block_includes_thumbnail_url(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[0]["thumbnail"] == "https://static.nyt.com/img1.jpg"

def test_nyt_block_thumbnail_none_when_missing(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[1]["thumbnail"] is None

def test_nyt_block_returns_none_on_api_error(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", status_code=429)
    result = nyt_block("test-key")
    assert result is None

def test_nyt_block_returns_none_with_no_key():
    result = nyt_block(None)
    assert result is None
