from __future__ import annotations

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

# No CONDITION_ICONS dict needed — renderer uses existing _weather_icon() SVGs,
# which keyword-match on the condition string (e.g. "rain", "snow", "thunder", "clear", "fog").


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
    """Convert RFC 3339 timestamp (e.g. '2026-03-25T06:52:00Z') to '6:52am'."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return iso


def _parse_alert(raw: dict) -> dict:
    expires_raw = raw.get("eventEndTime", "")
    try:
        expires = datetime.fromisoformat(expires_raw).strftime("%a %-I:%M%p").lower()
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
                "unitSystem": "i",
                "countryCode": "US",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data["currentWeather"]
        today = data["forecastDaily"]["days"][0]
        code = today["conditionCode"]
        alerts_raw = data.get("weatherAlerts", {}).get("alerts", [])

        def c_to_f(c: float) -> int:
            return round(c * 9 / 5 + 32)

        return {
            "location": name,
            "temp": c_to_f(current["temperature"]),
            "condition": CONDITION_LABELS.get(code, "Unknown"),
            "high": c_to_f(today["temperatureMax"]),
            "low": c_to_f(today["temperatureMin"]),
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
            "q": location_str, "format": "json", "limit": 1, "addressdetails": 1,
        }, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        r = results[0]
        addr = r.get("address", {})
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("municipality")
            or addr.get("city_district")
            or addr.get("suburb")
        )
        if not city:
            # No city-level field — parse the original input string before falling
            # back to county or display_name (both can be unhelpfully broad/raw).
            for part in [p.strip() for p in location_str.split(",")]:
                if not part or part[0].isdigit() or len(part) <= 2:
                    continue
                if any(kw in part for kw in ("United States", "USA", "Canada")):
                    continue
                city = part
                break
            else:
                city = addr.get("county") or r["display_name"].split(",")[0].strip()
        state = addr.get("state_code") or addr.get("state", "")
        name = f"{city}, {state}" if state else city
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "name": name}
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
