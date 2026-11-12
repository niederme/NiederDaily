"""Deterministic "where is the reader today" fact, derived before the model sees anything.

Sources, all configured in the profile (see modules/profile.py and the README):
- All-day "<PREFIX>: <place>" day markers (`day_marker_prefixes`) say where the reader
  is for the day: "JD: Boston" is a trip, "JD: WFH" or "JD: Home" a home day
  (`home_keywords`), and a `commute.city_aliases` place is a commute day.
- Commute timetable events ("<line> 12 Inbound", `commute.transit_lines`): an Inbound
  event is the booked ride into the commute city. Outbound events are evening return
  options, often more than one, so they bound the return time but never confirm
  which ride the reader takes.
- Timed entries on the reader's own calendars (`own_calendars`) located in the
  commute city (`commute.location_keywords`) imply a commute day.
- Weather travel detection with travel_confirmed (TripIt, flight, trip) is away.

When signals conflict, or there are none, the status is "unknown": the opening
must not assume the reader is home.
"""
from __future__ import annotations

import re

from modules import profile
from modules.calendar import is_transit_option


def _prefix_pattern(prefixes) -> str | None:
    names = [re.escape(p) for p in prefixes or [] if p]
    return "|".join(names) or None


def _day_marker(title: str):
    prefixes = _prefix_pattern(profile.get()["day_marker_prefixes"])
    if not prefixes:
        return None
    return re.match(rf"^\s*(?:{prefixes})\s*:\s*(?P<place>[^()]+?)\s*(?:\(.*\))?\s*$", title or "", re.I)


def _other_owner(title: str) -> bool:
    prefixes = _prefix_pattern(profile.get()["household_prefixes"])
    return bool(prefixes and re.match(rf"^\s*(?:{prefixes})\s*:", title or "", re.I))


def _city_location(location: str) -> bool:
    keywords = [k for k in profile.get()["commute"].get("location_keywords") or [] if k]
    return any(re.search(rf"\b{re.escape(k)}\b", location or "", re.I) for k in keywords)


def is_day_marker(event: dict) -> bool:
    """All-day "<PREFIX>: <place>" entries; summarized by LOCATION rather than listed as events."""
    return bool(event.get("all_day") and _day_marker(event.get("title") or ""))


def _fold(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _place(raw: str) -> str:
    commute = profile.get()["commute"]
    city = commute.get("city")
    if city and _fold(raw) in {_fold(a) for a in [city, *(commute.get("city_aliases") or [])]}:
        return city
    return raw.strip()


def _clock_minutes(label: str | None) -> int | None:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(am|pm)\s*$", label or "", re.I)
    if not match:
        return None
    hour = int(match[1]) % 12 + (12 if match[3].lower() == "pm" else 0)
    return hour * 60 + int(match[2])


def _result(status, place=None, depart=None, back=None, source=None, evidence=None) -> dict:
    return {"status": status, "place": place, "depart": depart, "back": back,
            "commute_source": source, "evidence": evidence or []}


def derive_location(calendar_events: list | None, weather_data: dict | None = None) -> dict:
    conf = profile.get()
    commute = conf["commute"]
    city = commute.get("city")
    home_keywords = {_fold(k) for k in conf["home_keywords"] or []}
    own_calendars = {_fold(c) for c in conf["own_calendars"] or []}
    events = calendar_events or []
    away, home, evidence = [], [], []

    for event in events:
        title = (event.get("title") or "").strip()
        if not event.get("all_day"):
            continue
        marker = _day_marker(title)
        if not marker:
            continue
        place = marker["place"].strip()
        if _fold(place) in home_keywords:
            home.append(title)
        else:
            away.append(_place(place))
        evidence.append(title)

    inbound = [e for e in events if is_transit_option(e) and re.search(r"\bInbound\b", e.get("title") or "", re.I)]
    outbound = [e for e in events if is_transit_option(e) and re.search(r"\bOutbound\b", e.get("title") or "", re.I)]
    if inbound and city:
        away.append(city)
        evidence.append(inbound[0].get("title"))

    for event in events:
        if not city or event.get("all_day") or is_transit_option(event):
            continue
        if _fold(event.get("calendar") or "") not in own_calendars:
            continue
        if _other_owner(event.get("title") or ""):
            continue
        if _city_location(event.get("location") or ""):
            away.append(city)
            evidence.append(event.get("title"))

    if (weather_data or {}).get("travel_confirmed") and (weather_data or {}).get("travel_city"):
        away.append(weather_data["travel_city"])
        evidence.append("confirmed travel")

    if away and home or len(set(away)) > 1 and (not city or city not in away):
        return _result("unknown", evidence=evidence)
    if home:
        return _result("home", place=conf.get("home_label"), evidence=evidence)
    if not away:
        return _result("unknown", evidence=evidence)

    # A same-day commute plus an out-of-region destination: the farther one wins.
    others = [p for p in away if p != city]
    place = others[0] if others else city
    depart = back = source = None
    if city and place == city:
        departures = sorted(filter(None, (_clock_minutes(e.get("time")) for e in inbound)))
        returns = sorted(filter(None, (_clock_minutes(e.get("end_time") or e.get("time")) for e in outbound)))
        if departures:
            depart = next(e.get("time") for e in inbound if _clock_minutes(e.get("time")) == departures[0])
            source = "calendar"
        if returns:
            latest = returns[-1]
            back = next((e.get("end_time") or e.get("time")) for e in outbound
                        if _clock_minutes(e.get("end_time") or e.get("time")) == latest)
            source = "calendar"
        if not depart and not back and (commute.get("depart") or commute.get("home")):
            depart, back, source = commute.get("depart"), commute.get("home"), "usual"
    return _result("away", place=place, depart=depart, back=back, source=source, evidence=evidence)


def location_line(location: dict) -> str:
    conf = profile.get()
    commute = conf["commute"]
    name = profile.owner()
    mode = commute.get("mode") or "bus"
    status = location.get("status")
    if status == "home":
        where = f" in {location['place']}" if location.get("place") else ""
        return (f"LOCATION: {name} is home{where} today, per the calendar ("
                + "; ".join(location["evidence"]) + ").")
    if status == "away":
        line = f"LOCATION: {name} is away in {location['place']} today"
        if commute.get("city") and location["place"] == commute["city"]:
            home_label = conf.get("home_label")
            parts = []
            if location.get("commute_source") == "usual":
                if location.get("depart"):
                    parts.append(f"on the usual commute: out on the {location['depart']} {mode}")
                if location.get("back"):
                    parts.append(f"back home{f' in {home_label}' if home_label else ''} about {location['back']}")
            else:
                if location.get("depart"):
                    parts.append(f"leaving on the {location['depart']} {mode}")
                if location.get("back"):
                    stop = commute.get("arrival_stop")
                    parts.append(f"the last listed {mode} home "
                                 + (f"reaches {stop}" if stop else "arrives")
                                 + f" about {location['back']}")
            if parts:
                line += ", " + ", ".join(parts)
        return line + f". {name[:1].upper() + name[1:]} is not home during the day."
    return f"LOCATION: unknown. The calendar does not say whether {name} is home or away today."
