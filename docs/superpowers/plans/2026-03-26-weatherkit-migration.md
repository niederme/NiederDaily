# WeatherKit Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Open-Meteo with Apple WeatherKit REST API, adding emoji icons, Haiku-generated weather sentences, and linked severe weather alerts.

**Architecture:** `modules/weather.py` is fully rewritten — JWT generation, WeatherKit fetch, and condition maps live there. The Haiku sentence is generated in `niederdaily.py` (not `weather_block`) to avoid burning two model calls per run, since `weather_block` is called twice in the orchestrator. `renderer.py._weather_html()` gains icon, sentence, alert banner, and attribution rendering. All new behavior is covered by tests before implementation.

**Tech Stack:** Python 3.11+, `PyJWT[cryptography]` (ES256 JWT), `requests` (already present), `anthropic` (already present), `requests-mock` (already present in test deps)

---

## File Map

| File | What changes |
|------|-------------|
| `requirements.txt` | Add `PyJWT[cryptography]>=2.8.0` |
| `config.py` | Add `weatherkit` sub-key validation to `REQUIRED_KEYS` |
| `modules/weather.py` | Full rewrite — removes Open-Meteo, adds WeatherKit |
| `renderer.py` | Update `_weather_html()` only |
| `niederdaily.py` | Update preflight + add single Haiku sentence call after final weather |
| `tests/test_weather.py` | Full rewrite with WeatherKit mocks |
| `tests/test_renderer_weather.py` | New file — tests for `_weather_html()` changes |

---

## Task 1: Add PyJWT dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

```
# requirements.txt — add after anthropic line:
PyJWT[cryptography]>=2.8.0
```

- [ ] **Step 2: Install it**

```bash
pip install "PyJWT[cryptography]>=2.8.0"
```

Expected: installs without error; `python -c "import jwt; print(jwt.__version__)"` prints a version ≥ 2.8.0.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add PyJWT[cryptography] for WeatherKit JWT auth"
```

---

## Task 2: Config validation

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py` (temporary location — will be replaced in Task 4):

```python
# At top of file, add this import:
from config import load_config, ConfigError
import json, tempfile, os

def test_config_requires_weatherkit_keys(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "recipient_email": "a@b.com",
        "default_location": {"name": "X", "lat": 0.0, "lon": 0.0},
        "nyt_api_key": "k",
        "anthropic_api_key": "k",
        # weatherkit block intentionally missing
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
        "weatherkit": {"team_id": "T"},  # missing service_id, key_id, key_file
    }))
    with pytest.raises(ConfigError, match="weatherkit"):
        load_config(str(cfg_file))

def test_config_rejects_blank_weatherkit_subkeys(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "recipient_email": "a@b.com",
        "default_location": {"name": "X", "lat": 0.0, "lon": 0.0},
        "nyt_api_key": "k",
        "anthropic_api_key": "k",
        "weatherkit": {"team_id": "", "service_id": "com.x", "key_id": "K", "key_file": "/p"},
    }))
    with pytest.raises(ConfigError, match="weatherkit"):
        load_config(str(cfg_file))

def test_config_rejects_fill_in_weatherkit_subkeys(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "recipient_email": "a@b.com",
        "default_location": {"name": "X", "lat": 0.0, "lon": 0.0},
        "nyt_api_key": "k",
        "anthropic_api_key": "k",
        "weatherkit": {"team_id": "FILL_IN", "service_id": "com.x", "key_id": "K", "key_file": "/p"},
    }))
    with pytest.raises(ConfigError, match="weatherkit"):
        load_config(str(cfg_file))
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_weather.py::test_config_requires_weatherkit_keys -v
```

Expected: FAIL — config loads without error currently (no weatherkit validation).

- [ ] **Step 3: Update `config.py`**

