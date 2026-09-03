from __future__ import annotations

import logging
import time
from datetime import date

import requests

log = logging.getLogger(__name__)

NYT_URL = "https://api.nytimes.com/svc/topstories/v2/home.json"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5.0
# Top Stories multimedia carries the same image at several crops. Prefer the 3:2
# crops the email's 175x117 slot is cut for, then the wider stand-ins, and leave
# the 75x75 "Standard Thumbnail" as a last resort — it upscales badly.
PREFERRED_FORMATS = [
    "mediumThreeByTwo210",
    "threeByTwoSmallAt2X",
    "mediumThreeByTwo440",
    "Normal",
    "superJumbo",
    "thumbLarge",
    "Standard Thumbnail",
]


def _pick_thumbnail(multimedia) -> str | None:
    """The documented shape is a list of format variants. The object shape with
    `default`/`thumbnail` children is undocumented here, but it is what the 2025
    multimedia rework did to the sibling NYT feeds, so absorb it rather than
    dropping every image the day it reaches this one."""
    if isinstance(multimedia, dict):
        for key in ("default", "thumbnail"):
            url = (multimedia.get(key) or {}).get("url")
            if url:
                return url
        return multimedia.get("url")
    if not multimedia:
        return None
    for fmt in PREFERRED_FORMATS:
        for item in multimedia:
            if item.get("format") == fmt:
                return item.get("url")
    return multimedia[0].get("url")


def _published_date(raw: str | None) -> str:
    """Top Stories publishes full ISO timestamps; the renderer wants a plain date
    it can age against. Slice rather than parse: the documented example offset is
    "-5:00", a single-digit hour that datetime.fromisoformat rejects outright."""
    if not raw:
        return ""
    candidate = raw[:10]
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return ""
    return candidate


def _fetch_results(api_key: str) -> list:
    """Fetch the home top stories, retrying transient failures. Raises on
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
    results = _fetch_results(api_key)
    stories = [s for s in results if s.get("title") and s.get("url")][:5]
    return [
        {
            "title": s.get("title", ""),
            "abstract": s.get("abstract", ""),
            "byline": s.get("byline", ""),
            "published_date": _published_date(s.get("published_date")),
            "url": s.get("url", ""),
            "thumbnail": _pick_thumbnail(s.get("multimedia")) or s.get("thumbnail_standard"),
        }
        for s in stories
    ]
