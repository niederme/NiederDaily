#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime


def _run_applescript(script: str) -> int:
    return subprocess.run(["osascript", "-e", script]).returncode


def _escape(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _calendar_script(payload: dict) -> str:
    title = _escape(payload.get("title"))
    calendar = _escape(payload.get("calendar"))
    date_str = payload.get("date") or ""
    time_str = payload.get("time") or ""
    if time_str:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M%p")
        appt = dt.strftime("%A, %B %-d, %Y at %-I:%M:%S %p")
        return f'''tell application "Calendar"
    activate
    set targetSummary to "{title}"
    set targetStart to date "{appt}"
    set candidateCalendars to calendars
    if "{calendar}" is not "" then set candidateCalendars to calendars whose name is "{calendar}"
    repeat with cal in candidateCalendars
        set matches to (every event of cal whose summary is targetSummary and start date = targetStart)
        if (count of matches) > 0 then
            show item 1 of matches
            return
        end if
    end repeat
end tell'''

    day_start = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %-d, %Y 12:00:00 AM")
    return f'''tell application "Calendar"
    activate
    set targetSummary to "{title}"
    set targetDayStart to date "{day_start}"
    set targetDayEnd to targetDayStart + (24 * hours)
    set candidateCalendars to calendars
    if "{calendar}" is not "" then set candidateCalendars to calendars whose name is "{calendar}"
    repeat with cal in candidateCalendars
        set matches to (every event of cal whose summary is targetSummary and start date ≥ targetDayStart and start date < targetDayEnd)
        if (count of matches) > 0 then
            show item 1 of matches
            return
        end if
    end repeat
end tell'''


def _reminder_script(payload: dict) -> str:
    title = _escape(payload.get("title"))
    list_name = _escape(payload.get("list"))
    return f'''tell application "Reminders"
    activate
    set targetName to "{title}"
    set candidateLists to lists
    if "{list_name}" is not "" then set candidateLists to lists whose name is "{list_name}"
    repeat with currentList in candidateLists
        set matches to (every reminder of currentList whose name is targetName)
        if (count of matches) > 0 then
            show item 1 of matches
            return
        end if
    end repeat
end tell'''


def _photo_script(payload: dict) -> str:
    photo_id = _escape(payload.get("id"))
    filename = _escape(payload.get("filename"))
    title = _escape(payload.get("title"))
    date_str = _escape(payload.get("date"))
    search_term = filename or title or date_str
    if photo_id:
        return f'''tell application "Photos"
    activate
    spotlight media item id "{photo_id}"
end tell'''
    return f'''tell application "Photos"
    activate
    search for "{search_term}"
end tell'''


def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    payload = json.loads(raw)
    item_type = payload.get("type")
    if item_type == "calendar":
        return _run_applescript(_calendar_script(payload))
    if item_type == "reminder":
        return _run_applescript(_reminder_script(payload))
    if item_type == "photo":
        return _run_applescript(_photo_script(payload))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
