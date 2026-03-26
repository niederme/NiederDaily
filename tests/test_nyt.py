import pytest

from modules.nyt import nyt_block

NYT_RESPONSE = {
    "results": [
        {
            "title": "Big Story One",
            "abstract": "Something important happened.",
            "byline": "By Reporter One",
            "url": "https://nytimes.com/story1",
            "multimedia": [{"url": "https://static.nyt.com/img1.jpg", "format": "threeByTwoSmallAt2X"}],
        },
        {
            "title": "Big Story Two",
            "abstract": "Something else happened.",
            "byline": "By Reporter Two",
            "url": "https://nytimes.com/story2",
            "multimedia": [],
            "media": [
                {
                    "type": "image",
                    "media-metadata": [
                        {"url": "https://static.nyt.com/thumb.jpg", "format": "Standard Thumbnail"},
                        {"url": "https://static.nyt.com/img2-210.jpg", "format": "mediumThreeByTwo210"},
                        {"url": "https://static.nyt.com/img2-440.jpg", "format": "mediumThreeByTwo440"},
                    ],
                }
            ],
        },
    ] + [{"title": f"Story {i}", "abstract": "...", "byline": "", "url": f"https://nytimes.com/{i}", "multimedia": [], "media": []} for i in range(10)]
}

def test_nyt_block_returns_top_5(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert len(result) == 5

def test_nyt_block_includes_thumbnail_url(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[0]["thumbnail"] == "https://static.nyt.com/img1.jpg"
    assert result[0]["byline"] == "By Reporter One"

def test_nyt_block_uses_media_metadata_thumbnail_when_multimedia_missing(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[1]["thumbnail"] == "https://static.nyt.com/img2-210.jpg"

def test_nyt_block_returns_none_on_api_error(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json", status_code=429)
    result = nyt_block("test-key")
    assert result is None

def test_nyt_block_returns_none_with_no_key():
    result = nyt_block(None)
    assert result is None
