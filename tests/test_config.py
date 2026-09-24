import json
import pytest

from config import load_config, ConfigError

def test_load_valid_config(tmp_path):
    cfg = {
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "abc123",
        "anthropic_api_key": "sk-ant-123",
        "weatherkit": {
            "team_id": "TEAMID1234",
            "service_id": "com.niederme.weatherkit",
            "key_id": "KEYID12345",
            "key_file": "/fake/path/AuthKey.p8",
        },
        "reminders_lists": []
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["recipient_email"] == "me@example.com"
    assert result["default_location"]["lat"] == 41.2512

def test_missing_required_key_raises(tmp_path):
    cfg = {"recipient_email": "me@example.com"}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="default_location"):
        load_config(str(p))

def test_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/path/config.json")


@pytest.mark.parametrize("radius", [-1, "25", True, None, float("inf"), float("nan")])
def test_invalid_weather_travel_radius_raises(tmp_path, radius):
    cfg = {
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "abc123",
        "anthropic_api_key": "test-key",
        "weatherkit": {"team_id": "T", "service_id": "S", "key_id": "K", "key_file": "/fake/key.p8"},
        "weather_travel_min_miles": radius,
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))

    with pytest.raises(ConfigError, match="weather_travel_min_miles"):
        load_config(str(p))

def test_unfilled_placeholder_raises(tmp_path):
    cfg = {
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "FILL_IN",
        "anthropic_api_key": "sk-ant-123",
        "reminders_lists": []
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="nyt_api_key"):
        load_config(str(p))
