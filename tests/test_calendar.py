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
    event.calendarItemIdentifier.return_value = "event-123"
    event.calendar.return_value.title.return_value = "Personal"
    event.calendar.return_value.colorStringRaw.return_value = "#0088FF"
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
    assert result[0]["identifier"] == "event-123"
    assert result[0]["calendar_color"] == "#0088FF"
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


def test_parcel_window_end_is_preserved_without_native_access():
    event = _make_event("Example Store", 1742979600)
    event.endDate.return_value = _FakeNSDate(1742986800)
    assert calendar._delivery_end_time(event, "Parcel") is not None
    assert calendar._delivery_end_time(event, "Personal") is None
    event.endDate.return_value = _FakeNSDate(1742979600 - 60)
    assert calendar._delivery_end_time(event, "Parcel") is None
    event.endDate.return_value = _FakeNSDate(1742979600 + 86400)
    assert calendar._delivery_end_time(event, "Parcel") is None
    event.endDate.return_value = None
    assert calendar._delivery_end_time(event, "Parcel") is None


def _transit_profile():
    from modules import profile
    profile.configure({"commute": {"transit_lines": ["Metro", "Coach"]}})


def test_transit_options_come_from_configured_lines():
    assert not calendar.is_transit_option({"title": "Metro 500 Inbound"})  # neutral default
    _transit_profile()
    assert calendar.is_transit_option({"title": "Metro 500 Inbound"})
    assert calendar.is_transit_option({"title": "coach 12 Outbound to the city"})
    assert not calendar.is_transit_option({"title": "Metro planning meeting"})


def test_transit_arrival_end_time_is_preserved_on_any_calendar():
    _transit_profile()
    event = _make_event("Metro 500 Outbound", 1742979600)
    event.endDate.return_value = _FakeNSDate(1742979600 + 4800)
    assert calendar._delivery_end_time(event, "Home", "Metro 500 Outbound") is not None
    assert calendar._delivery_end_time(event, "Home", "Dinner") is None


class _Src:
    def __init__(self, kind):
        self._k = kind

    def sourceType(self):
        return self._k


class _Cal:
    def __init__(self, title, kind=0, ident=None):
        self._t, self._s, self._i = title, _Src(kind), ident or f"{title}-{kind}"

    def title(self):
        return self._t

    def source(self):
        return self._s

    def calendarIdentifier(self):
        return self._i


ALIASES = {
    "Work": {"title": "Calendar", "source_type": "exchange"},
    "Holidays": {"title": "US Holidays", "source_type": None},
}


def _select(available, names, caplog, aliases=ALIASES):
    from modules import profile
    profile.configure({"calendar_aliases": aliases})
    store = MagicMock()
    store.calendarsForEntityType_.return_value = available
    original = calendar.EventKit
    calendar.EventKit = types.SimpleNamespace(EKEntityTypeEvent=0, EKSourceTypeExchange=1)
    try:
        with caplog.at_level("INFO", logger="modules.calendar"):
            return calendar._selected_calendars(store, names)
    finally:
        calendar.EventKit = original


def test_alias_picks_exchange_calendar_not_icloud(caplog):
    icloud, exchange = _Cal("Calendar", 0, "ic"), _Cal("Calendar", 1, "ex")
    chosen = _select([icloud, exchange, _Cal("Home")], ["Work", "Home"], caplog)
    assert chosen[0] is exchange and [c.title() for c in chosen] == ["Calendar", "Home"]
    assert "'Work' resolved to 'Calendar' (exchange account)" in caplog.text
    assert calendar._DISPLAY_NAMES == {"ex": "Work"}


def test_alias_without_config_is_unmatched(caplog):
    assert _select([_Cal("Calendar", 1, "ex")], ["Work"], caplog, aliases={}) == []
    assert "'Work' matches no calendar" in caplog.text


def test_case_insensitive_fallback_single_match_only(caplog):
    chosen = _select([_Cal("Tripit"), _Cal("Home")], ["TripIt", "Home"], caplog)
    assert [c.title() for c in chosen] == ["Tripit", "Home"]
    assert "'TripIt' matched 'Tripit' ignoring case" in caplog.text
    caplog.clear()
    assert _select([_Cal("Tripit"), _Cal("TRIPIT")], ["TripIt"], caplog) == []
    assert "matches 2 calendars ignoring case" in caplog.text
    # An exact title always wins over a case-folded one.
    exact = _Cal("Tripit", 0, "exact")
    assert _select([exact, _Cal("TRIPIT")], ["Tripit"], caplog) == [exact]


def test_ambiguous_alias_is_skipped_with_warning(caplog):
    chosen = _select([_Cal("Calendar", 1, "a"), _Cal("Calendar", 1, "b")], ["Work"], caplog)
    assert chosen == []
    assert "ambiguous" in caplog.text


def test_alias_without_source_type_matches_any_account(caplog):
    chosen = _select([_Cal("US Holidays"), _Cal("United States holidays", 1)], ["Holidays"], caplog)
    assert [c.title() for c in chosen] == ["US Holidays"]


def test_unmatched_names_warn(caplog):
    chosen = _select([_Cal("Home")], ["Nonexistent Calendar"], caplog)
    assert chosen == []
    assert "'Nonexistent Calendar' matches no calendar" in caplog.text
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_exact_title_wins_over_alias(caplog):
    work = _Cal("Work", 0, "w")
    assert _select([work, _Cal("Calendar", 1, "ex")], ["Work"], caplog) == [work]