```python
import json
from pathlib import Path

REQUIRED_KEYS = ["recipient_email", "default_location", "nyt_api_key", "anthropic_api_key", "weatherkit"]
REQUIRED_WEATHERKIT_KEYS = ["team_id", "service_id", "key_id", "key_file"]

class ConfigError(Exception):
    pass

def load_config(path: str = None) -> dict:
    if path is None:
        path = Path.home() / ".niederdaily" / "config.json"
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    try:
        cfg = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {e}")
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ConfigError(f"Missing required config key: {key}")
        if cfg[key] == "FILL_IN":
            raise ConfigError(f"Config key not filled in: {key}")
    wk = cfg.get("weatherkit", {})
    for sub in REQUIRED_WEATHERKIT_KEYS:
        if sub not in wk:
            raise ConfigError(f"Missing required weatherkit config key: {sub}")
        if not wk[sub] or wk[sub] == "FILL_IN":
            raise ConfigError(f"weatherkit config key not filled in: {sub}")
    return cfg
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_weather.py::test_config_requires_weatherkit_keys tests/test_weather.py::test_config_requires_weatherkit_subkeys -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_weather.py
git commit -m "feat: validate weatherkit config keys at startup"
```

---

## Task 3: JWT generation

**Files:**
- Modify: `modules/weather.py` (add `_make_jwt` only — rest of file stays for now)
- Modify: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_weather.py:
from unittest.mock import patch, MagicMock

WEATHERKIT_CONFIG = {
    "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
    "anthropic_api_key": "test-anthropic-key",
    "weatherkit": {
        "team_id": "TEAMID1234",
        "service_id": "com.niederme.weatherkit",
        "key_id": "KEYID12345",
        "key_file": "/fake/path/AuthKey.p8",
    },
}

def test_make_jwt_correct_claims(tmp_path):
    # Write a fake key file (content doesn't matter — we mock jwt.encode)
    key_file = tmp_path / "AuthKey.p8"
    key_file.write_text("-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----\n")
    cfg = {**WEATHERKIT_CONFIG, "weatherkit": {**WEATHERKIT_CONFIG["weatherkit"], "key_file": str(key_file)}}

    with patch("modules.weather.jwt.encode", return_value="tok") as mock_encode:
        from modules.weather import _make_jwt
        result = _make_jwt(cfg)

    assert result == "tok"
    payload, key, *_ = mock_encode.call_args.args
    kwargs = mock_encode.call_args.kwargs
    assert payload["iss"] == "TEAMID1234"
    assert payload["sub"] == "com.niederme.weatherkit"
    assert "iat" in payload and "exp" in payload
    assert payload["exp"] - payload["iat"] == 1800
    assert kwargs["algorithm"] == "ES256"
    assert kwargs["headers"]["kid"] == "KEYID12345"
    assert kwargs["headers"]["typ"] == "JWT"
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_weather.py::test_make_jwt_correct_claims -v
```

Expected: FAIL — `_make_jwt` not yet defined.

- [ ] **Step 3: Add `_make_jwt` to `modules/weather.py`**

Add these imports and function at the top of the existing file (do not remove existing code yet):

```python
import jwt
import time

WEATHERKIT_URL = "https://weatherkit.apple.com/api/v1/weather/en"


def _make_jwt(config: dict) -> str:
    wk = config["weatherkit"]
    key = Path(wk["key_file"]).expanduser().read_text()
    now = int(time.time())
    return jwt.encode(
        {"iss": wk["team_id"], "sub": wk["service_id"], "iat": now, "exp": now + 1800},
        key,
        algorithm="ES256",
        headers={"kid": wk["key_id"], "typ": "JWT"},
    )
```

Also add `from pathlib import Path` to imports.

- [ ] **Step 4: Run test**

```bash
pytest tests/test_weather.py::test_make_jwt_correct_claims -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/weather.py tests/test_weather.py
git commit -m "feat: add WeatherKit JWT generation"
```

---

## Task 4: Rewrite `fetch_weather`

**Files:**
- Modify: `modules/weather.py` (full rewrite — remove Open-Meteo code)
- Modify: `tests/test_weather.py` (replace Open-Meteo tests)

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_weather.py` with:

