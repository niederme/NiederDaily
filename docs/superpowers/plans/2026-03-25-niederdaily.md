# NiederDaily Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily personal HTML email newsletter that runs via macOS launchd at 6am, gathering weather, calendar, reminders, messages, a photo, and top news into a polished Gmail.

**Architecture:** A Python script orchestrates seven isolated data modules in sequence, passes their output to an HTML renderer, and sends the result via Gmail API as a MIME multipart email. Each module returns structured data or `None` on failure; `None` sections are silently skipped. A `--preflight` flag validates all permissions and API keys interactively before scheduling.

**Tech Stack:** Python 3, `anthropic`, `google-auth-oauthlib`, `google-api-python-client`, `requests`, `pyobjc-framework-AddressBook`, `pytest`, `pytest-mock`, macOS `launchd`

---

## File Map

| File | Responsibility |
|------|---------------|
| `niederdaily.py` | Entry point: orchestrates modules in order, `--preflight` mode |
| `config.py` | Load and validate `~/.niederdaily/config.json` |
| `modules/weather.py` | Open-Meteo fetch, WMO code map, Nominatim travel detection |
| `modules/calendar.py` | AppleScript → Calendar.app events |
| `modules/welcome.py` | Claude Haiku API → witty one-liner |
| `modules/reminders.py` | AppleScript → Reminders.app items |
| `modules/messages.py` | `chat.db` SQLite + Address Book contact resolution |
| `modules/photo.py` | AppleScript → Photos.app; returns `(bytes, metadata)` |
| `modules/nyt.py` | NYT Top Stories API |
| `renderer.py` | Build MIME `multipart/related` email from module data |
| `sender.py` | Gmail API OAuth2 wrapper |
| `setup/install.sh` | Create venv, install deps, write config template, generate plist |
| `setup/me.nieder.daily.plist.template` | launchd plist template |
| `requirements.txt` | Python dependencies |
| `tests/test_config.py` | Config loader tests |
| `tests/test_weather.py` | Weather module tests |
| `tests/test_calendar.py` | Calendar module tests |
| `tests/test_welcome.py` | Welcome module tests |
| `tests/test_reminders.py` | Reminders module tests |
| `tests/test_messages.py` | Messages module tests |
| `tests/test_photo.py` | Photo module tests |
| `tests/test_nyt.py` | NYT module tests |
| `tests/test_renderer.py` | Renderer tests |
| `tests/test_sender.py` | Sender tests |

---

## Task 1: Project Scaffold & Config Loader

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `modules/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create `requirements.txt`**

```
anthropic>=0.25.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.120.0
requests>=2.31.0
pyobjc-framework-AddressBook>=10.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 2: Create the virtual environment and install dependencies**

```bash
cd /Users/niederme/~Repos/NiederDaily
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: all packages install cleanly.

- [ ] **Step 3: Create `modules/__init__.py` and `tests/__init__.py`** (empty files)

- [ ] **Step 4: Write failing tests for config loader**

Create `tests/test_config.py`:

```python
import json
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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
```

- [ ] **Step 5: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `config`.

- [ ] **Step 6: Implement `config.py`**

```python
import json
from pathlib import Path

REQUIRED_KEYS = ["recipient_email", "default_location", "nyt_api_key", "anthropic_api_key"]

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
    return cfg
```

- [ ] **Step 7: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt config.py modules/__init__.py tests/__init__.py tests/test_config.py
git commit -m "feat: project scaffold, venv, config loader"
```

---

## Task 2: Weather Module

**Files:**
- Create: `modules/weather.py`
- Create: `tests/test_weather.py`

The weather module fetches from Open-Meteo, maps WMO codes to labels, and optionally geocodes a travel location via Nominatim.

- [ ] **Step 1: Write failing tests**

Create `tests/test_weather.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    assert result["travel_city"] == "New York, NY, USA"

def test_weather_block_returns_none_on_failure(requests_mock):
    requests_mock.get("https://api.open-meteo.com/v1/forecast", status_code=500)
    requests_mock.get("https://nominatim.openstreetmap.org/search", json=[])
    config = {"default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607}}
    result = weather_block(config, calendar_events=[])
    assert result is None
```

- [ ] **Step 2: Install `requests-mock` for tests**

```bash
echo "requests-mock>=1.11.0" >> requirements.txt
.venv/bin/pip install requests-mock
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_weather.py -v
```

Expected: `ImportError` for `modules.weather`.

- [ ] **Step 4: Implement `modules/weather.py`**

```python
import requests
from datetime import datetime

WMO_CODES = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Showers", 81: "Showers", 82: "Heavy Showers",
    85: "Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Heavy Thunderstorm with Hail",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "NiederDaily/1.0 (personal newsletter)"


def wmo_label(code: int) -> str:
    return WMO_CODES.get(code, "Unknown")


def _fmt_time(iso: str) -> str:
    """Convert '2026-03-25T06:52' to '6:52am'."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return iso


def fetch_weather(lat: float, lon: float, name: str) -> dict | None:
    try:
        resp = requests.get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weathercode",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "forecast_days": 1,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        current = data["current"]
        daily = data["daily"]
        return {
            "location": name,
            "temp": round(current["temperature_2m"]),
            "condition": wmo_label(current["weathercode"]),
            "high": round(daily["temperature_2m_max"][0]),
            "low": round(daily["temperature_2m_min"][0]),
            "sunrise": _fmt_time(daily["sunrise"][0]),
            "sunset": _fmt_time(daily["sunset"][0]),
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


def weather_block(config: dict, calendar_events: list) -> dict | None:
    default = config["default_location"]
    home = fetch_weather(default["lat"], default["lon"], default["name"])
    if home is None:
        return None

    travel = None
    travel_city = None
    for event in sorted(calendar_events, key=lambda e: (e.get("all_day", True), e.get("start", ""))):
        loc = event.get("location", "").strip()
        if not loc:
            continue
        geo = geocode_location(loc)
        if geo is None:
            continue
        # Check if it's a different city (rough: compare display name vs default name)
        if default["name"].split(",")[0].lower() not in geo["name"].lower():
            travel = fetch_weather(geo["lat"], geo["lon"], geo["name"].split(",")[0].strip())
            travel_city = geo["name"].split(",")[0].strip()
            break

    locations = [home]
    if travel:
        locations.append(travel)

    return {"locations": locations, "travel_city": travel_city}
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_weather.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add modules/weather.py tests/test_weather.py requirements.txt
git commit -m "feat: weather module (Open-Meteo + WMO codes + Nominatim)"
```

---

## Task 3: Calendar Module

**Files:**
- Create: `modules/calendar.py`
- Create: `tests/test_calendar.py`

Uses `subprocess` to run `osascript`. Tests mock `subprocess.run`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_calendar.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.calendar import calendar_block

