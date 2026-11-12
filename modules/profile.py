"""Personal conventions the opening relies on, read from config.json.

The repository ships neutral defaults. Everything specific to one reader (names,
home town, commute, calendar shorthand, recurring people) lives in the reader's
own ~/.niederdaily/config.json; see "Personal conventions" in the README.

`configure(conf)` is called once per run, right after the config loads. Modules
read the active profile with `get()`.
"""
from __future__ import annotations

import copy

COMMUTE_DEFAULTS = {
    "city": None,              # e.g. "Capital City": where a commute day takes the reader
    "city_aliases": [],        # day-marker places that mean the commute city, e.g. ["CC", "downtown"]
    "location_keywords": [],   # event locations that place the reader in the city
    "transit_lines": [],       # timetable title prefixes, e.g. ["Metro"] for "Metro 12 Inbound"
    "mode": "bus",             # how the commute is described ("bus", "train")
    "depart": None,            # usual departure, e.g. "7:05am"
    "home": None,              # usual time back home, e.g. "6:45pm"
    "arrival_stop": None,      # where the last listed ride home arrives, e.g. "Springfield"
}

DEFAULTS = {
    "owner_name": "the reader",
    "owner_full_name": None,
    "employer": None,
    # All-day "<PREFIX>: <place>" events say where the reader is that day.
    "day_marker_prefixes": [],
    "home_keywords": ["home", "wfh", "work from home"],
    "home_label": None,
    # Title prefixes for items that belong to someone else in the household: {"AB": "Alex"}.
    "household_prefixes": {},
    # Calendars that are the reader's own (subscribed calendars never place the reader anywhere).
    "own_calendars": [],
    # Title substring -> context sentence for recurring people or events.
    "event_context": {},
    "routine_event_keywords": [],
    # Appointment word -> calendar title keywords that substantiate it: {"therapy": ["Dr. Lee"]}.
    "appointment_aliases": {},
    # Extra household facts appended to the opening's instructions.
    "prompt_notes": [],
    # Configured calendar name -> the EventKit calendar it means: {"Work": {"title": "Calendar", "source_type": "exchange"}}.
    "calendar_aliases": {},
    # Reminder titles kept in Apple Reminders but left out of the newsletter.
    "reminders_suppressed_titles": [],
    # [{"title": "Check filter!", "list": "Home", "newsletter_title": "Replace the furnace filter!"}]
    "reminder_title_overrides": [],
    "commute": COMMUTE_DEFAULTS,
}

_active: dict = copy.deepcopy(DEFAULTS)


def configure(conf: dict | None) -> dict:
    """Merge the reader's config over the neutral defaults and make it active."""
    global _active
    merged = copy.deepcopy(DEFAULTS)
    for key, value in (conf or {}).items():
        if key == "commute" and isinstance(value, dict):
            merged["commute"] = {**COMMUTE_DEFAULTS, **value}
        elif key in DEFAULTS and value is not None:
            merged[key] = value
    _active = merged
    return _active


def get() -> dict:
    return _active


def owner() -> str:
    return _active["owner_name"] or DEFAULTS["owner_name"]
