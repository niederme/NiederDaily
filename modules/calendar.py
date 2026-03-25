import subprocess
from datetime import date

APPLESCRIPT = """
set today to current date
set todayStart to today - (time of today)
set todayEnd to todayStart + 86399
set output to ""
tell application "Calendar"
    repeat with cal in calendars
        set evts to (every event of cal whose start date >= todayStart and start date <= todayEnd)
        repeat with e in evts
            set t to ""
            try
                if allday event of e is true then
                    set t to ""
                else
                    set h to hours of (start date of e)
                    set m to minutes of (start date of e)
                    set ampm to "am"
                    if h >= 12 then set ampm to "pm"
                    if h > 12 then set h to h - 12
                    if h = 0 then set h to 12
                    set mins to m as string
                    if m < 10 then set mins to "0" & mins
                    set t to (h as string) & ":" & mins & ampm
                end if
            end try
            set loc to ""
            try
                set loc to location of e
                if loc is missing value then set loc to ""
            end try
            set output to output & t & "|" & (summary of e) & "|" & loc & "\n"
        end repeat
    end repeat
end tell
return output
"""


def _time_sort_key(event):
    """Parse time string and return minutes since midnight for sorting."""
    t = event.get("time") or ""
    try:
        h, rest = t.split(":")
        m = int(rest[:2])
        ampm = rest[2:].lower()
        h = int(h)
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        return h * 60 + m
    except Exception:
        return 0


def calendar_block() -> list | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", APPLESCRIPT],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        events = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 2:
                continue
            time_str, title = parts[0].strip(), parts[1].strip()
            location = parts[2].strip() if len(parts) > 2 else ""
            if not title:
                continue
            time_val = time_str if time_str else None
            events.append({
                "time": time_val,
                "title": title,
                "location": location,
                "all_day": time_val is None,
            })
        # Sort: timed events chronologically, all-day last
        timed = sorted([e for e in events if not e["all_day"]], key=_time_sort_key)
        all_day = [e for e in events if e["all_day"]]
        return timed + all_day
    except Exception:
        return None
