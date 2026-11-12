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
    reminder.calendarItemIdentifier.return_value = "reminder-123"
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
        "identifier": "reminder-123",
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


def _routine_profile():
    from modules import profile
    profile.configure({
        "reminders_suppressed_titles": ["Morning pills", "Vitamins!", "Call Grandma", "Reset Kid’s Limits"],
        "reminder_title_overrides": [
            {"title": "Check filter!", "list": "Home", "newsletter_title": "Replace the furnace filter!"}],
    })


def test_configured_routines_are_omitted_from_every_bucket(mocker):
    _routine_profile()
    today = date.today()
    store = MagicMock()
    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Inbox"])
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)
    titles = ["Morning pills", "Vitamins!", "  CALL   GRANDMA  ", "Reset Kid's Limits", "Reset Kid’s Limits"]
    items = [_make_reminder(title, today + timedelta(days=offset))
             for title in titles for offset in (-1, 0, 1)]
    items.append(_make_reminder("Call Grandma about Thanksgiving", today))
    mocker.patch.object(reminders, "_fetch_reminders", return_value=items)
    result = reminders.reminders_block([])
    assert result["overdue"] == []
    assert result["upcoming"] == []
    assert [item["title"] for item in result["today"]] == ["Call Grandma about Thanksgiving"]


def test_title_override_is_scoped_to_its_list():
    assert reminders._newsletter_title("Check filter!", "Home") == "Check filter!"  # neutral default
    _routine_profile()
    assert reminders._newsletter_title("Check filter!", "Home") == "Replace the furnace filter!"
    assert reminders._newsletter_title("  CHECK   FILTER!  ", "home") == "Replace the furnace filter!"
    assert reminders._newsletter_title("Check filter!", "Car") == "Check filter!"
    assert reminders._newsletter_title("Check filter!", None) == "Check filter!"
    assert reminders._newsletter_title("Check car filter!", "Home") == "Check car filter!"
    assert reminders._newsletter_title("Buy coffee filters", "Home") == "Buy coffee filters"


def test_title_override_preserves_source_and_due_buckets(mocker):
    _routine_profile()
    today = date(2026, 11, 9)
    items = [_make_reminder("Check filter!", today + timedelta(days=offset))
             for offset in (-21, 0, 3)]
    for item in items:
        item.calendar.return_value.title.return_value = "Home"
    store = MagicMock()
    mocker.patch.object(reminders, "EventKit", types.SimpleNamespace(EKEntityTypeReminder=1))
    mocker.patch.object(reminders, "_event_store", return_value=store)
    mocker.patch.object(reminders, "_has_reminders_access", return_value=True)
    mocker.patch.object(reminders, "_selected_lists", return_value=["Home"])
    mocker.patch.object(reminders, "_nsdate_for_local", side_effect=lambda dt: dt)
    mocker.patch.object(reminders, "_fetch_reminders", return_value=items)

    result = reminders.reminders_block(["Home"], as_of=today)

    for bucket, offset in (("overdue", -21), ("today", 0), ("upcoming", 3)):
        assert result[bucket] == [{
            "title": "Replace the furnace filter!",
            "due": (today + timedelta(days=offset)).isoformat(),
            "list": "Home",
            "identifier": "reminder-123",
            "list_color": "#0088FF",
        }]
    for item in items:
        assert item.title() == "Check filter!"
        assert not any(call[0].startswith("set") for call in item.mock_calls)
    assert not any(call[0].startswith(("save", "remove", "commit")) for call in store.mock_calls)
