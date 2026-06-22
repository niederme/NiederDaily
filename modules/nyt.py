from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

NYT_URL = "https://api.nytimes.com/svc/mostpopular/v2/viewed/7.json"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5.0
PREFERRED_FORMATS = ["mediumThreeByTwo210", "threeByTwoSmallAt2X", "mediumThreeByTwo440"]
MEDIA_METADATA_FORMATS = ["mediumThreeByTwo210", "mediumThreeByTwo440", "Standard Thumbnail"]


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


def _fetch_results(api_key: str) -> list:
    """Fetch most-viewed stories, retrying transient failures. Raises on
    persistent failure so the orchestrator's _safe() wrapper logs it —
    a silently missing section is undiagnosable."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(NYT_URL, params={"api-key": api_key}, timeout=10)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            status = exc.response.status_code if isinstance(exc, requests.HTTPError) else None
            retryable = status is None or status in RETRYABLE_STATUSES
            if retryable and attempt < MAX_ATTEMPTS:
                log.warning("NYT fetch attempt %s/%s failed (%s); retrying.", attempt, MAX_ATTEMPTS, exc)
                time.sleep(RETRY_DELAY_SECONDS * attempt)
                continue
            raise


def nyt_block(api_key: str | None) -> list | None:
    if not api_key:
        return None
    stories = _fetch_results(api_key)[:5]
    return [
        {
            "title": s.get("title", ""),
            "abstract": s.get("abstract", ""),
            "byline": s.get("byline", ""),
            "published_date": s.get("published_date", ""),
            "url": s.get("url", ""),
            "thumbnail": _pick_thumbnail(s.get("multimedia", [])) or _pick_media_thumbnail(s.get("media", [])),
        }
        for s in stories
    ]
