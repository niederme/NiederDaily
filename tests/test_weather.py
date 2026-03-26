import pytest

from modules.weather import fetch_weather, geocode_location, wmo_label, weather_block

OPEN_METEO_RESPONSE = {
    "current": {"temperature_2m": 54.1, "weathercode": 3},
    "hourly": {
        "time": [
            "2026-03-25T00:00",
            "2026-03-25T12:00",
            "2026-03-25T15:00",
        ],
        "wind_gusts_10m": [12.0, 22.0, 28.0],
    },
    "daily": {
        "temperature_2m_max": [61.0, 70.0],
        "temperature_2m_min": [44.0, 49.0],
        "sunrise": ["2026-03-25T06:52"],
        "sunset": ["2026-03-25T19:31"],
        "precipitation_probability_max": [10.0, 20.0],
        "weathercode": [3, 1],
    }
}

NOMINATIM_RESPONSE = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, NY, USA"}]
NWS_ALERTS_EMPTY = {"features": []}
NWS_ALERTS_RESPONSE = {
    "features": [
        {
            "properties": {
                "event": "Wind Advisory",
                "severity": "Moderate",
                "ends": "2026-03-25T08:00:00-04:00",
            }
        }
    ]
}

def test_wmo_label_known_code():
    assert wmo_label(0) == "Clear Sky"
    assert wmo_label(3) == "Overcast"
    assert wmo_label(61) == "Light Rain"

def test_wmo_label_unknown_code():
    assert wmo_label(999) == "Unknown"

def test_fetch_weather_returns_structured_data(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://api.weather.gov/alerts/active", json=NWS_ALERTS_EMPTY)
    result = fetch_weather(41.2512, -74.3607, "Warwick, NY")
    assert result["location"] == "Warwick, NY"
    assert result["temp"] == 54
    assert result["condition"] == "Overcast"
    assert result["high"] == 61
    assert result["low"] == 44
    assert result["sunrise"] == "6:52am"
    assert result["sunset"] == "7:31pm"
    assert result["summary"] == "Overcast today, with gusts up to 28 mph this afternoon."

def test_fetch_weather_returns_none_on_error(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", status_code=500)
    result = fetch_weather(41.2512, -74.3607, "Warwick, NY")
    assert result is None

def test_fetch_weather_prefers_official_alerts(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://api.weather.gov/alerts/active", json=NWS_ALERTS_RESPONSE)
    result = fetch_weather(41.2512, -74.3607, "Warwick, NY")
    assert result["summary"] == "Wind Advisory in effect until 8:00am. Overcast today, with gusts up to 28 mph this afternoon."

def test_geocode_location_returns_lat_lon(requests_mock):
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    result = geocode_location("New York, NY")
    assert result["lat"] == pytest.approx(40.7128, rel=1e-3)
    assert result["lon"] == pytest.approx(-74.0060, rel=1e-3)
    assert result["name"] == "New York, NY, USA"

def test_geocode_location_returns_none_on_no_results(requests_mock):
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=[])
    result = geocode_location("Nowhere")
    assert result is None

def test_weather_block_default_only(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://api.weather.gov/alerts/active", json=NWS_ALERTS_EMPTY)
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    result = weather_block(config, calendar_events=[])
    assert len(result["locations"]) == 1
    assert result["locations"][0]["location"] == "Warwick, NY"
    assert result["travel_city"] is None

def test_weather_block_with_travel(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    requests_mock.get("https://api.weather.gov/alerts/active", json=NWS_ALERTS_EMPTY)
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    events = [{"title": "Meeting", "location": "New York, NY", "calendar": "TripIt", "all_day": False, "start": "9:00am"}]
    result = weather_block(config, calendar_events=events)
    assert len(result["locations"]) == 2
    assert result["travel_city"] == "New York"

def test_weather_block_ignores_non_travel_calendars(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    requests_mock.get("https://api.weather.gov/alerts/active", json=NWS_ALERTS_EMPTY)
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    events = [{"title": "Bills game", "location": "New York, NY", "calendar": "Buffalo Bills", "all_day": False, "start": "1:00pm"}]
    result = weather_block(config, calendar_events=events)
    assert len(result["locations"]) == 1
    assert result["travel_city"] is None

def test_weather_block_returns_none_on_failure(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", status_code=500)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=[])
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    result = weather_block(config, calendar_events=[])
    assert result is None
