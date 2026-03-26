import types
from datetime import date, timedelta
from unittest.mock import MagicMock

import modules.reminders as reminders


class _FakeComponents:
    def __init__(self, year, month, day):
        self._year = year
        self._month = month
        self._day = day

    def year(self):
        return self._year

    def month(self):
        return self._month

    def day(self):
        return self._day


def _make_reminder(title, due):
    reminder = MagicMock()
    reminder.title.return_value = title
    if due is None:
        reminder.dueDateComponents.return_value = None
    else:
        reminder.dueDateComponents.return_value = _FakeComponents(due.year, due.month, due.day)
    reminder.calendar.return_value.title.return_value = "House Wish List"
    reminder.calendar.return_value.colorStringRaw.return_value = "#0088FFFF"
    return reminder


def test_overdue_items(mocker):
    today = date.today()
    reminder_items = [
        _make_reminder("Overdue task", today - timedelta(days=1)),
        _make_reminder("Very overdue", today - timedelta(days=8)),
    ]

    store = MagicMock()
    store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.return_value = "predicate"
    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Inbox"])
    mocker.patch.object(reminders, "_fetch_reminders", return_value=reminder_items)
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = reminders.reminders_block([])

    assert result is not None
    assert len(result["overdue"]) == 2
    assert result["today"] == []
    assert result["upcoming"] == []


def test_today_items(mocker):
    today = date.today()
    store = MagicMock()
    store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.return_value = "predicate"

    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Inbox"])
    mocker.patch.object(reminders, "_fetch_reminders", return_value=[_make_reminder("Today task", today)])
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = reminders.reminders_block([])

    assert result is not None
    assert result["today"] == [{
        "title": "Today task",
        "due": today.isoformat(),
        "list": "House Wish List",
        "list_color": "#0088FF",
    }]
    assert result["overdue"] == []
    assert result["upcoming"] == []


def test_upcoming_items(mocker):
    today = date.today()
    store = MagicMock()
    store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.return_value = "predicate"

    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Inbox"])
    mocker.patch.object(reminders, "_fetch_reminders", return_value=[
        _make_reminder("Upcoming A", today + timedelta(days=3)),
        _make_reminder("Upcoming B", today + timedelta(days=6)),
    ])
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = reminders.reminders_block([])

    assert result is not None
    assert len(result["upcoming"]) == 2
    assert result["overdue"] == []
    assert result["today"] == []


def test_no_access_returns_none(mocker):
    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_has_reminders_access", return_value=False)
    assert reminders.reminders_block([]) is None


def test_due_date_string_ignores_undefined_components(mocker):
    undefined = 9223372036854775807
    mocker.patch.object(reminders, "NSUndefinedDateComponent", undefined)
    reminder = MagicMock()
    reminder.dueDateComponents.return_value = _FakeComponents(undefined, 3, 25)

    assert reminders._due_date_string(reminder) is None


def test_upcoming_capped_at_5(mocker):
    today = date.today()
    items = [_make_reminder(f"Task {i}", today + timedelta(days=i + 1)) for i in range(7)]
    store = MagicMock()
    store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.return_value = "predicate"

    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Inbox"])
    mocker.patch.object(reminders, "_fetch_reminders", return_value=items)
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)

    result = reminders.reminders_block([])

    assert result is not None
    assert len(result["upcoming"]) == 5