```python
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

def _mock_haiku(text="Bundle up today."):
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=text)]
    return mock_resp

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

def test_weather_sentence_returns_string(requests_mock):
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Bundle up today.")]
        mock_anthropic.return_value.messages.create.return_value = mock_resp
        from modules.weather import weather_sentence
        loc = {**WEATHERKIT_RESPONSE["currentWeather"], "location": "Warwick, NY",
               "temp": 54, "condition": "Partly Cloudy", "high": 61, "low": 44}
        result = weather_sentence(loc, "test-key")
    assert result == "Bundle up today."

def test_weather_sentence_returns_empty_on_failure():
    with patch("anthropic.Anthropic", side_effect=Exception("API down")):
        from modules.weather import weather_sentence
        loc = {"location": "X", "temp": 50, "condition": "Clear", "high": 60, "low": 40}
        result = weather_sentence(loc, "bad-key")
    assert result == ""
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/test_weather.py -v 2>&1 | head -60
```

Expected: many FAILs — `fetch_weather` still uses Open-Meteo signature, no WeatherKit code yet.

- [ ] **Step 3: Rewrite `modules/weather.py`**

```python
import jwt
import time
import requests
from datetime import datetime
from pathlib import Path

import anthropic

WEATHERKIT_URL = "https://weatherkit.apple.com/api/v1/weather/en"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "NiederDaily/1.0 (personal newsletter)"

CONDITION_LABELS = {
    "Clear": "Clear",
    "MostlyClear": "Mostly Clear",
    "PartlyCloudy": "Partly Cloudy",
    "MostlyCloudy": "Mostly Cloudy",
    "Cloudy": "Cloudy",
    "Foggy": "Foggy",
    "Haze": "Hazy",
    "Smoky": "Smoky",
    "Breezy": "Breezy",
    "Windy": "Windy",
    "Drizzle": "Drizzle",
    "Rain": "Rain",
    "HeavyRain": "Heavy Rain",
    "SunShowers": "Sun Showers",
    "Thunderstorms": "Thunderstorms",
    "IsolatedThunderstorms": "Isolated Thunderstorms",
    "ScatteredThunderstorms": "Scattered Thunderstorms",
    "StrongStorms": "Strong Storms",
    "Flurries": "Flurries",
    "Snow": "Snow",
    "SunFlurries": "Sun Flurries",
    "Sleet": "Sleet",
    "WintryMix": "Wintry Mix",
    "FreezingDrizzle": "Freezing Drizzle",
    "FreezingRain": "Freezing Rain",
    "BlowingSnow": "Blowing Snow",
    "HeavySnow": "Heavy Snow",
    "Blizzard": "Blizzard",
    "BlowingDust": "Blowing Dust",
    "Frigid": "Frigid",
    "Hail": "Hail",
    "Hot": "Hot",
    "Hurricane": "Hurricane",
    "TropicalStorm": "Tropical Storm",
}

# Note: no CONDITION_ICONS dict needed — renderer uses existing _weather_icon() SVGs,
# which keyword-match on the condition string (e.g. "rain", "snow", "thunder", "clear", "fog").
# WeatherKit label strings ("Rain", "Snow", "Thunderstorms", "Clear", "Foggy", etc.)
# match the existing patterns without any changes to _weather_icon().


def _make_jwt(config: dict) -> str:
    wk = config["weatherkit"]
    key = Path(wk["key_file"]).expanduser().read_text()
    now = int(time.time())
    return jwt.encode(
        {"iss": wk["team_id"], "sub": wk["service_id"], "iat": now, "exp": now + 1800},
        key,
        algorithm="ES256",
        headers={"kid": wk["key_id"], "typ": "JWT"},
    )


def _fmt_time(iso: str) -> str:
    """Convert RFC 3339 timestamp (e.g. '2026-03-25T06:52:00-05:00') to '6:52am'."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return iso


def _parse_alert(raw: dict) -> dict:
    expires_raw = raw.get("eventEndTime", "")
    try:
        expires = datetime.fromisoformat(expires_raw).strftime("%a %-I:%M%p").lower()
        # e.g. "thu 6:00pm"
        expires = expires[0].upper() + expires[1:]  # capitalize day
    except Exception:
        expires = expires_raw
    return {
        "event": raw.get("eventText", "Weather Alert"),
        "expires": expires,
        "agency": raw.get("source", ""),
        "url": raw.get("detailsUrl", ""),
    }


def fetch_weather(lat: float, lon: float, name: str, config: dict) -> dict | None:
    try:
        token = _make_jwt(config)
        resp = requests.get(
            f"{WEATHERKIT_URL}/{lat}/{lon}",
            params={
                "dataSets": "currentWeather,forecastDaily,weatherAlerts",
                "unitSystem": "imperial",
                "countryCode": "US",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data["currentWeather"]
        code = current["conditionCode"]
        today = data["forecastDaily"]["days"][0]
        alerts_raw = data.get("weatherAlerts", {}).get("alerts", [])

        return {
            "location": name,
            "temp": round(current["temperature"]),
            "condition": CONDITION_LABELS.get(code, "Unknown"),
            "high": round(today["temperatureMax"]),
            "low": round(today["temperatureMin"]),
            "sunrise": _fmt_time(today["sunrise"]),
            "sunset": _fmt_time(today["sunset"]),
            "alerts": [_parse_alert(a) for a in alerts_raw],
            "sentence": "",  # populated by niederdaily.py after final weather call
        }
    except Exception:
        return None


def geocode_location(location_str: str) -> dict | None:
    try:
        resp = requests.get(NOMINATIM_URL, params={
            "q": location_str, "format": "json", "limit": 1,
        }, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        r = results[0]
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "name": r["display_name"]}
    except Exception:
        return None


def weather_sentence(loc: dict, api_key: str) -> str:
    """Generate a one-sentence Haiku description for a single location dict.
    Returns "" on any failure — never raises.
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Write a single short sentence describing today's weather for {loc['location']}. "
            f"Current: {loc['temp']}°F, {loc['condition']}. "
            f"High {loc['high']}°, Low {loc['low']}°. "
            f"Be specific and vivid. No greeting. Plain text only."
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""


DEFAULT_TRAVEL_CALENDARS = {"Little York", "niederCal", "TripIt"}


def weather_block(config: dict, calendar_events: list) -> dict | None:
    default = config["default_location"]
    home = fetch_weather(default["lat"], default["lon"], default["name"], config)
    if home is None:
        return None

    travel = None
    travel_city = None
    travel_calendars = set(config.get("weather_calendars", DEFAULT_TRAVEL_CALENDARS))
    for event in sorted(calendar_events, key=lambda e: (e.get("all_day", True), e.get("start", ""))):
        source_calendar = event.get("calendar")
        if source_calendar not in travel_calendars:
            continue
        loc = event.get("location", "").strip()
        if not loc:
            continue
        geo = geocode_location(loc)
        if geo is None:
            continue
        if default["name"].split(",")[0].lower() not in geo["name"].lower():
            travel = fetch_weather(geo["lat"], geo["lon"], geo["name"].split(",")[0].strip(), config)
            travel_city = geo["name"].split(",")[0].strip()
            break

    locations = [home]
    if travel:
        locations.append(travel)

    return {"locations": locations, "travel_city": travel_city}
```