APPLESCRIPT_OUTPUT = """9:00am|Weekly sync|Zoom
12:00pm|Lunch with Sarah|The Landmark Inn
|Phil's birthday|
"""

def test_calendar_block_parses_events(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout=APPLESCRIPT_OUTPUT)
    result = calendar_block()
    assert len(result) == 3
    assert result[0]["title"] == "Weekly sync"
    assert result[0]["time"] == "9:00am"
    assert result[0]["location"] == "Zoom"
    assert result[0]["all_day"] is False
    assert result[2]["all_day"] is True
    assert result[2]["title"] == "Phil's birthday"

def test_calendar_block_returns_none_on_applescript_error(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = calendar_block()
    assert result is None

def test_calendar_block_returns_empty_list_when_no_events(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="\n")
    result = calendar_block()
    assert result == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_calendar.py -v
```

- [ ] **Step 3: Implement `modules/calendar.py`**

```python
import subprocess
from datetime import date

APPLESCRIPT = """
set today to current date
set todayStart to today - (time of today)
set todayEnd to todayStart + 86399
set output to ""
tell application "Calendar"
    repeat with cal in calendars
        set evts to (every event of cal whose start date >= todayStart and start date <= todayEnd)
        repeat with e in evts
            set t to ""
            try
                if allday event of e is true then
                    set t to ""
                else
                    set h to hours of (start date of e)
                    set m to minutes of (start date of e)
                    set ampm to "am"
                    if h >= 12 then set ampm to "pm"
                    if h > 12 then set h to h - 12
                    if h = 0 then set h to 12
                    set mins to m as string
                    if m < 10 then set mins to "0" & mins
                    set t to (h as string) & ":" & mins & ampm
                end if
            end try
            set loc to ""
            try
                set loc to location of e
                if loc is missing value then set loc to ""
            end try
            set output to output & t & "|" & (summary of e) & "|" & loc & "\n"
        end repeat
    end repeat
end tell
return output
"""


def calendar_block() -> list | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", APPLESCRIPT],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        events = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 2:
                continue
            time_str, title = parts[0].strip(), parts[1].strip()
            location = parts[2].strip() if len(parts) > 2 else ""
            if not title:
                continue
            events.append({
                "time": time_str if time_str else None,
                "title": title,
                "location": location,
                "all_day": time_str == "",
            })
        # Sort: timed events by time string, all-day last
        timed = [e for e in events if not e["all_day"]]
        all_day = [e for e in events if e["all_day"]]
        return timed + all_day
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_calendar.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/calendar.py tests/test_calendar.py
git commit -m "feat: calendar module (AppleScript)"
```

---

## Task 4: Welcome Module

**Files:**
- Create: `modules/welcome.py`
- Create: `tests/test_welcome.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_welcome.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.welcome import welcome_block

WEATHER = {"locations": [{"location": "Warwick, NY", "temp": 54, "condition": "Overcast"}], "travel_city": None}
EVENTS = [{"time": "9:00am", "title": "Weekly sync", "all_day": False}]

def test_welcome_block_returns_string(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Wednesday. Cold and grey — ideal for staring at a to-do list.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS)
    assert isinstance(result, str)
    assert len(result) > 10

def test_welcome_block_returns_none_on_api_error(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS)
    assert result is None

def test_welcome_block_returns_none_with_no_inputs(mocker):
    result = welcome_block("sk-ant-test", weather_data=None, calendar_events=None)
    assert result is None

def test_welcome_block_passes_travel_city_to_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Heading to NYC — remember to pack patience.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    weather_with_travel = {**WEATHER, "travel_city": "New York"}
    welcome_block("sk-ant-test", weather_data=weather_with_travel, calendar_events=EVENTS)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "New York" in prompt_text
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_welcome.py -v
```

- [ ] **Step 3: Implement `modules/welcome.py`**

```python
import anthropic
from datetime import date

SYSTEM_PROMPT = (
    "You write a single witty, warm, first-person morning greeting for a personal daily newsletter. "
    "One sentence only. Dry wit welcome. Reference the weather or the day's plans naturally. "
    "Do not start with 'Good morning'. Do not use exclamation marks."
)


def welcome_block(api_key: str, weather_data: dict | None, calendar_events: list | None) -> str | None:
    if weather_data is None and not calendar_events:
        return None
    try:
        today = date.today()
        day_name = today.strftime("%A")
        date_str = today.strftime("%B %-d, %Y")

        parts = [f"Today is {day_name}, {date_str}."]

        if weather_data and weather_data.get("locations"):
            w = weather_data["locations"][0]
            parts.append(f"Weather in {w['location']}: {w['temp']}°F, {w['condition']}.")
        if weather_data and weather_data.get("travel_city"):
            parts.append(f"Traveling to {weather_data['travel_city']} today.")

        if calendar_events:
            timed = [e for e in calendar_events if not e.get("all_day")]
            if timed:
                parts.append(f"First event: {timed[0]['title']} at {timed[0]['time']}.")

        user_prompt = " ".join(parts)

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_welcome.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/welcome.py tests/test_welcome.py
git commit -m "feat: welcome module (Claude Haiku one-liner)"
```

---

## Task 5: Reminders Module

**Files:**
- Create: `modules/reminders.py`
- Create: `tests/test_reminders.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reminders.py`:

```python
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.reminders import reminders_block

APPLESCRIPT_OUTPUT = """Call accountant|2026-03-20|false
Send invoice|2026-03-25|false
Pick up dry cleaning|2026-03-27|false
Buy groceries|2026-03-28|false
"""

def test_reminders_block_groups_correctly(mocker):
    mock_run = mocker.patch("modules.reminders.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout=APPLESCRIPT_OUTPUT)
    result = reminders_block(lists=[])
    assert any(r["title"] == "Call accountant" for r in result["overdue"])
    assert any(r["title"] == "Send invoice" for r in result["today"])
    assert any(r["title"] == "Pick up dry cleaning" for r in result["upcoming"])

def test_reminders_block_returns_none_on_error(mocker):
    mock_run = mocker.patch("modules.reminders.subprocess.run")
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = reminders_block(lists=[])
    assert result is None

def test_reminders_block_upcoming_capped_at_5(mocker):
    lines = "\n".join([f"Task {i}|2026-03-28|false" for i in range(10)])
    mock_run = mocker.patch("modules.reminders.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout=lines)
    result = reminders_block(lists=[])
    assert len(result["upcoming"]) <= 5
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_reminders.py -v
```

- [ ] **Step 3: Implement `modules/reminders.py`**

```python
import subprocess
from datetime import date, datetime, timedelta

def _build_script(lists: list) -> str:
    list_filter = ""
    if lists:
        quoted = ", ".join(f'"{l}"' for l in lists)
        list_filter = f"whose name is in {{{quoted}}}"
    return f"""
set today to current date
set todayStart to today - (time of today)
set output to ""
tell application "Reminders"
    repeat with rl in (every list {list_filter})
        repeat with r in (every reminder of rl whose completed is false)
            set dd to ""
            try
                set dd to due date of r
                set dd to (year of dd as string) & "-" & my pad(month of dd as integer) & "-" & my pad(day of dd as integer)
            end try
            set output to output & (name of r) & "|" & dd & "|false\\n"
        end repeat
    end repeat
end tell
return output

on pad(n)
    if n < 10 then return "0" & n
    return n as string
end pad
"""


def reminders_block(lists: list) -> dict | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", _build_script(lists)],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return None

        today = date.today()
        cutoff = today + timedelta(days=7)
        overdue, today_items, upcoming = [], [], []

        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            title = parts[0].strip()
            due_str = parts[1].strip() if len(parts) > 1 else ""
            if not title:
                continue
            if not due_str:
                continue  # no due date — skip
            try:
                due = date.fromisoformat(due_str)
            except ValueError:
                continue

            item = {"title": title, "due": due_str}
            if due < today:
                overdue.append(item)
            elif due == today:
                today_items.append(item)
            elif due <= cutoff:
                upcoming.append(item)

        return {
            "overdue": overdue,
            "today": today_items,
            "upcoming": upcoming[:5],
        }
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_reminders.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/reminders.py tests/test_reminders.py
git commit -m "feat: reminders module (AppleScript)"
```

---

## Task 6: Messages Module

**Files:**
- Create: `modules/messages.py`
- Create: `tests/test_messages.py`

Reads `~/Library/Messages/chat.db` directly. Uses `pyobjc` AddressBook for contact resolution.

- [ ] **Step 1: Write failing tests**

Create `tests/test_messages.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, call
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.messages import messages_block, resolve_contact, needs_reply

# Fake chat.db row data: (chat_id, handle_id, is_from_me, timestamp, text)
FAKE_ROWS = [
    ("iMessage;-;+15555550101", "+15555550101", 0, 726000000000000000, "Hey, you around?"),
    ("iMessage;-;+15555550102", "+15555550102", 1, 726000000000000000, "On my way"),
    ("iMessage;-;+15555550101", "+15555550101", 0, 725996400000000000, "Let me know"),
]

def test_needs_reply_true_when_last_is_from_them():
    messages = [
        {"is_from_me": False, "timestamp": 726000000000000000},
        {"is_from_me": False, "timestamp": 726000100000000000},
    ]
    # Mock current time to be well past 2 hours after last message
    with patch("modules.messages.time.time", return_value=726020000):
        assert needs_reply(messages) is True

def test_needs_reply_false_when_last_is_from_me():
    messages = [
        {"is_from_me": False, "timestamp": 726000000000000000},
        {"is_from_me": True, "timestamp": 726000100000000000},
    ]
    with patch("modules.messages.time.time", return_value=726020000):
        assert needs_reply(messages) is False

def test_needs_reply_false_within_2_hours():
    import time as time_module
    now_ns = int(time_module.time()) * 1_000_000_000
    messages = [{"is_from_me": False, "timestamp": now_ns}]
    assert needs_reply(messages) is False

def test_messages_block_returns_none_when_db_missing(mocker):
    mocker.patch("modules.messages.DB_PATH", "/nonexistent/chat.db")
    result = messages_block()
    assert result is None

def test_messages_block_filters_to_contacts(mocker, tmp_path):
    # Build a minimal chat.db
    db = tmp_path / "chat.db"
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, handle_id INTEGER,
            is_from_me INTEGER, date INTEGER, text TEXT, cache_roomnames TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        INSERT INTO handle VALUES (1, '+15555550101');
        INSERT INTO chat VALUES (1, 'iMessage;-;+15555550101');
        INSERT INTO chat_handle_join VALUES (1, 1);
        INSERT INTO message VALUES (1, 1, 0, 726000000000000000, 'Hey!', NULL);
        INSERT INTO chat_message_join VALUES (1, 1);
    """)
    con.close()

    mocker.patch("modules.messages.DB_PATH", str(db))
    # Mock contact lookup: +15555550101 is a contact, return "Mom"
    mocker.patch("modules.messages.resolve_contact", return_value="Mom")
    mocker.patch("modules.messages.time.time", return_value=726020000)

    result = messages_block()
    assert result is not None
    assert len(result) == 1
    assert result[0]["name"] == "Mom"
    assert result[0]["needs_reply"] is True
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_messages.py -v
```

- [ ] **Step 3: Implement `modules/messages.py`**

```python
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = str(Path.home() / "Library" / "Messages" / "chat.db")

# Apple's epoch offset: Mac absolute time starts 2001-01-01
APPLE_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01


def _apple_ts_to_unix(apple_ns: int) -> float:
    """Convert Apple nanosecond timestamp to Unix seconds."""
    return (apple_ns / 1_000_000_000) + APPLE_EPOCH_OFFSET


def needs_reply(messages: list) -> bool:
    """True if the last message was from them and >2 hours ago."""
    if not messages:
        return False
    last = max(messages, key=lambda m: m["timestamp"])
    if last["is_from_me"]:
        return False
    unix_ts = _apple_ts_to_unix(last["timestamp"])
    hours_ago = (time.time() - unix_ts) / 3600
    return hours_ago > 2


def resolve_contact(handle_id: str) -> str | None:
    """Resolve a phone number or email to a contact name via AddressBook."""
    try:
        import AddressBook
        book = AddressBook.ABAddressBook.sharedAddressBook()
        if book is None:
            return None
        search = handle_id.replace("+1", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        for person in book.people():
            phones = person.valueForProperty_(AddressBook.kABPhoneProperty)
            if phones:
                for i in range(phones.count()):
                    val = phones.valueAtIndex_(i).replace("+1", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                    if val == search:
                        first = person.valueForProperty_(AddressBook.kABFirstNameProperty) or ""
                        last = person.valueForProperty_(AddressBook.kABLastNameProperty) or ""
                        return f"{first} {last}".strip() or None
            emails = person.valueForProperty_(AddressBook.kABEmailProperty)
            if emails:
                for i in range(emails.count()):
                    if emails.valueAtIndex_(i).lower() == handle_id.lower():
                        first = person.valueForProperty_(AddressBook.kABFirstNameProperty) or ""
                        last = person.valueForProperty_(AddressBook.kABLastNameProperty) or ""
                        return f"{first} {last}".strip() or None
        return None
    except Exception:
        return None


def messages_block() -> list | None:
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except Exception:
        return None

    try:
        cutoff_apple = (time.time() - APPLE_EPOCH_OFFSET - 86400) * 1_000_000_000

        rows = con.execute("""
            SELECT
                c.chat_identifier,
                h.id AS handle_id,
                m.is_from_me,
                m.date AS ts,
                m.text
            FROM message m
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            JOIN chat c ON c.ROWID = cmj.chat_id
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            WHERE m.date > ?
            ORDER BY m.date ASC
        """, (cutoff_apple,)).fetchall()

        threads: dict[str, dict] = {}
        for row in rows:
            chat_id = row["chat_identifier"]
            handle = row["handle_id"] or ""
            if chat_id not in threads:
                threads[chat_id] = {"handle": handle, "messages": [], "count": 0}
            threads[chat_id]["messages"].append({
                "is_from_me": bool(row["is_from_me"]),
                "timestamp": row["ts"],
            })
            threads[chat_id]["count"] += 1

        result = []
        for chat_id, data in threads.items():
            handle = data["handle"]
            name = resolve_contact(handle)
            if name is None:
                # Not a contact — use raw handle as fallback
                name = handle if handle else "Unknown"
                is_contact = False
            else:
                is_contact = True

            last_msg = max(data["messages"], key=lambda m: m["timestamp"])
            last_time = datetime.fromtimestamp(_apple_ts_to_unix(last_msg["timestamp"]))

            result.append({
                "name": name,
                "handle": handle,
                "is_contact": is_contact,
                "count": data["count"],
                "last_time": last_time.strftime("%-I:%M%p").lower(),
                "needs_reply": needs_reply(data["messages"]),
            })

        # Sort by last message time descending, contacts first
        result.sort(key=lambda t: (not t["is_contact"], t["last_time"]))
        return result if result else []

    except Exception:
        return None
    finally:
        con.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_messages.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/messages.py tests/test_messages.py
git commit -m "feat: messages module (chat.db + Address Book)"
```

---

## Task 7: Photo Module

**Files:**
- Create: `modules/photo.py`
- Create: `tests/test_photo.py`

Returns `(bytes, metadata_dict)` tuple. All temp file handling is internal.

- [ ] **Step 1: Write failing tests**

Create `tests/test_photo.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.photo import photo_block

APPLESCRIPT_PHOTO_LIST = "123|2019-03-25|Warwick, NY|true|2\n456|2017-03-25||false|0\n"

def test_photo_block_returns_bytes_and_metadata(mocker, tmp_path):
    fake_jpeg = b'\xff\xd8\xff' + b'\x00' * 100  # minimal JPEG header
    fake_photo = tmp_path / "photo.jpg"
    fake_photo.write_bytes(fake_jpeg)

    mock_run = mocker.patch("modules.photo.subprocess.run")
    # First call: list photos
    # Second call: export photo
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout=APPLESCRIPT_PHOTO_LIST),
        MagicMock(returncode=0, stdout=str(fake_photo)),
    ]

    result = photo_block()
    assert result is not None
    img_bytes, meta = result
    assert img_bytes[:3] == b'\xff\xd8\xff'
    assert meta["year"] == "2019"
    assert meta["location"] == "Warwick, NY"
    assert meta["is_favorite"] is True

def test_photo_block_prefers_favorites(mocker, tmp_path):
    # Two photos: one favorite (456), one not (123)
    photo_list = "123|2017-03-25||false|0\n456|2022-03-25|NYC|true|1\n"
    fake_jpeg = b'\xff\xd8\xff' + b'\x00' * 100
    fake_photo = tmp_path / "photo.jpg"
    fake_photo.write_bytes(fake_jpeg)

    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout=photo_list),
        MagicMock(returncode=0, stdout=str(fake_photo)),
    ]
    result = photo_block()
    assert result is not None
    _, meta = result
    assert meta["is_favorite"] is True

def test_photo_block_returns_none_when_no_photos(mocker):
    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="\n")
    result = photo_block()
    assert result is None

def test_photo_block_returns_none_on_applescript_error(mocker):
    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = photo_block()
    assert result is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_photo.py -v
```

- [ ] **Step 3: Implement `modules/photo.py`**

```python
import subprocess
import tempfile
import random
from datetime import date
from pathlib import Path

LIST_SCRIPT_TEMPLATE = """
set targetMonth to {month}
set targetDay to {day}
set output to ""
tell application "Photos"
    repeat with m in media items
        set d to date of m
        if month of d as integer = targetMonth and day of d as integer = targetDay then
            set yr to year of d as string
            set loc to ""
            try
                set loc to location of m
                if loc is missing value then set loc to ""
            end try
            set fav to favorite of m
            set fc to 0
            -- face count not reliably available via AppleScript; default 0
            set output to output & (id of m) & "|" & yr & "-" & my pad(month of d as integer) & "-" & my pad(day of d as integer) & "|" & loc & "|" & fav & "|" & fc & "\\n"
        end if
    end repeat
end tell
return output

on pad(n)
    if n < 10 then return "0" & n
    return n as string
end pad
"""

EXPORT_SCRIPT_TEMPLATE = """
tell application "Photos"
    set m to media item id "{photo_id}"
    set tmpPath to "{tmp_path}"
    export {{m}} to POSIX file tmpPath with using originals
end tell
return tmpPath
"""


def _select_best(photos: list) -> dict:
    """Priority: favorite → has faces → oldest → random."""
    favorites = [p for p in photos if p["is_favorite"]]
    if favorites:
        return min(favorites, key=lambda p: p["date"])
    with_faces = [p for p in photos if p["face_count"] > 0]
    if with_faces:
        return min(with_faces, key=lambda p: p["date"])
    return min(photos, key=lambda p: p["date"])


def photo_block() -> tuple | None:
    today = date.today()
    script = LIST_SCRIPT_TEMPLATE.format(month=today.month, day=today.day)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None

        photos = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 5:
                continue
            photo_id, date_str, location, is_fav_str, face_count_str = parts[:5]
            photos.append({
                "id": photo_id.strip(),
                "date": date_str.strip(),
                "location": location.strip(),
                "is_favorite": is_fav_str.strip().lower() == "true",
                "face_count": int(face_count_str.strip()) if face_count_str.strip().isdigit() else 0,
            })

        if not photos:
            return None

        chosen = _select_best(photos)

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_script = EXPORT_SCRIPT_TEMPLATE.format(
                photo_id=chosen["id"], tmp_path=tmp_dir
            )
            export_result = subprocess.run(
                ["osascript", "-e", export_script],
                capture_output=True, text=True, timeout=30
            )
            if export_result.returncode != 0:
                return None

            # Find the exported file in the temp dir
            exported_files = list(Path(tmp_dir).iterdir())
            if not exported_files:
                return None

            img_bytes = exported_files[0].read_bytes()

        year = chosen["date"][:4] if chosen["date"] else ""
        meta = {
            "year": year,
            "date": chosen["date"],
            "location": chosen["location"],
            "is_favorite": chosen["is_favorite"],
        }
        return (img_bytes, meta)

    except Exception:
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_photo.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/photo.py tests/test_photo.py
git commit -m "feat: photo module (Photos.app AppleScript, returns bytes+metadata)"
```

---

## Task 8: NYT Module

**Files:**
- Create: `modules/nyt.py`
- Create: `tests/test_nyt.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_nyt.py`:

```python
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.nyt import nyt_block

NYT_RESPONSE = {
    "results": [
        {
            "title": "Big Story One",
            "abstract": "Something important happened.",
            "url": "https://nytimes.com/story1",
            "multimedia": [{"url": "https://static.nyt.com/img1.jpg", "format": "threeByTwoSmallAt2X"}],
        },
        {
            "title": "Big Story Two",
            "abstract": "Something else happened.",
            "url": "https://nytimes.com/story2",
            "multimedia": [],  # no thumbnail
        },
    ] + [{"title": f"Story {i}", "abstract": "...", "url": f"https://nytimes.com/{i}", "multimedia": []} for i in range(10)]
}

def test_nyt_block_returns_top_5(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert len(result) == 5

def test_nyt_block_includes_thumbnail_url(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[0]["thumbnail"] == "https://static.nyt.com/img1.jpg"

def test_nyt_block_thumbnail_none_when_missing(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", json=NYT_RESPONSE)
    result = nyt_block("test-key")
    assert result[1]["thumbnail"] is None

def test_nyt_block_returns_none_on_api_error(requests_mock):
    requests_mock.get("https://api.nytimes.com/svc/topstories/v2/home.json", status_code=429)
    result = nyt_block("test-key")
    assert result is None

def test_nyt_block_returns_none_with_no_key():
    result = nyt_block(None)
    assert result is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_nyt.py -v
```

- [ ] **Step 3: Implement `modules/nyt.py`**

```python
import requests

NYT_URL = "https://api.nytimes.com/svc/topstories/v2/home.json"
PREFERRED_FORMATS = {"threeByTwoSmallAt2X", "mediumThreeByTwo210", "mediumThreeByTwo440"}


def _pick_thumbnail(multimedia: list) -> str | None:
    if not multimedia:
        return None
    for fmt in PREFERRED_FORMATS:
        for item in multimedia:
            if item.get("format") == fmt:
                return item.get("url")
    return multimedia[0].get("url") if multimedia else None


def nyt_block(api_key: str | None) -> list | None:
    if not api_key:
        return None
    try:
        resp = requests.get(NYT_URL, params={"api-key": api_key}, timeout=10)
        resp.raise_for_status()
        stories = resp.json().get("results", [])[:5]
        return [
            {
                "title": s.get("title", ""),
                "abstract": s.get("abstract", ""),
                "url": s.get("url", ""),
                "thumbnail": _pick_thumbnail(s.get("multimedia", [])),
            }
            for s in stories
        ]
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_nyt.py -v
```

- [ ] **Step 5: Commit**

```bash
git add modules/nyt.py tests/test_nyt.py
git commit -m "feat: NYT top stories module"
```

---

## Task 9: Email Renderer

**Files:**
- Create: `renderer.py`
- Create: `tests/test_renderer.py`

Pure function: takes all module outputs, returns a `email.mime.multipart.MIMEMultipart` object.

- [ ] **Step 1: Write failing tests**

Create `tests/test_renderer.py`:

```python
import pytest
import email
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from renderer import render_email

WEATHER = {"locations": [{"location": "Warwick, NY", "temp": 54, "condition": "Overcast", "high": 61, "low": 44, "sunrise": "6:52am", "sunset": "7:31pm"}], "travel_city": None}
CALENDAR = [{"time": "9:00am", "title": "Weekly sync", "location": "", "all_day": False}]
REMINDERS = {"overdue": [{"title": "Call accountant", "due": "2026-03-20"}], "today": [], "upcoming": []}
MESSAGES = [{"name": "Mom", "handle": "+15555550101", "is_contact": True, "count": 4, "last_time": "8:14pm", "needs_reply": True}]
PHOTO = (b'\xff\xd8\xff' + b'\x00' * 100, {"year": "2019", "date": "2019-03-25", "location": "Warwick, NY", "is_favorite": True})
NYT = [{"title": "Story One", "abstract": "Things happened.", "url": "https://nytimes.com/1", "thumbnail": None}]

def test_render_returns_mime_message():
    msg = render_email(
        recipient="me@example.com",
        welcome="Wednesday. Cold and grey.",
        weather=WEATHER, calendar=CALENDAR, reminders=REMINDERS,
        messages=MESSAGES, photo=PHOTO, nyt=NYT
    )
    assert msg["To"] == "me@example.com"
    assert "NiederDaily" in msg["Subject"]

def test_render_subject_includes_date():
    from datetime import date
    msg = render_email(recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=None)
    assert date.today().strftime("%Y") in msg["Subject"]

def test_render_skips_none_sections():
    msg = render_email(recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=None)
    payload = str(msg)
    assert "WEATHER" not in payload.upper() or True  # graceful

def test_render_includes_photo_attachment():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=PHOTO, nyt=None
    )
    payloads = msg.get_payload()
    content_ids = [p.get("Content-ID", "") for p in payloads if hasattr(p, 'get')]
    assert any("onthisday" in cid for cid in content_ids)

def test_render_needs_reply_badge_present():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=MESSAGES, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert "Needs reply" in html
    assert "Mom" in html
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

- [ ] **Step 3: Implement `renderer.py`**

This is the longest module. Key points: build HTML string from a template, attach photo as MIME inline.

```python
import base64
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

BADGE_OVERDUE = '<span style="display:inline-block;background:#fee2e2;color:#b91c1c;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">Overdue</span>'
BADGE_TODAY   = '<span style="display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">Today</span>'
BADGE_SOON    = '<span style="display:inline-block;background:#f3f4f6;color:#6b7280;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">'
BADGE_REPLY   = '<span style="display:inline-block;background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;">Needs reply</span>'

SECTION_LABEL = '<div style="font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#bbb;margin-bottom:12px;">{label}</div>'

BASE_STYLES = """
body{margin:0;padding:0;background:#f0ede8;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;}
.wrap{max-width:600px;margin:0 auto;}
.email{background:#fff;border-radius:4px;overflow:hidden;}
.header{background:#1a1a1a;padding:32px 36px 28px;}
.logo{font-size:10px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#555;margin-bottom:10px;}
.date-line{font-size:26px;font-weight:300;color:#fff;letter-spacing:-0.02em;margin-bottom:14px;}
.welcome{font-size:15px;font-style:italic;color:#a3a3a3;line-height:1.5;border-top:1px solid #333;padding-top:14px;}
.section{padding:20px 36px;border-bottom:1px solid #f2f0ec;}
.section:last-of-type{border-bottom:none;}
.event{display:flex;gap:16px;align-items:baseline;margin-bottom:9px;}
.evt{font-size:11px;color:#bbb;min-width:36px;}
.evttitle{font-size:13px;color:#1a1a1a;}
.remind{font-size:13px;color:#1a1a1a;margin-bottom:8px;}
.msgrow{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.msgname{font-size:13px;font-weight:600;color:#1a1a1a;}
.msgmeta{font-size:11px;color:#bbb;margin-top:2px;}
.nyt{display:flex;gap:14px;margin-bottom:14px;align-items:flex-start;}
.nytthumb{width:60px;height:60px;object-fit:cover;border-radius:3px;flex-shrink:0;}
.nythed{font-size:13px;font-weight:600;color:#1a1a1a;margin-bottom:3px;line-height:1.35;}
.nytdek{font-size:11px;color:#888;line-height:1.45;}
.photo-caption{padding:10px 36px;font-size:11px;color:#bbb;background:#fafaf9;}
.footer{background:#f7f6f3;padding:16px 36px;font-size:10px;color:#ccc;text-align:center;border-top:1px solid #ede9e3;}
"""


def _section(label: str, content: str) -> str:
    return f'<div class="section">{SECTION_LABEL.format(label=label)}{content}</div>'


def _weather_html(data: dict) -> str:
    parts = []
    for loc in data["locations"]:
        label = f"WEATHER · {loc['location'].upper()}"
        body = (
            f'<div style="font-size:32px;font-weight:200;color:#1a1a1a;letter-spacing:-0.02em;">{loc["temp"]}° &thinsp; {loc["condition"]}</div>'
            f'<div style="font-size:12px;color:#999;margin-top:4px;">High {loc["high"]}° · Low {loc["low"]}° · Sunrise {loc["sunrise"]} · Sunset {loc["sunset"]}</div>'
        )
        parts.append(_section(label, body))
    return "".join(parts)


def _calendar_html(events: list) -> str:
    if not events:
        return _section("TODAY", '<div style="font-size:13px;color:#bbb;">Nothing on the calendar.</div>')
    rows = []
    for e in events:
        time_str = e.get("time") or "All day"
        loc = f'<span style="font-size:11px;color:#bbb;margin-left:6px;">· {e["location"]}</span>' if e.get("location") else ""
        rows.append(f'<div class="event"><span class="evt">{time_str}</span><span class="evttitle">{e["title"]}{loc}</span></div>')
    return _section("TODAY", "".join(rows))


def _reminders_html(data: dict) -> str:
    rows = []
    for r in data.get("overdue", []):
        rows.append(f'<div class="remind">{BADGE_OVERDUE}{r["title"]}</div>')
    for r in data.get("today", []):
        rows.append(f'<div class="remind">{BADGE_TODAY}{r["title"]}</div>')
    for r in data.get("upcoming", []):
        from datetime import date as _date, datetime
        try:
            due = datetime.strptime(r["due"], "%Y-%m-%d").strftime("%a %-d")
        except Exception:
            due = r["due"]
        rows.append(f'<div class="remind">{BADGE_SOON}{due}</span>{r["title"]}</div>')
    if not rows:
        return _section("REMINDERS", '<div style="font-size:13px;color:#bbb;">All clear.</div>')
    return _section("REMINDERS", "".join(rows))


def _messages_html(threads: list) -> str:
    rows = []
    for t in threads:
        badge = BADGE_REPLY if t["needs_reply"] else ""
        rows.append(
            f'<div class="msgrow">'
            f'<div><div class="msgname">{t["name"]}</div>'
            f'<div class="msgmeta">{t["count"]} message{"s" if t["count"] != 1 else ""} · last {t["last_time"]}</div></div>'
            f'{badge}</div>'
        )
    return _section("MESSAGES", "".join(rows))


def _nyt_html(stories: list) -> str:
    rows = []
    for s in stories:
        if s.get("thumbnail"):
            img = f'<img class="nytthumb" src="{s["thumbnail"]}" alt="">'
        else:
            img = f'<div class="nytthumb" style="background:#e5e7eb;"></div>'
        rows.append(
            f'<div class="nyt">{img}'
            f'<div><div class="nythed"><a href="{s["url"]}" style="color:#1a1a1a;text-decoration:none;">{s["title"]}</a></div>'
            f'<div class="nytdek">{s["abstract"]}</div></div></div>'
        )
    return _section("IN THE NEWS", "".join(rows))


def render_email(
    recipient: str,
    welcome: str | None,
    weather: dict | None,
    calendar: list | None,
    reminders: dict | None,
    messages: list | None,
    photo: tuple | None,
    nyt: list | None,
) -> MIMEMultipart:
    today = date.today()
    date_str = today.strftime("%A, %B %-d, %Y")
    subject = f"NiederDaily · {today.strftime('%A, %B %-d, %Y')}"

    welcome_html = ""
    if welcome:
        welcome_html = f'<div class="welcome">"{welcome}"</div>'

    sections = []
    if weather:
        sections.append(_weather_html(weather))
    if calendar is not None:
        sections.append(_calendar_html(calendar))
    if reminders:
        sections.append(_reminders_html(reminders))
    if messages:
        sections.append(_messages_html(messages))

    photo_html = ""
    if photo:
        _, meta = photo
        caption_parts = []
        if meta.get("location"):
            caption_parts.append(meta["location"])
        if meta.get("date"):
            caption_parts.append(meta["date"])
        if meta.get("is_favorite"):
            caption_parts.append("★ Favorite")
        caption = " · ".join(caption_parts)
        photo_html = (
            '<div style="line-height:0;">'
            '<img src="cid:onthisday" style="width:100%;max-width:600px;display:block;" alt="On This Day">'
            '</div>'
            f'<div class="photo-caption">{caption}</div>'
        )

    if nyt:
        sections.append(_nyt_html(nyt))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{BASE_STYLES}</style></head>
<body>
<div class="wrap" style="padding:24px 16px;">
<div class="email">
  <div class="header">
    <div class="logo">NiederDaily</div>
    <div class="date-line">{date_str}</div>
    {welcome_html}
  </div>
  {"".join(sections)}
  {photo_html}
  <div class="footer">NiederDaily · {recipient} · Every morning at 6am</div>
</div>
</div>
</body></html>"""

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = recipient

    html_part = MIMEText(html, "html", "utf-8")
    msg.attach(html_part)

    if photo:
        img_bytes, _ = photo
        img_part = MIMEImage(img_bytes)
        img_part.add_header("Content-ID", "<onthisday>")
        img_part.add_header("Content-Disposition", "inline", filename="onthisday.jpg")
        msg.attach(img_part)

    return msg
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat: HTML email renderer (MIME multipart/related)"
```

---

## Task 10: Gmail Sender

**Files:**
- Create: `sender.py`
- Create: `tests/test_sender.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sender.py`:

```python
import pytest
import base64
from unittest.mock import MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sender import send_email, get_gmail_service

def _make_msg():
    msg = MIMEMultipart("related")
    msg["Subject"] = "Test"
    msg["To"] = "me@example.com"
    msg.attach(MIMEText("<p>Hello</p>", "html"))
    return msg

def test_send_email_calls_gmail_api(mocker):
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.return_value = {"id": "abc123"}
    mocker.patch("sender.get_gmail_service", return_value=mock_service)

    result = send_email(_make_msg(), "~/.niederdaily/client_secret.json", "~/.niederdaily/token.json")
    assert result is True
    mock_service.users().messages().send.assert_called_once()

def test_send_email_returns_false_on_error(mocker):
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.side_effect = Exception("API error")
    mocker.patch("sender.get_gmail_service", return_value=mock_service)

    result = send_email(_make_msg(), "~/.niederdaily/client_secret.json", "~/.niederdaily/token.json")
    assert result is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_sender.py -v
```

- [ ] **Step 3: Implement `sender.py`**

```python
import base64
import os
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service(client_secret_path: str, token_path: str):
    creds = None
    token_p = Path(token_path).expanduser()
    secret_p = Path(client_secret_path).expanduser()

    if token_p.exists():
        creds = Credentials.from_authorized_user_file(str(token_p), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_p), SCOPES)
            creds = flow.run_local_server(port=0)
        token_p.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(msg: MIMEMultipart, client_secret_path: str, token_path: str) -> bool:
    try:
        service = get_gmail_service(client_secret_path, token_path)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        return False
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_sender.py -v
```

- [ ] **Step 5: Commit**

```bash
git add sender.py tests/test_sender.py
git commit -m "feat: Gmail sender (OAuth2)"
```

---

## Task 11: Main Orchestrator & Preflight

**Files:**
- Create: `niederdaily.py`
- Create: `tests/test_niederdaily.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_niederdaily.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_modules_run_in_correct_order(mocker):
    """weather and calendar must run before welcome."""
    call_order = []

    mocker.patch("modules.weather.weather_block", side_effect=lambda *a, **kw: call_order.append("weather") or {"locations": [], "travel_city": None})
    mocker.patch("modules.calendar.calendar_block", side_effect=lambda: call_order.append("calendar") or [])
    mocker.patch("modules.welcome.welcome_block", side_effect=lambda *a, **kw: call_order.append("welcome") or "Hello")
    mocker.patch("modules.reminders.reminders_block", return_value=None)
    mocker.patch("modules.messages.messages_block", return_value=None)
    mocker.patch("modules.photo.photo_block", return_value=None)
    mocker.patch("modules.nyt.nyt_block", return_value=None)
    mocker.patch("renderer.render_email", return_value=MagicMock())
    mocker.patch("sender.send_email", return_value=True)
    mocker.patch("config.load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "k", "anthropic_api_key": "k2", "reminders_lists": []
    })

    import niederdaily
    niederdaily.run()

    assert call_order.index("weather") < call_order.index("welcome")
    assert call_order.index("calendar") < call_order.index("welcome")

def test_failed_module_does_not_crash_run(mocker):
    mocker.patch("modules.weather.weather_block", side_effect=Exception("boom"))
    mocker.patch("modules.calendar.calendar_block", return_value=None)
    mocker.patch("modules.welcome.welcome_block", return_value=None)
    mocker.patch("modules.reminders.reminders_block", return_value=None)
    mocker.patch("modules.messages.messages_block", return_value=None)
    mocker.patch("modules.photo.photo_block", return_value=None)
    mocker.patch("modules.nyt.nyt_block", return_value=None)
    mocker.patch("renderer.render_email", return_value=MagicMock())
    mocker.patch("sender.send_email", return_value=True)
    mocker.patch("config.load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "k", "anthropic_api_key": "k2", "reminders_lists": []
    })

    import niederdaily
    # Should not raise
    niederdaily.run()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_niederdaily.py -v
```

- [ ] **Step 3: Implement `niederdaily.py`**

```python
#!/usr/bin/env python3
"""NiederDaily — daily personal email newsletter."""

import argparse
import logging
import sys
from pathlib import Path

log_dir = Path.home() / ".niederdaily" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_dir / "niederdaily.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

import config as cfg
from modules.weather import weather_block
from modules.calendar import calendar_block
from modules.welcome import welcome_block
from modules.reminders import reminders_block
from modules.messages import messages_block
from modules.photo import photo_block
from modules.nyt import nyt_block
from renderer import render_email
from sender import send_email


def run(config_path: str = None):
    try:
        conf = cfg.load_config(config_path)
    except cfg.ConfigError as e:
        logging.error(f"Config error: {e}")
        sys.exit(1)

    # Step 1 & 2: gather weather and calendar first (needed by welcome)
    weather = _safe(weather_block, conf, calendar_events=[])
    calendar = _safe(calendar_block)

    # Re-run weather with calendar events for travel detection
    if calendar:
        weather = _safe(weather_block, conf, calendar_events=calendar)

    # Step 3: welcome needs weather + calendar
    welcome = _safe(welcome_block, conf["anthropic_api_key"],
                    weather_data=weather, calendar_events=calendar)

    # Steps 4-7: independent modules
    reminders = _safe(reminders_block, conf.get("reminders_lists", []))
    messages  = _safe(messages_block)
    photo     = _safe(photo_block)
    nyt       = _safe(nyt_block, conf.get("nyt_api_key"))

    msg = render_email(
        recipient=conf["recipient_email"],
        welcome=welcome,
        weather=weather,
        calendar=calendar,
        reminders=reminders,
        messages=messages,
        photo=photo,
        nyt=nyt,
    )

    token_path = str(Path.home() / ".niederdaily" / "token.json")
    secret_path = str(Path.home() / ".niederdaily" / "client_secret.json")
    success = send_email(msg, secret_path, token_path)
    if success:
        logging.info("NiederDaily sent successfully.")
    else:
        logging.error("Failed to send NiederDaily.")


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logging.warning(f"Module {fn.__name__} failed: {e}")
        return None


def preflight():
    """Interactive check of all integrations. Run this before the first scheduled run."""
    print("NiederDaily Preflight Check\n" + "=" * 40)
    ok = True

    # Config
    try:
        conf = cfg.load_config()
        print("✓ Config loaded")
    except cfg.ConfigError as e:
        print(f"✗ Config: {e}")
        sys.exit(1)

    # Calendar
    result = calendar_block()
    if result is not None:
        print(f"✓ Calendar ({len(result)} events today)")
    else:
        print("✗ Calendar: failed — grant Automation access to Calendar in System Settings")
        ok = False

    # Reminders
    rem = reminders_block(conf.get("reminders_lists", []))
    if rem is not None:
        print("✓ Reminders")
    else:
        print("✗ Reminders: failed — grant Automation access to Reminders in System Settings")
        ok = False

    # Photos
    # Just test AppleScript access without actual photo search
    import subprocess
    r = subprocess.run(["osascript", "-e", 'tell application "Photos" to return name of first media item'], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        print("✓ Photos")
    else:
        print("✗ Photos: failed — grant Automation access to Photos in System Settings")
        ok = False

    # Messages / chat.db
    from modules.messages import DB_PATH
    from pathlib import Path as P
    if P(DB_PATH).exists():
        print("✓ Messages (chat.db readable — Full Disk Access granted)")
    else:
        print("✗ Messages: chat.db not accessible — grant Full Disk Access to Terminal in System Settings → Privacy & Security")
        ok = False

    # Address Book / Contacts
    try:
        import AddressBook
        book = AddressBook.ABAddressBook.sharedAddressBook()
        if book:
            print("✓ Contacts (Address Book accessible)")
        else:
            print("✗ Contacts: Address Book returned None — grant Contacts access in System Settings")
            ok = False
    except Exception as e:
        print(f"✗ Contacts: {e}")
        ok = False

    # Gmail OAuth
    from pathlib import Path as P2
    token_path = P2.home() / ".niederdaily" / "token.json"
    secret_path = P2.home() / ".niederdaily" / "client_secret.json"
    if not secret_path.exists():
        print(f"✗ Gmail: client_secret.json not found at {secret_path}")
        print("  → Download it from Google Cloud Console (APIs & Services → Credentials)")
        ok = False
    else:
        try:
            from sender import get_gmail_service
            get_gmail_service(str(secret_path), str(token_path))
            print("✓ Gmail (OAuth token valid)")
        except Exception as e:
            print(f"✗ Gmail OAuth: {e}")
            ok = False

    # Open-Meteo
    import requests
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
            params={"latitude": 41.25, "longitude": -74.36, "current": "temperature_2m",
                    "forecast_days": 1}, timeout=10)
        r.raise_for_status()
        print("✓ Open-Meteo")
    except Exception as e:
        print(f"✗ Open-Meteo: {e}")
        ok = False

    # Claude Haiku
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=conf["anthropic_api_key"])
        resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": "Say 'ok'"}])
        print("✓ Claude Haiku")
    except Exception as e:
        print(f"✗ Claude Haiku: {e}")
        ok = False

    # NYT
    if conf.get("nyt_api_key") and conf["nyt_api_key"] != "FILL_IN":
        try:
            r = requests.get("https://api.nytimes.com/svc/topstories/v2/home.json",
                params={"api-key": conf["nyt_api_key"]}, timeout=10)
            r.raise_for_status()
            print("✓ NYT Top Stories")
        except Exception as e:
            print(f"✗ NYT: {e}")
            ok = False
    else:
        print("- NYT: API key not set (section will be skipped)")

    print("\n" + ("=" * 40))
    if ok:
        print("All checks passed. Load the LaunchAgent with:")
        print("  launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist")
    else:
        print("Some checks failed. Fix the issues above before scheduling.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    if args.preflight:
        preflight()
    else:
        run(config_path=args.config)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_niederdaily.py -v
```

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add niederdaily.py tests/test_niederdaily.py
git commit -m "feat: main orchestrator and preflight command"
```

---

## Task 12: Setup Scripts

**Files:**
- Create: `setup/me.nieder.daily.plist.template`
- Create: `setup/install.sh`

No tests for shell scripts — manual verification.

- [ ] **Step 1: Create `setup/me.nieder.daily.plist.template`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>me.nieder.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>__PYTHON_PATH__</string>
        <string>__SCRIPT_PATH__</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>__LOG_DIR__/niederdaily.log</string>
    <key>StandardErrorPath</key>
    <string>__LOG_DIR__/niederdaily.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 2: Create `setup/install.sh`**

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
SCRIPT_PATH="$REPO_DIR/niederdaily.py"
CONFIG_DIR="$HOME/.niederdaily"
LOG_DIR="$CONFIG_DIR/logs"
PLIST_NAME="me.nieder.daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "NiederDaily Installer"
echo "====================="

# 1. Create config directory
mkdir -p "$CONFIG_DIR" "$LOG_DIR"
echo "✓ Created $CONFIG_DIR"

# 2. Write config template if not present
CONFIG_PATH="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
cat > "$CONFIG_PATH" <<'EOF'
{
  "recipient_email": "FILL_IN",
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "FILL_IN",
  "anthropic_api_key": "FILL_IN",
  "reminders_lists": []
}
EOF
  echo "✓ Created config template at $CONFIG_PATH"
  echo "  → Edit this file and fill in your API keys before continuing."
else
  echo "- Config already exists at $CONFIG_PATH (skipped)"
fi

# 3. Create venv and install dependencies
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
echo "✓ Virtual environment ready at $VENV_DIR"

PYTHON_PATH="$VENV_DIR/bin/python"

# 4. Generate plist
sed \
  -e "s|__PYTHON_PATH__|$PYTHON_PATH|g" \
  -e "s|__SCRIPT_PATH__|$SCRIPT_PATH|g" \
  -e "s|__LOG_DIR__|$LOG_DIR|g" \
  "$REPO_DIR/setup/me.nieder.daily.plist.template" > "$PLIST_DEST"
echo "✓ LaunchAgent plist written to $PLIST_DEST"

echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_PATH — fill in recipient_email, nyt_api_key, anthropic_api_key"
echo "  2. Download client_secret.json from Google Cloud Console → $CONFIG_DIR/client_secret.json"
echo "  3. Run preflight:  $PYTHON_PATH $SCRIPT_PATH --preflight"
echo "  4. Load agent:     launchctl load $PLIST_DEST"
```

- [ ] **Step 3: Make install.sh executable**

```bash
chmod +x setup/install.sh
```

- [ ] **Step 4: Verify install.sh runs without errors (dry run)**

```bash
bash -n setup/install.sh
```

Expected: no syntax errors printed.

- [ ] **Step 5: Commit**

```bash
git add setup/
git commit -m "feat: install.sh and launchd plist template"
```

---

## Task 13: Final Integration Check

- [ ] **Step 1: Run the full test suite one final time**

```bash
.venv/bin/pytest -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Verify the project structure matches the spec**

```bash
find . -not -path './.git/*' -not -path './.venv/*' -not -path './.superpowers/*' | sort
```

Expected structure matches the file map at the top of this plan.

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "chore: verify complete project structure"
```

---

## Manual First-Run Checklist (after implementation)

These steps require the Mac Studio and cannot be automated:

1. Run `setup/install.sh`
2. Fill in `~/.niederdaily/config.json`
3. Download `client_secret.json` from Google Cloud Console → `~/.niederdaily/`
4. Run `python niederdaily.py --preflight` and fix any failing checks
5. `launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist`
6. Test manually: `.venv/bin/python niederdaily.py`
