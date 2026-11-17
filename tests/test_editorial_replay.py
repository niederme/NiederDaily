"""Synthetic replay of a commute day: introduction and destination selection."""

from datetime import date
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from modules.weather import geocode_location, weather_block
from modules.welcome import welcome_block


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "editorial_replay.json").read_text())
HOME = {"name": "Sampleton, PA", "lat": 40.0, "lon": -75.0}
CONFIG = {"default_location": HOME, "weather_calendars": ["Personal", "TripIt"]}
NOMINATIM = "https://nominatim.openstreetmap.org/search"


@pytest.fixture(autouse=True)
def _owner_profile():
    """A fictional reader whose conventions would normally come from config."""
    from modules import profile
    profile.configure({
        "owner_name": "Alex",
        "day_marker_prefixes": ["AX"],
        "commute": {"transit_lines": ["RailCo", "BusLine"]},
        "appointment_aliases": {"dentist": ["Dr. Rivera"]},
    })
    yield
    profile.configure(None)


def _result(city, state, code, country, country_code, lat, lon):
    return [{"lat": str(lat), "lon": str(lon), "display_name": f"{city}, {state}, {country}",
             "address": {"city": city, "state": state, "state_code": code,
                         "country": country, "country_code": country_code}}]


def _weather(lat, lon, name, config):
    return {"location": name, "temp": 60, "condition": "Clear"}


def _client(mocker, answer):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text=answer)])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    return client


def test_replay_rejects_raipur_and_keeps_nyc_weather(requests_mock, mocker):
    hits = iter([
        _result("Raipur", "Chhattisgarh", "CG", "India", "in", 21.25, 81.63),
        _result("New York", "New York", "NY", "United States", "us", 40.71, -74.00),
    ])
    requests_mock.get(NOMINATIM, json=lambda request, context: next(hits))
    mocker.patch("modules.weather.fetch_weather", side_effect=_weather)

    weather = weather_block(CONFIG, FIXTURE["calendar"])

    assert [place["location"] for place in weather["locations"]] == ["Sampleton, PA", "New York"]
    assert weather["travel_city"] == "New York"
    assert weather["travel_confirmed"] is False
    assert requests_mock.call_count == 2  # the six timetable options were skipped

    client = _client(mocker, "The team lunch and planning meeting are on today's calendar.")
    result = welcome_block("test", weather, FIXTURE["calendar"],
                           reminders=FIXTURE["reminders"], as_of=date.fromisoformat(FIXTURE["date"]))
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]

    assert result == "The team lunch and planning meeting are on today's calendar."
    assert "Planning meeting" in prompt
    assert "RailCo" not in prompt and "BusLine" not in prompt
    assert "Raipur" not in prompt and "Traveling to" not in prompt
    assert "Dentist" not in prompt and "flight" not in prompt.casefold()


@pytest.mark.parametrize("claim", [
    "You're headed to Raipur.",
    "Raipur is your destination today.",
    "Dentist at 9am is your anchor.",
    "Check your flight time and connections.",
])
def test_replay_rejects_unsupported_generated_claims(mocker, claim):
    client = _client(mocker, claim)
    weather = {"locations": [{"location": "Sampleton, PA", "temp": 60, "condition": "Clear"}],
               "travel_city": None, "travel_confirmed": False}

    result = welcome_block("test", weather, FIXTURE["calendar"],
                           reminders=FIXTURE["reminders"], as_of=date.fromisoformat(FIXTURE["date"]))

    assert client.messages.create.called
    assert result is None


def test_transit_options_alone_do_not_create_a_destination(mocker):
    geocode = mocker.patch("modules.weather.geocode_location")
    mocker.patch("modules.weather.fetch_weather", side_effect=_weather)

    weather = weather_block(CONFIG, FIXTURE["calendar"][:6])

    assert weather["travel_city"] is None
    assert weather["travel_confirmed"] is False
    geocode.assert_not_called()


@pytest.mark.parametrize("title,answer", [
    ("Trip to Boston", "Your trip to Boston is on the calendar."),
    ("Flight to Boston", "Your flight to Boston is on the calendar."),
])
def test_explicit_travel_still_works(requests_mock, mocker, title, answer):
    requests_mock.get(NOMINATIM, json=_result(
        "Boston", "Massachusetts", "MA", "United States", "us", 42.36, -71.06))
    mocker.patch("modules.weather.fetch_weather", side_effect=_weather)
    calendar = [{"time": "9:00am", "title": title, "location": "Boston, MA, United States",
                 "calendar": "TripIt", "all_day": False}]
    weather = weather_block(CONFIG, calendar)
    client = _client(mocker, answer)

    result = welcome_block("test", weather, calendar, as_of=date(2026, 10, 13))
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]

    assert weather["travel_confirmed"] is True
    assert weather["travel_city"] == "Boston"
    assert "Traveling to Boston today" in prompt
    assert result == answer


def test_confirmed_appointment_remains_eligible(mocker):
    calendar = [{"time": "9:00am", "title": "Dr. Rivera and Alex's session", "all_day": False}]
    _client(mocker, "Dentist at 9am is on the calendar.")
    weather = {"locations": [{"location": "Sampleton, PA", "temp": 60, "condition": "Clear"}]}

    assert welcome_block("test", weather, calendar, as_of=date(2026, 10, 13)) == (
        "Dentist at 9am is on the calendar."
    )


def test_geocoder_rejects_wrong_state(requests_mock):
    requests_mock.get(NOMINATIM, json=_result(
        "Sampleton", "Rhode Island", "RI", "United States", "us", 41.70, -71.42))
    assert geocode_location("Sampleton, PA, United States") is None


def test_geocoder_accepts_matching_iso_region(requests_mock):
    result = _result("New York", "New York", "NY", "United States", "us", 40.71, -74.00)
    result[0]["address"].pop("state_code")
    result[0]["address"]["ISO3166-2-lvl4"] = "US-NY"
    requests_mock.get(NOMINATIM, json=result)
    assert geocode_location("New York, NY, United States")["name"] == "New York, New York"


def test_geocoder_rejects_wrong_written_country(requests_mock):
    requests_mock.get(NOMINATIM, json=_result(
        "Raipur", "Chhattisgarh", "CG", "India", "in", 21.25, 81.63))
    assert geocode_location("Paris, France") is None