- [ ] **Step 4: Run all weather tests**

```bash
pytest tests/test_weather.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/weather.py tests/test_weather.py
git commit -m "feat: replace Open-Meteo with WeatherKit REST API"
```

---

## Task 5: Update renderer

The real renderer (`renderer.py` lines 187–204) uses:
- CSS classes (`.weather-card`, `.weather-summary`, `.weather-meta`) — not inline styles
- SVG icons via `_weather_icon(loc["condition"])` — not emoji; condition string keyword-matches already work with WeatherKit label strings
- `_section(None, body, show_rule=False)` — no label, no divider rule
- `loc["summary"]` for the description — rename to `loc["sentence"]`

Changes needed: rename `summary` → `sentence`, add alert banner + attribution (new elements, inline styles), keep everything else intact.

**Files:**
- Modify: `renderer.py` (`_weather_html` only — lines 187–204)
- Create: `tests/test_renderer_weather.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_renderer_weather.py`:

```python
from renderer import _weather_html

BASE_LOC = {
    "location": "Warwick, NY",
    "temp": 54,
    "condition": "Partly Cloudy",
    "high": 61,
    "low": 44,
    "sunrise": "6:52am",
    "sunset": "7:31pm",
    "alerts": [],
    "sentence": "A partly cloudy afternoon with highs in the low 60s.",
}

def test_weather_html_shows_location():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "Warwick, NY" in html

def test_weather_html_shows_high_low():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "61°" in html
    assert "44°" in html

def test_weather_html_shows_sentence():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "A partly cloudy afternoon" in html
    assert 'weather-summary' in html

def test_weather_html_omits_sentence_div_when_empty():
    loc = {**BASE_LOC, "sentence": ""}
    html = _weather_html({"locations": [loc]})
    assert "weather-summary" not in html

def test_weather_html_shows_sunrise_sunset():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "6:52am" in html
    assert "7:31pm" in html

def test_weather_html_no_rule_or_label():
    """section-rule div and section label must not appear — show_rule=False, label=None."""
    html = _weather_html({"locations": [BASE_LOC]})
    assert "section-rule" not in html
    assert "WEATHER ·" not in html

def test_weather_html_no_alert_when_empty():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "⚠" not in html

def test_weather_html_shows_alert_banner():
    loc = {**BASE_LOC, "alerts": [{
        "event": "Flood Watch",
        "expires": "Thu 6:00pm",
        "agency": "NWS Chicago",
        "url": "https://alerts.weather.gov/example",
    }]}
    html = _weather_html({"locations": [loc]})
    assert "⚠" in html
    assert "Flood Watch" in html
    assert "alerts.weather.gov" in html
    assert "Thu 6:00pm" in html
    assert "NWS Chicago" in html

def test_weather_html_alert_uses_inline_styles_not_class():
    """Alert banner has no CSS class — uses inline styles (email client compatibility)."""
    loc = {**BASE_LOC, "alerts": [{
        "event": "Winter Storm Warning",
        "expires": "Fri 9:00am",
        "agency": "NWS",
        "url": "https://alerts.weather.gov/example",
    }]}
    html = _weather_html({"locations": [loc]})
    assert 'style=' in html
    assert 'class="alert' not in html

def test_weather_html_shows_attribution():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "weatherkit.apple.com/legal-attribution.html" in html
    assert ">Weather<" in html
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/test_renderer_weather.py -v
```

