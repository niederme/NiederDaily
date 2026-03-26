import pytest
from unittest.mock import patch, MagicMock
from config import load_config, ConfigError
import json

# ── Fixtures ──────────────────────────────────────────────────────────────────

WEATHERKIT_CONFIG = {
    "recipient_email": "a@b.com",
    "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
    "nyt_api_key": "k",
    "anthropic_api_key": "test-key",
    "weatherkit": {
        "team_id": "TEAMID1234",
        "service_id": "com.niederme.weatherkit",
        "key_id": "KEYID12345",
        "key_file": "/fake/path/AuthKey.p8",
    },
}

WEATHERKIT_RESPONSE = {
    "currentWeather": {
        "conditionCode": "PartlyCloudy",
        "temperature": 54.1,
        "humidity": 0.65,
        "precipitationIntensity": 0.0,
        "pressure": 1013.0,
        "pressureTrend": "rising",
        "temperatureApparent": 52.0,
        "temperatureDewPoint": 45.0,
        "uvIndex": 3,
        "visibility": 10000.0,
        "windSpeed": 10.0,
    },
    "forecastDaily": {
        "days": [{
            "conditionCode": "PartlyCloudy",
            "temperatureMax": 61.0,
            "temperatureMin": 44.0,
            "sunrise": "2026-03-25T06:52:00-05:00",
            "sunset": "2026-03-25T19:31:00-05:00",
        }]
    },
}

WEATHERKIT_RESPONSE_WITH_ALERT = {
    **WEATHERKIT_RESPONSE,
    "weatherAlerts": {
        "alerts": [{
            "eventSource": "NWS",
            "eventOnset": "2026-03-25T00:00:00Z",
            "eventEndTime": "2026-03-26T18:00:00Z",
            "severity": "Severe",
            "urgency": "Expected",
            "certainty": "Likely",
            "areaId": "ILZ014",
            "areaName": "Cook",
            "attributionURL": "https://alerts.weather.gov/cap/wwlxml.php?warnid=ILZ014.NWS.FLOOD",
            "countryCode": "US",
            "description": "...full text...",
            "detailsUrl": "https://alerts.weather.gov/cap/wwlxml.php?warnid=ILZ014.NWS.FLOOD",
            "eventText": "Flood Watch",
            "issuedTime": "2026-03-25T00:00:00Z",
            "responses": ["Prepare"],
            "source": "National Weather Service",
        }]
    }
}

NOMINATIM_RESPONSE = [{"lat": "40.7128", "lon": "-74.0060", "display_name": "New York, NY, USA"}]

# ── Config tests ──────────────────────────────────────────────────────────────

def test_config_requires_weatherkit_keys(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "recipient_email": "a@b.com",
        "default_location": {"name": "X", "lat": 0.0, "lon": 0.0},
        "nyt_api_key": "k",
        "anthropic_api_key": "k",
    }))
    with pytest.raises(ConfigError, match="weatherkit"):
        load_config(str(cfg_file))

def test_config_requires_weatherkit_subkeys(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "recipient_email": "a@b.com",
        "default_location": {"name": "X", "lat": 0.0, "lon": 0.0},
        "nyt_api_key": "k",
        "anthropic_api_key": "k",
        "weatherkit": {"team_id": "T"},
    }))
    with pytest.raises(ConfigError, match="weatherkit"):
        load_config(str(cfg_file))

# ── JWT tests ─────────────────────────────────────────────────────────────────

def test_make_jwt_correct_claims(tmp_path):
    key_file = tmp_path / "AuthKey.p8"
    key_file.write_text("fake-key")
    cfg = {**WEATHERKIT_CONFIG, "weatherkit": {**WEATHERKIT_CONFIG["weatherkit"], "key_file": str(key_file)}}

    with patch("modules.weather.jwt.encode", return_value="tok") as mock_encode:
        from modules.weather import _make_jwt
        result = _make_jwt(cfg)

    assert result == "tok"
    payload = mock_encode.call_args.args[0]
    kwargs = mock_encode.call_args.kwargs
    assert payload["iss"] == "TEAMID1234"
    assert payload["sub"] == "com.niederme.weatherkit"
    assert payload["exp"] - payload["iat"] == 1800
    assert kwargs["algorithm"] == "ES256"
    assert kwargs["headers"]["kid"] == "KEYID12345"
    assert kwargs["headers"]["typ"] == "JWT"

# ── Condition mapping tests ───────────────────────────────────────────────────

def test_condition_label_known_code():
    from modules.weather import CONDITION_LABELS
    assert CONDITION_LABELS["PartlyCloudy"] == "Partly Cloudy"
    assert CONDITION_LABELS["Thunderstorms"] == "Thunderstorms"
    assert CONDITION_LABELS["Blizzard"] == "Blizzard"

def test_condition_unknown_code_falls_back():
    from modules.weather import CONDITION_LABELS
    assert CONDITION_LABELS.get("XyzUnknown", "Unknown") == "Unknown"

# ── fetch_weather tests ───────────────────────────────────────────────────────

