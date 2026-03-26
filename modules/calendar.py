from __future__ import annotations

from datetime import date, datetime, time, timedelta
import threading

try:
    import EventKit
    from Foundation import NSDate
except ImportError:  # pragma: no cover - exercised in integration environments
    EventKit = None
    NSDate = None


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


def _request_full_access(store, entity_type: int) -> bool:
    done = threading.Event()
    result = {"granted": False}

    if entity_type == EventKit.EKEntityTypeEvent and hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        def completion(granted, error):
            result["granted"] = bool(granted)
            done.set()

        store.requestFullAccessToEventsWithCompletion_(completion)
    elif entity_type == EventKit.EKEntityTypeReminder and hasattr(store, "requestFullAccessToRemindersWithCompletion_"):
        def completion(granted, error):
            result["granted"] = bool(granted)
            done.set()

        store.requestFullAccessToRemindersWithCompletion_(completion)
    elif hasattr(store, "requestAccessToEntityType_completion_"):
        def completion(granted, error):
            result["granted"] = bool(granted)
            done.set()

        store.requestAccessToEntityType_completion_(entity_type, completion)
    else:
        return False

    done.wait(5)
    return result["granted"]


def _has_calendar_access(prompt: bool = False) -> bool:
    if EventKit is None:
        return False
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    if status in _readable_statuses():
        return True
    if not prompt:
        return False
    store = _event_store()
    if store is None:
        return False
    return _request_full_access(store, EventKit.EKEntityTypeEvent)


def calendar_access_granted(prompt: bool = False) -> bool:
    return _has_calendar_access(prompt=prompt)


def _nsdate_for_local(dt: datetime):
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _selected_calendars(store, calendars: list | None):
    available = list(store.calendarsForEntityType_(EventKit.EKEntityTypeEvent) or [])
    if not calendars:
        return available
    wanted = set(calendars)
    return [cal for cal in available if cal.title() in wanted]


def _format_time_label(event) -> str | None:
    if event.isAllDay():
        return None
    start_dt = datetime.fromtimestamp(event.startDate().timeIntervalSince1970())
    return start_dt.strftime("%-I:%M%p").lower()


def _calendar_name(event) -> str | None:
    try:
        calendar = event.calendar()
        if calendar is None:
            return None
        title = calendar.title()
        return title.strip() if title else None
    except Exception:
        return None


def _calendar_color(event) -> str | None:
    try:
        calendar = event.calendar()
        if calendar is None:
            return None

        for attr in ("colorStringRaw", "colorString"):
            value = getattr(calendar, attr, None)
            if value is None:
                continue
            color = value() if callable(value) else value
            if isinstance(color, str) and color.startswith("#") and len(color) in {4, 7, 9}:
                return color
    except Exception:
        return None
    return None


def _time_sort_key(event):
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


def calendar_block(calendars: list | None = None) -> list | None:
    if EventKit is None or not _has_calendar_access():
        return None

    try:
        store = _event_store()
        selected = _selected_calendars(store, calendars)
        if not selected:
            return []

        start_dt = datetime.combine(date.today(), time.min)
        end_dt = start_dt + timedelta(days=1)
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            _nsdate_for_local(start_dt),
            _nsdate_for_local(end_dt),
            selected,
        )
        raw_events = list(store.eventsMatchingPredicate_(predicate) or [])

        events = []
        for event in raw_events:
            title = (event.title() or "").strip()
            if not title:
                continue
            time_val = _format_time_label(event)
            location = (event.location() or "").strip()
            events.append({
                "time": time_val,
                "title": title,
                "location": location,
                "calendar": _calendar_name(event),
                "calendar_color": _calendar_color(event),
                "all_day": time_val is None,
            })

        timed = sorted([e for e in events if not e["all_day"]], key=_time_sort_key)
        all_day = [e for e in events if e["all_day"]]
        return timed + all_day
    except Exception:
        return None
