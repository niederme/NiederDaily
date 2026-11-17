"""Fixture-only replay. Never imports the orchestrator/sender or collects sources.

Usage: python offline_preview.py fixture.json /private/output/preview.eml
The fixture contains rendered-section inputs and an optional candidate welcome.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path

from modules.welcome import validate_opening
from renderer import render_email


def preview(fixture: dict, destination: Path) -> dict:
    if not isinstance(fixture, dict) or "date" not in fixture:
        raise ValueError("Fixture requires an ISO report date")
    as_of = date.fromisoformat(fixture["date"])
    candidate = fixture.get("welcome")
    welcome = validate_opening(candidate, calendar_events=fixture.get("calendar"),
                               weather_data=fixture.get("weather"),
                               reminders=fixture.get("reminders"), packages=fixture.get("packages"))
    msg = render_email(recipient="preview@example.invalid", welcome=welcome,
                       weather=fixture.get("weather"), calendar=fixture.get("calendar"),
                       reminders=fixture.get("reminders"), packages=fixture.get("packages"),
                       messages=None, photo=None, nyt=fixture.get("nyt"),
                       tweet=fixture.get("tweet"), as_of=as_of)
    # No overwrite and owner-private permissions, including when umask is permissive.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(msg.as_bytes())
    return {"mode": "offline_preview", "sent": False,
            "opening": "included" if welcome else "omitted", "output": str(destination)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(preview(json.loads(args.fixture.read_text()), args.destination)))