Expected: `test_weather_html_no_rule_or_label` PASS (already correct), `test_weather_html_shows_sentence` FAIL (uses `summary` key), alert/attribution tests FAIL (not yet added).

- [ ] **Step 3: Update `_weather_html()` in `renderer.py`**

Replace the existing `_weather_html` function (lines 187–204) with:

```python
def _weather_html(data: dict) -> str:
    parts = []
    for loc in data["locations"]:
        # sentence replaces summary — same CSS class, same position
        sentence_html = ""
        if loc.get("sentence"):
            sentence_html = f'<div class="weather-summary">{_esc(loc["sentence"])}</div>'

        # alert banner (new — inline styles, no CSS class)
        alert_html = ""
        for alert in loc.get("alerts", []):
            alert_html += (
                f'<div style="margin-top:10px;padding:8px 0;border-top:1px solid rgba(214,208,198,0.6);">'
                f'<div style="font-size:12px;font-weight:600;color:#ff453a;">'
                f'⚠ <a href="{_esc(alert["url"])}" style="color:#ff453a;text-decoration:none;">'
                f'{_esc(alert["event"])} →</a></div>'
                f'<div style="font-size:11px;color:{MUTED};margin-top:2px;">'
                f'Until {_esc(alert["expires"])} · {_esc(alert["agency"])}</div>'
                f'</div>'
            )

        # attribution (Apple requirement — inline styles)
        attribution_html = (
            f'<div style="font-size:10px;color:#9aa0a6;margin-top:8px;">'
            f'<a href="https://weatherkit.apple.com/legal-attribution.html" '
            f'style="color:#9aa0a6;text-decoration:none;">Weather</a></div>'
        )

        body = (
            f'<div class="weather-card">'
            f'<div class="module-place">{_esc(loc["location"])}</div>'
            f'<div class="display-line">'
            f'{_weather_icon(loc["condition"])}'
            f'<span>{loc["high"]}° / {loc["low"]}°</span></div>'
            f'{sentence_html}'
            f'<div class="weather-meta">Sunrise {_esc(loc["sunrise"])} · Sunset {_esc(loc["sunset"])}</div>'
            f'{alert_html}'
            f'{attribution_html}'
            f'</div>'
        )
        parts.append(_section(None, body, show_rule=False))  # preserve: no rule, no label
    return "".join(parts)
```

