from __future__ import annotations

import requests

NYT_URL = "https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json"
PREFERRED_FORMATS = ["threeByTwoSmallAt2X", "mediumThreeByTwo440", "mediumThreeByTwo210"]
MEDIA_METADATA_FORMATS = ["mediumThreeByTwo440", "mediumThreeByTwo210", "Standard Thumbnail"]


def _pick_thumbnail(multimedia: list) -> str | None:
    if not multimedia:
        return None
    for fmt in PREFERRED_FORMATS:
        for item in multimedia:
            if item.get("format") == fmt:
                return item.get("url")
    return multimedia[0].get("url") if multimedia else None


def _pick_media_thumbnail(media: list) -> str | None:
    if not media:
        return None
    for item in media:
        metadata = item.get("media-metadata", [])
        for fmt in MEDIA_METADATA_FORMATS:
            for entry in metadata:
                if entry.get("format") == fmt:
                    return entry.get("url")
        if metadata:
            return metadata[0].get("url")
    return None


def nyt_block(api_key: str | None) -> list | None:
    if not api_key:
        return None
    try:
        resp = requests.get(NYT_URL, params={"api-key": api_key}, timeout=10)
        resp.raise_for_status()
        stories = resp.json().get("results", [])[:5]
        return [
            {
                "title": s.get("title", ""),
                "abstract": s.get("abstract", ""),
                "url": s.get("url", ""),
                "thumbnail": _pick_thumbnail(s.get("multimedia", [])) or _pick_media_thumbnail(s.get("media", [])),
            }
            for s in stories
        ]
    except Exception:
        return None
