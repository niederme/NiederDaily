from __future__ import annotations

import requests
from datetime import datetime
import logging

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
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
USER_AGENT = "NiederDaily/1.0 (personal newsletter)"
DEFAULT_TRAVEL_CALENDARS = {"Little York", "niederCal", "TripIt"}
SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
log = logging.getLogger(__name__)


def wmo_label(code: int) -> str:
    return WMO_CODES.get(code, "Unknown")


def _fmt_time(iso: str) -> str:
    """Convert '2026-03-25T06:52' to '6:52am'."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return iso


def _lower_condition(condition: str) -> str:
    c = condition.lower()
    if "thunder" in c:
        return "Stormy today"
    if "snow" in c or "ice" in c:
        return "Snowy today"
    if "rain" in c or "drizzle" in c or "shower" in c:
        return "Rainy today"
    if "fog" in c:
        return "Foggy today"
    if "overcast" in c:
        return "Overcast today"
    if "partly cloudy" in c:
        return "Partly cloudy today"
    if "mainly clear" in c:
        return "Mostly clear today"
    if "clear" in c or "sun" in c:
        return "Clear today"
    return f"{condition} today"


def _period_label(hour: int) -> str:
    if 5 <= hour < 12:
        return "this morning"
    if 12 <= hour < 17:
        return "this afternoon"
    if 17 <= hour < 22:
        return "this evening"
    return "overnight"


def _peak_gust_summary(hourly: dict) -> tuple[int, str] | None:
    times = hourly.get("time", [])
    gusts = hourly.get("wind_gusts_10m", [])
    peak = None
    for iso, gust in zip(times, gusts):
        if gust is None:
            continue
        try:
            dt = datetime.fromisoformat(iso)
        except Exception:
            continue
        candidate = (round(gust), dt.hour)
        if peak is None or candidate[0] > peak[0]:
            peak = candidate
    if peak is None:
        return None
    return peak[0], _period_label(peak[1])


def _alert_end_phrase(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%-I:%M%p").lower()
    except Exception:
        return None


def _top_alert(features: list[dict]) -> dict | None:
    if not features:
        return None

    def sort_key(feature: dict):
        props = feature.get("properties", {})
        severity = props.get("severity", "Unknown")
        ends = props.get("ends") or props.get("expires") or ""
        return (-SEVERITY_RANK.get(severity, 0), ends)

    return sorted(features, key=sort_key)[0]


def _fetch_alert_summary(lat: float, lon: float) -> str | None:
    try:
        resp = requests.get(
            NWS_ALERTS_URL,
            params={"point": f"{lat},{lon}"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=10,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        alert = _top_alert(features)
        if not alert:
            return None
        props = alert.get("properties", {})
        event = props.get("event")
        if not event:
            headline = props.get("headline")
            if headline:
                return headline.rstrip(".") + "."
            return None
        end_phrase = _alert_end_phrase(props.get("ends") or props.get("expires"))
        if end_phrase:
            return f"{event} in effect until {end_phrase}."
        return f"{event} in effect."
    except Exception:
        return None


def _summary_line(condition: str, daily: dict, hourly: dict, alert_summary: str | None = None) -> str:
    today_phrase = _lower_condition(condition)
    condition_lower = condition.lower()

    gust_phrase = None
    peak_gust = _peak_gust_summary(hourly)
    if peak_gust and peak_gust[0] >= 25:
        gust_phrase = f"with gusts up to {peak_gust[0]} mph {peak_gust[1]}"

    precip_probs = daily.get("precipitation_probability_max", [])
    precip_max = round(precip_probs[0]) if precip_probs and precip_probs[0] is not None else None
    precip_phrase = None
    if precip_max is not None and precip_max >= 40 and not any(word in condition_lower for word in ["rain", "drizzle", "shower", "storm", "snow"]):
        precip_phrase = f"Rain chances up to {precip_max}% today."

    today_sentence = None
    if gust_phrase:
        today_sentence = f"{today_phrase}, {gust_phrase}."
    elif precip_phrase:
        today_sentence = f"{today_phrase}. {precip_phrase}"
    else:
        today_sentence = f"{today_phrase}."

    if alert_summary:
        return f"{alert_summary} {today_sentence}"
    return today_sentence


def fetch_weather(lat: float, lon: float, name: str) -> dict | None:
    last_error = None
    for _ in range(2):
        try:
            resp = requests.get(OPEN_METEO_URL, params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weathercode",
                "hourly": "wind_gusts_10m",
                "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max,weathercode",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
                "forecast_days": 2,
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            current = data["current"]
            daily = data["daily"]
            hourly = data.get("hourly", {})
            alert_summary = _fetch_alert_summary(lat, lon)
            return {
                "location": name,
                "temp": round(current["temperature_2m"]),
                "condition": wmo_label(current["weathercode"]),
                "high": round(daily["temperature_2m_max"][0]),
                "low": round(daily["temperature_2m_min"][0]),
                "sunrise": _fmt_time(daily["sunrise"][0]),
                "sunset": _fmt_time(daily["sunset"][0]),
                "summary": _summary_line(wmo_label(current["weathercode"]), daily, hourly, alert_summary=alert_summary),
            }
        except Exception as exc:
            last_error = exc
    log.warning("Weather fetch failed for %s (%s, %s): %s", name, lat, lon, last_error)
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
    except Exception as exc:
        log.warning("Weather geocode failed for %r: %s", location_str, exc)
        return None


def weather_block(config: dict, calendar_events: list) -> dict | None:
    default = config["default_location"]
    home = fetch_weather(default["lat"], default["lon"], default["name"])
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
        # Check if it's a different city (rough: compare display name vs default name)
        if default["name"].split(",")[0].lower() not in geo["name"].lower():
            travel = fetch_weather(geo["lat"], geo["lon"], geo["name"].split(",")[0].strip())
            travel_city = geo["name"].split(",")[0].strip()
            break

    locations = [home]
    if travel:
        locations.append(travel)

    return {"locations": locations, "travel_city": travel_city}
