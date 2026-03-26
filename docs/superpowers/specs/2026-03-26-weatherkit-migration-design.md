# WeatherKit Migration Design

**Date:** 2026-03-26
**Status:** Approved

## Overview

Replace Open-Meteo with Apple WeatherKit REST API as the weather data source for NiederDaily. This yields richer condition codes, emoji icons, Haiku-generated weather sentences, and structured severe weather alerts.

## Goals

- Swap Open-Meteo for WeatherKit with no regression in existing data (temp, high/low, sunrise/sunset)
- Add emoji icon per weather condition
- Replace raw condition label with a Haiku-generated natural language sentence
- Surface active weather alerts as a linked banner in the email
- Keep the return dict interface stable so the welcome module and orchestrator need minimal changes

## Out of Scope

- Minute-by-minute precipitation forecast
- Historical weather averages
- Air quality data
- Provider abstraction / fallback to Open-Meteo

---

## 1. Apple Developer Setup (one-time, manual)

Before any code runs, the following must be configured in the Apple Developer portal:

1. Create a **Service ID** (e.g. `com.niederme.weatherkit`) under Certificates, Identifiers & Profiles
2. Enable the **WeatherKit** capability on that Service ID
3. Create a **private key** with WeatherKit enabled → download the `.p8` file
4. Note: **Team ID**, **Service ID**, **Key ID**

These four values, plus the path to the `.p8` file, are added to `config.json`.

---

## 2. Configuration (`config.json`)

The app loads `~/.niederdaily/config.json` via `config.py`. Add a top-level `"weatherkit"` key:

```json
{
  "weatherkit": {
    "team_id": "XXXXXXXXXX",
    "service_id": "com.niederme.weatherkit",
    "key_id": "XXXXXXXXXX",
    "key_file": "~/.credentials/AuthKey_XXXXXXXXXX.p8"
  }
}
```

`config.py` must be updated to validate these four required keys at startup (alongside existing required keys).

The existing `default_location` block (`name`, `lat`, `lon`) is unchanged.

---

## 3. `modules/weather.py` — Full Rewrite

### JWT Generation

A fresh JWT is generated on every newsletter run (no caching needed for once-daily use).

- Algorithm: ES256
- Header: `alg=ES256`, `kid=key_id`, `typ=JWT`
- Claims: `iss=team_id`, `sub=service_id`, `iat=now`, `exp=now+30min`
- Signed with the private key loaded from the `.p8` file

Dependency: `PyJWT` with `cryptography` extras (added to `requirements.txt`).

### API Call

Single request fetching all needed datasets, requesting imperial units to avoid manual conversion:

```
GET https://weatherkit.apple.com/api/v1/weather/en/{lat}/{lon}
    ?dataSets=currentWeather,forecastDaily,weatherAlerts
    &unitSystem=imperial
    Authorization: Bearer <token>
```

### Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `temp` | `currentWeather.temperature` | Fahrenheit (imperial), rounded |
| `condition` | `currentWeather.conditionCode` | mapped to display label via `CONDITION_LABELS` |
| `icon` | `currentWeather.conditionCode` | mapped to emoji via `CONDITION_ICONS` |
| `high` | `forecastDaily.days[0].temperatureMax` | Fahrenheit, rounded |
| `low` | `forecastDaily.days[0].temperatureMin` | Fahrenheit, rounded |
| `sunrise` | `forecastDaily.days[0].sunrise` | RFC 3339 timestamp → "H:MMam" |
| `sunset` | `forecastDaily.days[0].sunset` | RFC 3339 timestamp → "H:MMpm" |
| `alerts` | `weatherAlerts.alerts` | list, may be empty; key may be absent (unsupported regions) |

**Sunrise/sunset parsing:** WeatherKit returns RFC 3339 timestamps with timezone offset (e.g. `"2026-03-25T06:52:00-05:00"`). `datetime.fromisoformat()` (Python 3.11+) handles this correctly. The existing `_fmt_time` helper must be updated to accept these strings.

**Weather alerts availability:** The `weatherAlerts` key is only present in the response for supported regions (primarily US). Always use `data.get("weatherAlerts", {}).get("alerts", [])` — never direct key access.

### Condition Code → Label and Emoji Mappings

Two parallel dicts — `CONDITION_LABELS` for the display string (used by `welcome.py`) and `CONDITION_ICONS` for emoji (used by `renderer.py`):

```python
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

CONDITION_ICONS = {
    "Clear": "☀️",
    "MostlyClear": "🌤",
    "PartlyCloudy": "⛅",
    "MostlyCloudy": "🌥",
    "Cloudy": "☁️",
    "Foggy": "🌫",
    "Haze": "🌫",
    "Smoky": "🌫",
    "Breezy": "🌬",
    "Windy": "💨",
    "Drizzle": "🌦",
    "Rain": "🌧",
    "HeavyRain": "🌧",
    "SunShowers": "🌦",
    "Thunderstorms": "⛈",
    "IsolatedThunderstorms": "⛈",
    "ScatteredThunderstorms": "⛈",
    "StrongStorms": "⛈",
    "Flurries": "🌨",
    "Snow": "❄️",
    "SunFlurries": "🌨",
    "Sleet": "🌨",
    "WintryMix": "🌨",
    "FreezingDrizzle": "🌧",
    "FreezingRain": "🌧",
    "BlowingSnow": "🌨",
    "HeavySnow": "❄️",
    "Blizzard": "🌨",
    "BlowingDust": "🌬",
    "Frigid": "🥶",
    "Hail": "🌨",
    "Hot": "🥵",
    "Hurricane": "🌀",
    "TropicalStorm": "🌀",
}
```

