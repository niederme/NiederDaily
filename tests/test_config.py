import json
import pytest

from config import load_config, ConfigError

def test_load_valid_config(tmp_path):
    cfg = {
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "abc123",
        "anthropic_api_key": "sk-ant-123",
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
