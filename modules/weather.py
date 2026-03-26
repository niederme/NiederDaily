import jwt
import time
from pathlib import Path
import requests
from datetime import datetime
from typing import Optional

WEATHERKIT_URL = "https://weatherkit.apple.com/api/v1/weather/en"

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


def wmo_label(code: int) -> str:
    return WMO_CODES.get(code, "Unknown")


def _fmt_time(iso: str) -> str:
    """Convert '2026-03-25T06:52' to '6:52am'."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return iso


def fetch_weather(lat: float, lon: float, name: str) -> Optional[dict]:
    try:
        resp = requests.get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weathercode",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
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


def geocode_location(location_str: str) -> Optional[dict]:
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


def weather_block(config: dict, calendar_events: list) -> Optional[dict]:
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
