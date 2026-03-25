import subprocess
from datetime import date, timedelta


def _build_script(lists: list | None) -> str:
    list_filter = ""
    if lists:
        quoted = ", ".join(f'"{l}"' for l in lists)
        list_filter = f"whose name is in {{{quoted}}}"
    return f"""
set today to current date
set output to ""
tell application "Reminders"
    repeat with rl in (every list {list_filter})
        repeat with r in (every reminder of rl whose completed is false)
            set dd to ""
            try
                set dd to due date of r
                set dd to (year of dd as string) & "-" & my pad(month of dd as integer) & "-" & my pad(day of dd as integer)
            end try
            set output to output & (name of r) & "|" & dd & "|false\\n"
        end repeat
    end repeat
end tell
return output

on pad(n)
    if n < 10 then return "0" & n
    return n as string
end pad
"""


def reminders_block(lists: list | None = None) -> dict | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", _build_script(lists)],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return None

        today = date.today()
        cutoff = today + timedelta(days=7)
        overdue, today_items, upcoming = [], [], []

        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            title = parts[0].strip()
            due_str = parts[1].strip() if len(parts) > 1 else ""
            if not title:
                continue
            if not due_str:
                continue  # no due date — skip
            try:
                due = date.fromisoformat(due_str)
            except ValueError:
                continue

            item = {"title": title, "due": due_str}
            if due < today:
                overdue.append(item)
            elif due == today:
                today_items.append(item)
            elif due <= cutoff:
                upcoming.append(item)

        return {
            "overdue": overdue,
            "today": today_items,
            "upcoming": upcoming[:5],
        }
    except Exception:
        return None
