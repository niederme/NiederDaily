import types
from unittest.mock import MagicMock

import modules.calendar as calendar


class _FakeNSDate:
    def __init__(self, ts):
        self._ts = ts

    def timeIntervalSince1970(self):
        return self._ts


def _make_event(title, ts, location="", all_day=False):
    event = MagicMock()
    event.title.return_value = title
    event.location.return_value = location
    event.isAllDay.return_value = all_day
    event.startDate.return_value = _FakeNSDate(ts)
    event.calendar.return_value.title.return_value = "Personal"
    return event


def test_calendar_block_parses_events(mocker):
    store = MagicMock()
    store.predicateForEventsWithStartDate_endDate_calendars_.return_value = "predicate"
    store.eventsMatchingPredicate_.return_value = [
        _make_event("Weekly sync", 1742979600, "Zoom"),
        _make_event("Lunch with Sarah", 1742990400, "The Landmark Inn"),
        _make_event("Phil's birthday", 1742990400, "", all_day=True),
    ]

    mocker.patch.object(calendar, "EventKit", types.SimpleNamespace(EKEntityTypeEvent=0))
    mocker.patch.object(calendar, "_event_store", return_value=store)
    mocker.patch.object(calendar, "_has_calendar_access", return_value=True)
    mocker.patch.object(calendar, "_selected_calendars", return_value=["Personal"])
    mocker.patch.object(calendar, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = calendar.calendar_block(["Personal"])

    assert len(result) == 3
    assert result[0]["title"] == "Weekly sync"
    assert result[0]["location"] == "Zoom"
    assert result[0]["calendar"] == "Personal"
    assert result[0]["all_day"] is False
    assert result[2]["all_day"] is True
    assert result[2]["title"] == "Phil's birthday"


def test_calendar_block_returns_none_without_access(mocker):
    mocker.patch.object(calendar, "EventKit", types.SimpleNamespace(EKEntityTypeEvent=0))
    mocker.patch.object(calendar, "_has_calendar_access", return_value=False)
    assert calendar.calendar_block() is None


def test_calendar_block_returns_empty_list_when_no_matching_calendars(mocker):
    store = MagicMock()
    mocker.patch.object(calendar, "EventKit", types.SimpleNamespace(EKEntityTypeEvent=0))
    mocker.patch.object(calendar, "_event_store", return_value=store)
    mocker.patch.object(calendar, "_has_calendar_access", return_value=True)
    mocker.patch.object(calendar, "_selected_calendars", return_value=[])

    assert calendar.calendar_block(["Missing"]) == []


def test_calendar_block_sorts_timed_events_chronologically(mocker):
    store = MagicMock()
    store.predicateForEventsWithStartDate_endDate_calendars_.return_value = "predicate"
    store.eventsMatchingPredicate_.return_value = [
        _make_event("Late meeting", 1742983200),
        _make_event("Early standup", 1742979600),
    ]

    mocker.patch.object(calendar, "EventKit", types.SimpleNamespace(EKEntityTypeEvent=0))
    mocker.patch.object(calendar, "_event_store", return_value=store)
    mocker.patch.object(calendar, "_has_calendar_access", return_value=True)
    mocker.patch.object(calendar, "_selected_calendars", return_value=["Personal"])
    mocker.patch.object(calendar, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = calendar.calendar_block(["Personal"])

    assert result[0]["title"] == "Early standup"
    assert result[1]["title"] == "Late meeting"
