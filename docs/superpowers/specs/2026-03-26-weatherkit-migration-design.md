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

These four values, plus the path to the `.p8` file, are added to `config.yaml`.

---

## 2. Configuration (`config.yaml`)

Add a top-level `weatherkit:` block:

```yaml
weatherkit:
  team_id: "XXXXXXXXXX"
  service_id: "com.niederme.weatherkit"
  key_id: "XXXXXXXXXX"
  key_file: "~/.credentials/AuthKey_XXXXXXXXXX.p8"
```

The existing `default_location` block (with `name`, `lat`, `lon`) is unchanged and still used for geocoding.

---

## 3. `modules/weather.py` — Full Rewrite

### JWT Generation

A fresh JWT is generated on every newsletter run (no caching needed for once-daily use).

- Algorithm: ES256
- Header: `alg=ES256`, `kid=key_id`
- Claims: `iss=team_id`, `sub=service_id`, `iat=now`, `exp=now+30min`
- Signed with the private key loaded from the `.p8` file

Dependency: `PyJWT` with `cryptography` extras (already available or added to requirements).

### API Call

Single request fetching all needed datasets:

```
GET https://weatherkit.apple.com/api/v1/weather/en/{lat}/{lon}
    ?dataSets=currentWeather,forecastDaily,weatherAlerts
    Authorization: Bearer <token>
```

### Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `temp` | `currentWeather.temperature` | °C → °F, rounded |
| `condition` | `currentWeather.conditionCode` | mapped to display label |
| `icon` | `currentWeather.conditionCode` | mapped to emoji |
| `high` | `forecastDaily.days[0].temperatureMax` | °C → °F, rounded |
| `low` | `forecastDaily.days[0].temperatureMin` | °C → °F, rounded |
| `sunrise` | `forecastDaily.days[0].sunrise` | formatted as "H:MMam" |
| `sunset` | `forecastDaily.days[0].sunset` | formatted as "H:MMpm" |
| `alerts` | `weatherAlerts.alerts` | list, may be empty |

### Condition Code → Emoji Mapping

Full mapping of WeatherKit condition codes to emoji:

```python
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

### Return Dict

Same shape as today, with two additions:

```python
{
    "location": str,       # location display name
    "temp": int,           # current temp in °F
    "condition": str,      # human-readable label (e.g. "Partly Cloudy")
    "icon": str,           # emoji (e.g. "⛅")
    "high": int,           # daily high in °F
    "low": int,            # daily low in °F
    "sunrise": str,        # e.g. "6:52am"
    "sunset": str,         # e.g. "7:31pm"
    "alerts": list[dict],  # [] when none active
}
```

Each alert dict:

```python
{
    "event": str,         # e.g. "Winter Storm Warning"
    "expires": str,       # formatted expiry, e.g. "Thu 6:00pm"
    "agency": str,        # e.g. "NWS Chicago"
    "url": str,           # detailsUrl linking to full alert
}
```

### Error Handling

On any failure (network, auth, bad response), `fetch_weather()` returns `None` — same behavior as today. The orchestrator already handles `None` gracefully.

---

## 4. `modules/weather.py` — Haiku Sentence

After fetching weather data, a brief Haiku call generates a 1–2 sentence weather description for display in the email. This replaces the raw condition label in the big display line.

**Prompt (approximate):**

> "Write a single short sentence describing today's weather for {location}. Current: {temp}°F, {condition}. High {high}°, Low {low}°. Be specific and vivid. No greeting. Plain text only."

**Example output:** `"Bundle up — snow likely this afternoon with temperatures dropping to 28°."`

This call is made inside `weather_block()` after data is fetched, adding a `"sentence"` key to the return dict.

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
```

### Changes to `_weather_html()`:

- **Big line**: icon + temp only (condition label removed)
- **Sentence line**: Haiku-generated sentence, smaller font, below the temp
- **Metadata line**: High/Low · Sunrise · Sunset (unchanged)
- **Alert banner** (only when `alerts` is non-empty): rendered below metadata
  - `⚠ {event}` as a linked anchor (`href=detailsUrl`)
  - Expiry and agency in smaller text below
  - Styled with amber/red accent (e.g. `color: #c0392b` or `background: #fff3cd`)
- **Attribution**: small "Powered by Weather" line at bottom of section (Apple requirement)

---

## 6. `tests/test_weather.py` — Updates

- Replace Open-Meteo mock responses with WeatherKit mock responses
- Add tests for JWT generation (mock the signing, assert correct claims)
- Add tests for condition code → emoji mapping
- Add tests for alert parsing
- Add test for graceful `None` return on API failure
- Haiku sentence generation: mock the Haiku call, assert `"sentence"` key present

---

## 7. Attribution (Apple Requirement)

Apple requires displaying the "Weather" trademark when showing WeatherKit data. Add a small line at the bottom of the weather section:

```html
<a href="https://weatherkit.apple.com/legal-attribution.html">Weather</a>
```

---

## Dependencies

- `PyJWT[cryptography]` — JWT generation with ES256
- No other new dependencies; `requests` already in use

---

## Files Changed

| File | Change |
|------|--------|
| `config.yaml` (template/docs) | Add `weatherkit:` block |
| `modules/weather.py` | Full rewrite |
| `renderer.py` | Update `_weather_html()` |
| `tests/test_weather.py` | Update mocks and add new test cases |
| `requirements.txt` | Add `PyJWT[cryptography]` |
