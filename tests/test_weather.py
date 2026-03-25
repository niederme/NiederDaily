import pytest

from modules.weather import fetch_weather, geocode_location, wmo_label, weather_block

OPEN_METEO_RESPONSE = {
    "current": {"temperature_2m": 54.1, "weathercode": 3},
    "daily": {
        "temperature_2m_max": [61.0],
        "temperature_2m_min": [44.0],
        "sunrise": ["2026-03-25T06:52"],
        "sunset": ["2026-03-25T19:31"],
    }
}

NOMINATIM_RESPONSE = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, NY, USA"}]

def test_wmo_label_known_code():
    assert wmo_label(0) == "Clear Sky"
    assert wmo_label(3) == "Overcast"
    assert wmo_label(61) == "Light Rain"

def test_wmo_label_unknown_code():
    assert wmo_label(999) == "Unknown"

def test_fetch_weather_returns_structured_data(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    result = fetch_weather(41.2512, -74.3607, "Warwick, NY")
    assert result["location"] == "Warwick, NY"
    assert result["temp"] == 54
    assert result["condition"] == "Overcast"
    assert result["high"] == 61
    assert result["low"] == 44
    assert result["sunrise"] == "6:52am"
    assert result["sunset"] == "7:31pm"

def test_fetch_weather_returns_none_on_error(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", status_code=500)
    result = fetch_weather(41.2512, -74.3607, "Warwick, NY")
    assert result is None

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
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    result = weather_block(config, calendar_events=[])
    assert len(result["locations"]) == 1
    assert result["locations"][0]["location"] == "Warwick, NY"
    assert result["travel_city"] is None

def test_weather_block_with_travel(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", json=OPEN_METEO_RESPONSE)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    events = [{"title": "Meeting", "location": "New York, NY", "all_day": False, "start": "9:00am"}]
    result = weather_block(config, calendar_events=events)
    assert len(result["locations"]) == 2
    assert result["travel_city"] == "New York"

def test_weather_block_returns_none_on_failure(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", status_code=500)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=[])
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    result = weather_block(config, calendar_events=[])
    assert result is None
