from __future__ import annotations

import json
import logging
import subprocess
from datetime import date, datetime

log = logging.getLogger(__name__)

BIRDCLAW_BIN = "birdclaw"
# How many authored tweets to scan when hunting for on-this-day matches.
AUTHORED_SCAN_LIMIT = 400
# How many recent saves to consider for the fallback pick.
FALLBACK_LIMIT = 25
TIMEOUT_SECONDS = 30


def _run_search(args: list[str]) -> list | None:
    """Run `birdclaw --json search tweets <args>` and return parsed rows.

    Returns None when birdclaw is unavailable or the command fails, so the
    orchestrator simply skips the section — mirrors how the photo module
    returns None when the local source can't be read.
    """
    try:
        result = subprocess.run(
            [BIRDCLAW_BIN, "--json", "search", "tweets", *args],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        log.warning("birdclaw CLI not found on PATH; skipping tweet block")
        return None
    except subprocess.TimeoutExpired:
        log.warning("birdclaw search timed out; skipping tweet block")
        return None

    if result.returncode != 0:
        log.warning(
            "birdclaw search failed: %s",
            result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}",
        )
        return None

    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        log.warning("birdclaw returned non-JSON output; skipping tweet block")
        return None
    return data if isinstance(data, list) else []


def _parse_created(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        # birdclaw emits ISO 8601 with a trailing Z.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize(row: dict, source: str) -> dict | None:
    """Flatten a birdclaw tweet row into the shape the renderer expects."""
    text = (row.get("text") or "").strip()
    if not text:
        return None
    author = row.get("author") or {}
    handle = (author.get("handle") or row.get("accountHandle") or "").lstrip("@")
    created = _parse_created(row.get("createdAt"))
    tweet_id = str(row.get("id") or "")
    url = f"https://twitter.com/{handle}/status/{tweet_id}" if handle and tweet_id else ""
    return {
        "id": tweet_id,
        "text": text,
        "handle": handle,
        "display_name": author.get("displayName") or (f"@{handle}" if handle else ""),
        "date": created.date().isoformat() if created else None,
        "year": str(created.year) if created else "",
        "like_count": int(row.get("likeCount") or 0),
        "url": url,
        "source": source,  # "authored" | "bookmarked" | "liked"
    }


def _on_this_day_authored() -> dict | None:
    """Prefer one of John's own tweets posted on this calendar day in a past year."""
    rows = _run_search(["--resource", "authored", "--limit", str(AUTHORED_SCAN_LIMIT)])
    if not rows:
        return None
    today = date.today()
    matches: list[tuple[datetime, dict]] = []
    for row in rows:
        created = _parse_created(row.get("createdAt"))
        if created is None:
            continue
        if (created.month, created.day) == (today.month, today.day) and created.year < today.year:
            normalized = _normalize(row, "authored")
            if normalized:
                matches.append((created, normalized))
    if not matches:
        return None
    # Oldest match wins — the most nostalgic look back.
    matches.sort(key=lambda m: m[0])
    return matches[0][1]


def _recent_save() -> dict | None:
    """Fallback: the most recent thing John bookmarked, else liked."""
    for flag, source in (("--bookmarked", "bookmarked"), ("--liked", "liked")):
        rows = _run_search([flag, "--limit", str(FALLBACK_LIMIT)])
        if not rows:
            continue
        candidates: list[tuple[float, dict]] = []
        for row in rows:
            normalized = _normalize(row, source)
            if not normalized:
                continue
            created = _parse_created(row.get("createdAt"))
            key = created.timestamp() if created else 0.0
            candidates.append((key, normalized))
        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            return candidates[0][1]
    return None


def tweet_block() -> dict | None:
    """Pick the tweet of the day from the local birdclaw store.

    Reads whatever is already synced into ~/.birdclaw — keeping live syncing a
    separate concern, the same way the photo module reads the local Photos
    library. Selection mirrors the on-this-day photo: prefer one of John's own
    tweets from this date in a past year, otherwise surface a recent save.
    """
    return _on_this_day_authored() or _recent_save()