Unknown condition codes fall back to `"condition"` → `"Unknown"` and `"icon"` → `"🌡"`.

### Return Dict

Same shape as today, with three additions (`icon`, `alerts`, `sentence`):

```python
{
    "location": str,       # location display name
    "temp": int,           # current temp in °F
    "condition": str,      # human-readable label, e.g. "Partly Cloudy" — used by welcome.py
    "icon": str,           # emoji, e.g. "⛅" — used by renderer
    "high": int,           # daily high in °F
    "low": int,            # daily low in °F
    "sunrise": str,        # e.g. "6:52am"
    "sunset": str,         # e.g. "7:31pm"
    "alerts": list[dict],  # [] when none active or region unsupported
    "sentence": str,       # Haiku-generated sentence — home location only; "" for travel
}
```

Each alert dict:

```python
{
    "event": str,      # e.g. "Winter Storm Warning"
    "expires": str,    # formatted, e.g. "Thu 6:00pm"
    "agency": str,     # e.g. "NWS Chicago"
    "url": str,        # link to full alert (from WeatherKit detailsUrl field)
}
```

### Error Handling

On any failure (network, auth, bad response), `fetch_weather()` returns `None` — same behavior as today. The orchestrator already handles `None` gracefully.

---

## 4. `modules/weather.py` — Haiku Sentence

After fetching weather data, a brief Haiku call generates a 1-sentence weather description for the home location only. Travel locations receive an empty `sentence` string (the condition label is still available via `condition`).

**API key access:** `weather_block(config, calendar_events)` already receives the full config dict. The Anthropic API key is accessed via `config["anthropic_api_key"]`, matching the pattern used elsewhere in the codebase.

**Prompt (approximate):**

> "Write a single short sentence describing today's weather for {location}. Current: {temp}°F, {condition}. High {high}°, Low {low}°. Be specific and vivid. No greeting. Plain text only."

**Example output:** `"Bundle up — snow likely this afternoon with temperatures dropping to 28°."`

---

## 5. `renderer.py` — Weather Section Updates

### Updated layout:

```
WEATHER · CHICAGO

⛅ 48°
Bundle up — expect afternoon showers clearing by evening.
High 52° · Low 41° · Sunrise 6:14am · Sunset 7:22pm

⚠ FLOOD WATCH →
Until Thu 6:00pm · NWS Chicago

Weather
```

### Changes to `_weather_html()`:

- **Big line**: icon + temp only (condition label removed from display)
- **Sentence line**: Haiku-generated sentence (`loc["sentence"]`), smaller font, below the temp; omitted if empty string (travel locations)
- **Metadata line**: High/Low · Sunrise · Sunset (unchanged)
- **Alert banner** (only when `loc["alerts"]` is non-empty): rendered below metadata
  - `⚠ {event}` as a linked anchor (`href=alert["url"]`)
  - Expiry and agency in smaller text below
  - Styled with amber/red accent (e.g. `color: #c0392b`)
- **Attribution**: small linked "Weather" line at bottom per Apple requirement (`href="https://weatherkit.apple.com/legal-attribution.html"`)

---

## 6. `niederdaily.py` — Preflight Update

The existing preflight check tests Open-Meteo connectivity. This must be replaced with a WeatherKit connectivity check: generate a JWT and make a lightweight availability call to `GET /api/v1/availability/{lat}/{lon}` to confirm credentials and network access are working.

---

## 7. `tests/test_weather.py` — Updates

- Replace Open-Meteo mock responses with WeatherKit mock JSON responses
- Add test for JWT generation: mock signing, assert header includes `typ=JWT`, assert claims (`iss`, `sub`, `iat`, `exp`)
- Add tests for `CONDITION_LABELS` and `CONDITION_ICONS` mappings (known and unknown codes)
- Add tests for alert parsing, including absent `weatherAlerts` key (unsupported region)
- Add test for graceful `None` return on API failure
- Add test for Haiku sentence: mock the Anthropic call, assert `"sentence"` key present for home location and `""` for travel location
- Add test for RFC 3339 sunrise/sunset parsing via updated `_fmt_time`

---

## 8. Attribution (Apple Requirement)

Apple requires displaying the "Weather" trademark as a link when showing WeatherKit data. Rendered at the bottom of every weather section:

```html
<a href="https://weatherkit.apple.com/legal-attribution.html">Weather</a>
```

---

## Dependencies

- `PyJWT[cryptography]` — JWT generation with ES256 (new)
- No other new dependencies; `requests` already in use

---

## Files Changed

| File | Change |
|------|--------|
| `~/.niederdaily/config.json` (user config) | Add `"weatherkit"` block |
| `config.py` | Validate new `weatherkit.*` required keys |
| `modules/weather.py` | Full rewrite |
| `renderer.py` | Update `_weather_html()` |
| `niederdaily.py` | Update preflight to test WeatherKit connectivity |
| `tests/test_weather.py` | Update mocks and add new test cases |
| `requirements.txt` | Add `PyJWT[cryptography]` |
