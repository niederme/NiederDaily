"""Persisted record of which reminders the opening mentioned, to stop daily nagging.

The file maps a normalized reminder title to the ISO date it was last mentioned.
A missing or corrupt file is an empty history; this module never raises.
It is written only after a real (non-test, non-backdated) send succeeds.
"""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import tempfile

from modules.opening_safety import _tokens

DEFAULT_COOLDOWN_DAYS = 7
MAX_OVERDUE_IN_PROMPT = 1


def default_path() -> Path:
    return Path.home() / ".niederdaily" / "state" / "opening_mentions.json"


def history_path(conf: dict | None) -> Path:
    configured = (conf or {}).get("opening_history_path")
    return Path(configured).expanduser() if configured else default_path()


def normalize(title: str) -> str:
    return " ".join(str(title).replace("’", "'").casefold().split())


def load(path: Path | str | None) -> dict:
    try:
        data = json.loads(Path(path).read_text())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    history = {}
    for key, value in data.items():
        try:
            history[str(key)] = date.fromisoformat(str(value)).isoformat()
        except ValueError:
            continue
    return history


def _days_since(history: dict, title: str, today: date) -> int | None:
    last = history.get(normalize(title))
    if not last:
        return None
    return (today - date.fromisoformat(last)).days


def filter_for_prompt(reminders: dict | None, history: dict | None, today: date,
                      cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
                      max_overdue: int = MAX_OVERDUE_IN_PROMPT) -> dict | None:
    """Reminders the opening may consider today. Items due today are always eligible."""
    if not reminders:
        return reminders
    history = history or {}

    def cooled(item):
        days = _days_since(history, item.get("title") or "", today)
        return days is None or days >= cooldown_days

    overdue = [r for r in reminders.get("overdue", []) if isinstance(r, dict) and cooled(r)]
    # Rotate: never-mentioned first, then least recently mentioned; stable within ties.
    overdue.sort(key=lambda r: -(_days_since(history, r.get("title") or "", today) or 10_000))
    return {
        **reminders,
        "today": list(reminders.get("today", [])),
        "overdue": overdue[:max_overdue],
        "upcoming": [r for r in reminders.get("upcoming", []) if isinstance(r, dict) and cooled(r)],
    }


def mentioned_titles(text: str | None, reminders: dict | None) -> list[str]:
    """Reminder titles the opening refers to, by the same token overlap opening_safety uses."""
    if not text or not reminders:
        return []
    words = _tokens(text)
    titles = []
    for bucket in ("today", "overdue", "upcoming"):
        for item in reminders.get(bucket, []):
            title = (item or {}).get("title") if isinstance(item, dict) else None
            if title and _tokens(title) & words and title not in titles:
                titles.append(title)
    return titles


def record(path: Path | str, titles: list[str], today: date) -> bool:
    """Atomically merge mentions into the history file. Returns False on any failure."""
    if not titles:
        return True
    try:
        path = Path(path)
        history = load(path)
        for title in titles:
            history[normalize(title)] = today.isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".opening_mentions.", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(history, handle, indent=2, sort_keys=True)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except Exception:
        return False