def test_fetch_weather_returns_structured_data(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE,
    )
    with patch("modules.weather._make_jwt", return_value="test-token"):
        from modules.weather import fetch_weather
        result = fetch_weather(41.2512, -74.3607, "Warwick, NY", WEATHERKIT_CONFIG)

    assert result["location"] == "Warwick, NY"
    assert result["temp"] == 54
    assert result["condition"] == "Partly Cloudy"
    assert result["high"] == 61
    assert result["low"] == 44
    assert result["sunrise"] == "6:52am"
    assert result["sunset"] == "7:31pm"
    assert result["alerts"] == []
    assert result["sentence"] == ""

def test_fetch_weather_parses_alerts(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE_WITH_ALERT,
    )
    with patch("modules.weather._make_jwt", return_value="test-token"):
        from modules.weather import fetch_weather
        result = fetch_weather(41.2512, -74.3607, "Warwick, NY", WEATHERKIT_CONFIG)

    assert len(result["alerts"]) == 1
    alert = result["alerts"][0]
    assert alert["event"] == "Flood Watch"
    assert alert["agency"] == "National Weather Service"
    assert "alerts.weather.gov" in alert["url"]
    assert "expires" in alert

def test_fetch_weather_handles_missing_alerts_key(requests_mock):
    """Regions without alert support return no weatherAlerts key."""
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE,  # no weatherAlerts key
    )
    with patch("modules.weather._make_jwt", return_value="test-token"):
        from modules.weather import fetch_weather
        result = fetch_weather(41.2512, -74.3607, "Warwick, NY", WEATHERKIT_CONFIG)

    assert result["alerts"] == []

def test_fetch_weather_returns_none_on_error(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        status_code=500,
    )
    with patch("modules.weather._make_jwt", return_value="test-token"):
        from modules.weather import fetch_weather
        result = fetch_weather(41.2512, -74.3607, "Warwick, NY", WEATHERKIT_CONFIG)

    assert result is None

def test_fmt_time_handles_rfc3339():
    from modules.weather import _fmt_time
    assert _fmt_time("2026-03-25T06:52:00-05:00") == "6:52am"
    assert _fmt_time("2026-03-25T19:31:00-05:00") == "7:31pm"

# ── geocode tests (unchanged) ─────────────────────────────────────────────────

def test_geocode_location_returns_lat_lon(requests_mock):
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    from modules.weather import geocode_location
    result = geocode_location("New York, NY")
    assert result["lat"] == pytest.approx(40.7128, rel=1e-3)
    assert result["lon"] == pytest.approx(-74.0060, rel=1e-3)
    assert result["name"] == "New York, NY, USA"

def test_geocode_location_returns_none_on_no_results(requests_mock):
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=[])
    from modules.weather import geocode_location
    result = geocode_location("Nowhere")
    assert result is None

# ── weather_block tests ───────────────────────────────────────────────────────

def test_weather_block_default_only(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE,
    )
    with patch("modules.weather._make_jwt", return_value="tok"):
        from modules.weather import weather_block
        result = weather_block(WEATHERKIT_CONFIG, calendar_events=[])

    assert len(result["locations"]) == 1
    assert result["locations"][0]["location"] == "Warwick, NY"
    assert result["locations"][0]["sentence"] == ""  # sentence set by orchestrator, not here
    assert result["travel_city"] is None

def test_weather_block_with_travel(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE,
    )
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/40.7128/-74.006",
        json=WEATHERKIT_RESPONSE,
    )
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=NOMINATIM_RESPONSE)
    with patch("modules.weather._make_jwt", return_value="tok"):
        from modules.weather import weather_block
        # calendar field must match a travel calendar or the event is skipped
        events = [{"title": "Meeting", "location": "New York, NY", "all_day": False,
                   "start": "9:00am", "calendar": "niederCal"}]
        result = weather_block(WEATHERKIT_CONFIG, calendar_events=events)

    assert len(result["locations"]) == 2
    assert result["travel_city"] == "New York"

def test_weather_block_ignores_events_from_non_travel_calendars(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        json=WEATHERKIT_RESPONSE,
    )
    with patch("modules.weather._make_jwt", return_value="tok"):
        from modules.weather import weather_block
        events = [{"title": "Meeting", "location": "New York, NY", "all_day": False,
                   "start": "9:00am", "calendar": "Work"}]  # not in travel_calendars
        result = weather_block(WEATHERKIT_CONFIG, calendar_events=events)

    assert len(result["locations"]) == 1  # travel not triggered

def test_weather_block_returns_none_on_failure(requests_mock):
    requests_mock.get(
        "https://weatherkit.apple.com/api/v1/weather/en/41.2512/-74.3607",
        status_code=500,
    )
    with patch("modules.weather._make_jwt", return_value="tok"):
        from modules.weather import weather_block
        result = weather_block(WEATHERKIT_CONFIG, calendar_events=[])

    assert result is None

def test_weather_sentence_returns_string():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Bundle up today.")]
        mock_anthropic.return_value.messages.create.return_value = mock_resp
        from modules.weather import weather_sentence
        loc = {"location": "Warwick, NY", "temp": 54, "condition": "Partly Cloudy", "high": 61, "low": 44}
        result = weather_sentence(loc, "test-key")
    assert result == "Bundle up today."

def test_weather_sentence_returns_empty_on_failure():
    with patch("anthropic.Anthropic", side_effect=Exception("API down")):
        from modules.weather import weather_sentence
        loc = {"location": "X", "temp": 50, "condition": "Clear", "high": 60, "low": 40}
        result = weather_sentence(loc, "bad-key")
    assert result == ""
