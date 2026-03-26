from __future__ import annotations

from datetime import date, datetime, time, timedelta
import threading

try:
    import EventKit
    from Foundation import NSDate, NSUndefinedDateComponent
except ImportError:  # pragma: no cover - exercised in integration environments
    EventKit = None
    NSDate = None
    NSUndefinedDateComponent = None


def _event_store():
    if EventKit is None:
        return None
    return EventKit.EKEventStore.alloc().init()


def _readable_statuses() -> set[int]:
    statuses = {EventKit.EKAuthorizationStatusAuthorized}
    full_access = getattr(EventKit, "EKAuthorizationStatusFullAccess", None)
    if full_access is not None:
        statuses.add(full_access)
    return statuses


def _request_full_access(store) -> bool:
    done = threading.Event()
    result = {"granted": False}

    if hasattr(store, "requestFullAccessToRemindersWithCompletion_"):
        def completion(granted, error):
            result["granted"] = bool(granted)
            done.set()

        store.requestFullAccessToRemindersWithCompletion_(completion)
    elif hasattr(store, "requestAccessToEntityType_completion_"):
        def completion(granted, error):
            result["granted"] = bool(granted)
            done.set()

        store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeReminder, completion)
    else:
        return False

    done.wait(5)
    return result["granted"]


def _has_reminders_access(prompt: bool = False) -> bool:
    if EventKit is None:
        return False
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeReminder)
    if status in _readable_statuses():
        return True
    if not prompt:
        return False
    store = _event_store()
    if store is None:
        return False
    return _request_full_access(store)


def reminders_access_granted(prompt: bool = False) -> bool:
    return _has_reminders_access(prompt=prompt)


def _nsdate_for_local(dt: datetime):
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _selected_lists(store, lists: list | None):
    available = list(store.calendarsForEntityType_(EventKit.EKEntityTypeReminder) or [])
    if not lists:
        return available
    wanted = set(lists)
    return [cal for cal in available if cal.title() in wanted]


def _fetch_reminders(store, predicate, timeout: int = 5):
    done = threading.Event()
    result = {"items": None}

    def completion(reminders):
        result["items"] = list(reminders or [])
        done.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, completion)
    if not done.wait(timeout):
        raise TimeoutError("Timed out fetching reminders from EventKit")
    return result["items"]


def _due_date_string(reminder) -> str | None:
    components = reminder.dueDateComponents()
    if components is None:
        return None
    year = components.year()
    month = components.month()
    day = components.day()
    if (
        year in (None, NSUndefinedDateComponent)
        or month in (None, NSUndefinedDateComponent)
        or day in (None, NSUndefinedDateComponent)
    ):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _list_name(reminder) -> str | None:
    try:
        calendar = reminder.calendar()
        if calendar is None:
            return None
        title = calendar.title()
        return title.strip() if title else None
    except Exception:
        return None


def _reminder_identifier(reminder) -> str | None:
    try:
        identifier = reminder.calendarItemIdentifier()
        return identifier.strip() if identifier else None
    except Exception:
        return None


def _list_color(reminder) -> str | None:
    try:
        calendar = reminder.calendar()
        if calendar is None:
            return None
        for attr in ("colorStringRaw", "colorString"):
            value = getattr(calendar, attr, None)
            if value is None:
                continue
            color = value() if callable(value) else value
            if isinstance(color, str) and color.startswith("#"):
                if len(color) == 9:
                    return color[:7]
                if len(color) in {4, 7}:
                    return color
    except Exception:
        return None
    return None


def reminders_block(lists: list | None = None) -> dict | None:
    if EventKit is None or not _has_reminders_access():
        return None

    try:
        store = _event_store()
        selected = _selected_lists(store, lists)
        if not selected:
            return {"overdue": [], "today": [], "upcoming": []}

        today = date.today()
        cutoff = today + timedelta(days=7)
        end_dt = datetime.combine(cutoff + timedelta(days=1), time.min)
        predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
            None,
            _nsdate_for_local(end_dt),
            selected,
        )
        reminders = _fetch_reminders(store, predicate)

        overdue, today_items, upcoming = [], [], []
        for reminder in reminders:
            title = (reminder.title() or "").strip()
            if not title:
                continue
            due_str = _due_date_string(reminder)
            if not due_str:
                continue
            try:
                due = date.fromisoformat(due_str)
            except ValueError:
                continue

            item = {
                "title": title,
                "due": due_str,
                "list": _list_name(reminder),
                "identifier": _reminder_identifier(reminder),
                "list_color": _list_color(reminder),
            }
            if due < today:
                overdue.append(item)
            elif due == today:
                today_items.append(item)
            elif due <= cutoff:
                upcoming.append(item)

        overdue.sort(key=lambda item: item["due"])
        today_items.sort(key=lambda item: item["title"].lower())
        upcoming.sort(key=lambda item: item["due"])
        return {
            "overdue": overdue,
            "today": today_items,
            "upcoming": upcoming[:5],
        }
    except Exception:
        return None
