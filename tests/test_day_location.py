import pytest

from modules import profile
from modules.day_location import derive_location, is_day_marker, location_line

# A made-up reader. Real conventions live only in ~/.niederdaily/config.json.
PROFILE = {
    "owner_name": "Jordan",
    "day_marker_prefixes": ["JD"],
    "home_keywords": ["home", "wfh", "springfield"],
    "home_label": "Springfield",
    "household_prefixes": {"AB": "Alex"},
    "own_calendars": ["Home", "Work"],
    "commute": {"city": "Boston", "city_aliases": ["BOS", "the city"],
                "location_keywords": ["Boston, MA", "South Station"], "transit_lines": ["Metro"],
                "depart": "7:05am", "home": "7:40pm", "arrival_stop": "Springfield"},
}


@pytest.fixture(autouse=True)
def jordan():
    profile.configure(PROFILE)


COMMUTE_DAY = [
    {"time": "12:30pm", "end_time": "4:30pm", "title": "Example Store - UPS", "calendar": "Parcel", "location": "", "all_day": False},
    {"time": "2:00pm", "title": "Kid - STEM club", "calendar": "Home",
     "location": "Community Center\n1 Main St, Springfield", "all_day": False},
    {"time": "7:00pm", "title": "Shelbyville @ Springfield Isotopes", "calendar": "Springfield Isotopes",
     "location": "Ballpark", "all_day": False},
    {"time": None, "title": "No School", "calendar": "Home", "location": "", "all_day": True},
    {"time": None, "title": "JD: BOS", "calendar": "Home", "location": "", "all_day": True},
    {"time": None, "title": "Pat Example's 40th Birthday", "calendar": "Birthdays", "location": "", "all_day": True},
]


def test_commute_day_marker_without_transit_events_uses_usual_commute():
    loc = derive_location(COMMUTE_DAY)
    assert loc["status"] == "away" and loc["place"] == "Boston"
    assert (loc["depart"], loc["back"], loc["commute_source"]) == ("7:05am", "7:40pm", "usual")
    line = location_line(loc)
    assert "Jordan is away in Boston" in line and "7:05am bus" in line
    assert "back home in Springfield about 7:40pm" in line
    assert "Jordan is not home during the day" in line


def test_configured_commute_times_are_used():
    profile.configure({**PROFILE, "commute": {**PROFILE["commute"], "home": "8:15pm"}})
    loc = derive_location(COMMUTE_DAY)
    assert (loc["depart"], loc["back"]) == ("7:05am", "8:15pm")


def test_commute_without_usual_times_states_no_times():
    profile.configure({**PROFILE, "commute": {**PROFILE["commute"], "depart": None, "home": None}})
    loc = derive_location(COMMUTE_DAY)
    assert (loc["status"], loc["depart"], loc["back"], loc["commute_source"]) == ("away", None, None, None)
    assert location_line(loc) == "LOCATION: Jordan is away in Boston today. Jordan is not home during the day."


def test_booked_transit_events_give_departure_and_latest_listed_return():
    events = [
        {"time": "7:05am", "end_time": "8:20am", "title": "Metro 500 Inbound", "calendar": "Home",
         "location": "Springfield Park and Ride", "all_day": False},
        {"time": "5:30pm", "end_time": "6:48pm", "title": "Metro 400 Outbound", "calendar": "Home",
         "location": "South Station, Boston, MA", "all_day": False},
        {"time": "6:30pm", "end_time": "7:50pm", "title": "Metro 500 Outbound", "calendar": "Home",
         "location": "South Station, Boston, MA", "all_day": False},
    ]
    loc = derive_location(events)
    assert loc["status"] == "away"
    assert (loc["depart"], loc["back"], loc["commute_source"]) == ("7:05am", "7:50pm", "calendar")
    assert "the last listed bus home reaches Springfield about 7:50pm" in location_line(loc)


def test_home_day_markers():
    for title in ("JD: WFH", "JD: Springfield", "JD: Home"):
        loc = derive_location([{"title": title, "all_day": True, "calendar": "Work"}])
        assert loc["status"] == "home", title
        assert "Jordan is home in Springfield" in location_line(loc)


def test_no_signal_is_unknown():
    loc = derive_location([{"time": "9:00am", "title": "Weekly sync", "all_day": False, "calendar": "Home"}])
    assert loc["status"] == "unknown"
    assert location_line(loc).startswith("LOCATION: unknown")


def test_conflicting_markers_are_unknown():
    loc = derive_location([{"title": "JD: WFH", "all_day": True}, {"title": "JD: BOS", "all_day": True}])
    assert loc["status"] == "unknown"


def test_city_location_on_own_calendar_implies_away_but_not_for_household_member():
    dentist = {"time": "5:00pm", "title": "JD: Dentist", "calendar": "Home", "all_day": False,
               "location": "1 Example St, Boston, MA 02110"}
    assert derive_location([dentist])["status"] == "away"
    assert derive_location([{**dentist, "title": "AB: Dentist"}])["status"] == "unknown"
    # Subscribed calendars (sports, concerts) never place the reader anywhere.
    assert derive_location([{**dentist, "calendar": "Concerts"}])["status"] == "unknown"


def test_confirmed_travel_and_multi_day_trip_marker():
    assert derive_location([], {"travel_city": "Denver", "travel_confirmed": True})["place"] == "Denver"
    trip = derive_location([{"title": "JD: Denver", "all_day": True}])
    assert trip["status"] == "away" and trip["place"] == "Denver" and trip["depart"] is None
    assert "away in Denver" in location_line(trip)


def test_parenthetical_detail_is_ignored_and_marker_detected():
    event = {"title": "JD: BOS (lunch with Sam)", "all_day": True}
    assert is_day_marker(event)
    assert derive_location([event])["place"] == "Boston"
    assert not is_day_marker({"title": "JD: Therapy", "all_day": False})


def test_neutral_defaults_never_place_the_reader():
    profile.configure(None)
    assert not is_day_marker({"title": "JD: BOS", "all_day": True})
    assert derive_location(COMMUTE_DAY)["status"] == "unknown"
    transit = [{"time": "7:05am", "title": "Metro 500 Inbound", "calendar": "Home", "all_day": False}]
    assert derive_location(transit)["status"] == "unknown"
    assert location_line(derive_location([])) == (
        "LOCATION: unknown. The calendar does not say whether the reader is home or away today.")