Note: alert accent color uses `#ff453a` (the existing `ACCENT` constant) rather than `#c0392b` to stay on-palette.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_renderer_weather.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add renderer.py tests/test_renderer_weather.py
git commit -m "feat: update weather renderer — sentence, alert banner, attribution"
```

---

## Task 6: Update `niederdaily.py` — sentence call + preflight

**Files:**
- Modify: `niederdaily.py`

- [ ] **Step 1: Add the sentence call after final weather result**

First, update the import at the top of `niederdaily.py` (line 18):
```python
# Before:
from modules.weather import weather_block
# After:
from modules.weather import weather_block, weather_sentence
```

Then, after the two `weather_block` calls (lines 37–42), add:

```python

# (existing lines 37-42 unchanged — note calendar_block takes conf.get("calendars"))
weather = _safe(weather_block, conf, calendar_events=[])
calendar = _safe(calendar_block, conf.get("calendars"))

if calendar:
    weather = _safe(weather_block, conf, calendar_events=calendar)

# Generate Haiku sentence once, for home location only
if weather:
    home = weather["locations"][0]
    home["sentence"] = weather_sentence(home, conf["anthropic_api_key"])
```

- [ ] **Step 2: Replace the Open-Meteo preflight block**

The real `preflight()` uses a `report()` helper and `blocking_ok`/`warnings` vars (not `ok`). The `import requests` at line 180 is shared with the NYT check that follows — keep it in place.

Find this block in `niederdaily.py` (lines 179–194):

```python
    # Open-Meteo
    import requests
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", ...)
        r.raise_for_status()
        print("✓ Open-Meteo")
    except Exception as e:
        report("Open-Meteo", False, "", f"{e}. ...", blocking=False)
```

Replace it with (keep `import requests` — NYT check below uses it):

```python
    # WeatherKit
    import requests
    try:
        from modules.weather import _make_jwt
        token = _make_jwt(conf)
        lat = conf["default_location"]["lat"]
        lon = conf["default_location"]["lon"]
        r = requests.get(
            f"https://weatherkit.apple.com/api/v1/availability/{lat}/{lon}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        report("WeatherKit", True, "", "", blocking=False)
    except Exception as e:
        report(
            "WeatherKit",
            False,
            "",
            f"{e}. The newsletter will skip the weather section until this recovers.",
            blocking=False,
        )
```

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add niederdaily.py
git commit -m "feat: add WeatherKit sentence call to orchestrator, update preflight"
```

---

## Task 7: Manual smoke test

- [ ] **Step 1: Add `weatherkit` block to your `~/.niederdaily/config.json`**

```json
"weatherkit": {
  "team_id": "YOUR_TEAM_ID",
  "service_id": "com.niederme.weatherkit",
  "key_id": "YOUR_KEY_ID",
  "key_file": "~/.credentials/AuthKey_YOURKEYID.p8"
}
```

- [ ] **Step 2: Run preflight**

```bash
python niederdaily.py --preflight
```

Expected: `✓ WeatherKit` appears. If `✗ WeatherKit`, check Team ID, Service ID, Key ID, and `.p8` file path.

- [ ] **Step 3: Send a test email**

```bash
python niederdaily.py
```

Verify in the received email:
- Weather section shows emoji icon + temperature
- Haiku-generated sentence appears below the temp
- If there are active alerts in your area: amber alert banner with link
- "Weather" attribution link at bottom of weather section

- [ ] **Step 4: Final commit** (no code changes — just confirm clean state)

```bash
git status
# Should be clean. If any tracked files are modified, stage and commit them:
# git add <specific files only — never add .p8 key files>
```
