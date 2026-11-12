from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
import re
import threading

from modules import profile

try:
    import EventKit
    from Foundation import NSDate
except ImportError:  # pragma: no cover - exercised in integration environments
    EventKit = None
    NSDate = None


log = logging.getLogger(__name__)


def is_transit_option(event: dict) -> bool:
    """Timetable alternatives ("<line> 12 Inbound") are context, not evidence of a booked trip.

    The line names come from the configured commute's `transit_lines`.
    """
    lines = [line for line in profile.get()["commute"].get("transit_lines") or [] if line]
    if not lines:
        return False
    title = event.get("title") or ""
    names = "|".join(re.escape(line) for line in lines)
    return bool(re.match(rf"^(?:{names})\s+\d+\s+(?:Inbound|Outbound)\b", title, re.I))


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


# Configured names that are not EventKit calendar titles come from the `calendar_aliases`
# config map: {"Work": {"title": "Calendar", "source_type": "exchange"}}. A source_type of
# "exchange" requires the calendar to live on an Exchange account, so an iCloud or local
# calendar with the same title is never picked up by mistake.

# calendarIdentifier -> configured name, so events show the name the reader configured.
_DISPLAY_NAMES: dict = {}


def _source_kind(cal) -> str | None:
    try:
        source = cal.source()
        if source is None:
            return None
        if source.sourceType() == getattr(EventKit, "EKSourceTypeExchange", 1):
            return "exchange"
        return "other"
    except Exception:
        return None


def _calendar_id(cal):
    try:
        return cal.calendarIdentifier()
    except Exception:
        return None


def _selected_calendars(store, calendars: list | None):
    available = list(store.calendarsForEntityType_(EventKit.EKEntityTypeEvent) or [])
    if not calendars:
        return available
    chosen = []
    _DISPLAY_NAMES.clear()
    for name in calendars:
        exact = [cal for cal in available if cal.title() == name]
        if exact:
            chosen.extend(exact)
            continue
        # Providers sometimes change a title's case ("TripIt" -> "Tripit").
        folded = [cal for cal in available if (cal.title() or "").casefold() == name.casefold()]
        if len(folded) == 1:
            log.info("Configured calendar %r matched %r ignoring case.", name, folded[0].title())
            chosen.append(folded[0])
            continue
        if len(folded) > 1:
            log.warning("Configured calendar %r matches %d calendars ignoring case; skipping it.",
                        name, len(folded))
            continue
        alias = (profile.get().get("calendar_aliases") or {}).get(name)
        if not isinstance(alias, dict) or not alias.get("title"):
            log.warning("Configured calendar %r matches no calendar; skipping it.", name)
            continue
        source_type = alias.get("source_type")
        matches = [cal for cal in available if cal.title() == alias["title"]
                   and (source_type is None or _source_kind(cal) == source_type)]
        if len(matches) == 1:
            log.info("Configured calendar %r resolved to %r%s.", name, alias["title"],
                     f" ({source_type} account)" if source_type else "")
            chosen.append(matches[0])
            identifier = _calendar_id(matches[0])
            if identifier:
                _DISPLAY_NAMES[identifier] = name
        elif matches:
            log.warning("Configured calendar %r is ambiguous (%d calendars titled %r); skipping it.",
                        name, len(matches), alias["title"])
        else:
            log.warning("Configured calendar %r (alias for %r) matches no calendar; skipping it.",
                        name, alias["title"])
    unique, seen = [], set()
    for cal in chosen:
        key = _calendar_id(cal) or id(cal)
        if key not in seen:
            seen.add(key)
            unique.append(cal)
    return unique


def _format_time_label(event) -> str | None:
    if event.isAllDay():
        return None
    start_dt = datetime.fromtimestamp(event.startDate().timeIntervalSince1970())
    return start_dt.strftime("%-I:%M%p").lower()


def _delivery_end_time(event, calendar_name, title: str | None = None) -> str | None:
    """Preserve a same-day Parcel window or transit arrival without inventing ordinary event duration."""
    is_transit = is_transit_option({"title": title or ""})
    if ((calendar_name or "").casefold() != "parcel" and not is_transit) or event.isAllDay():
        return None
    try:
        start = datetime.fromtimestamp(event.startDate().timeIntervalSince1970())
        end = datetime.fromtimestamp(event.endDate().timeIntervalSince1970())
        return end.strftime("%-I:%M%p").lower() if end.date() == start.date() and end > start else None
    except (AttributeError, TypeError, ValueError, OSError, OverflowError):
        return None


def _calendar_name(event) -> str | None:
    try:
        calendar = event.calendar()
        if calendar is None:
            return None
        alias = _DISPLAY_NAMES.get(_calendar_id(calendar))
        if alias:
            return alias
        title = calendar.title()
        return title.strip() if title else None
    except Exception:
        return None


def _calendar_identifier(event) -> str | None:
    try:
        identifier = event.calendarItemIdentifier()
        return identifier.strip() if identifier else None
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


def calendar_block(calendars: list | None = None, as_of: date | None = None) -> list | None:
    if EventKit is None:
        log.warning("Calendar block unavailable: EventKit framework not installed")
        return None
    if not _has_calendar_access():
        log.warning("Calendar block unavailable: calendar access not granted for this runtime")
        return None

    try:
        store = _event_store()
        selected = _selected_calendars(store, calendars)
        if not selected:
            return []

        start_dt = datetime.combine(as_of or date.today(), time.min)
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
            calendar_name = _calendar_name(event)
            events.append({
                "time": time_val,
                "title": title,
                "location": location,
                "calendar": calendar_name,
                "end_time": _delivery_end_time(event, calendar_name, title),
                "identifier": _calendar_identifier(event),
                "calendar_color": _calendar_color(event),
                "all_day": time_val is None,
            })

        timed = sorted([e for e in events if not e["all_day"]], key=_time_sort_key)
        all_day = [e for e in events if e["all_day"]]
        return timed + all_day
    except Exception:
        log.warning("Calendar block failed while reading EventKit events", exc_info=True)
        return None
