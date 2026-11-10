from __future__ import annotations

import anthropic
import json
from datetime import date

from modules.opening_safety import calendar_kind, opening_rejection, package_context

SYSTEM_PROMPT = (
    "You write a single witty, warm, first-person morning greeting for a personal daily newsletter. "
    "The newsletter belongs to John — when 'John' appears in a calendar event, that is the recipient himself, not a third party. "
    "One sentence only. Dry wit welcome. No exclamation marks. Do not start with 'Good morning.' "
    "Pick exactly ONE hook from the context and write only about that — prefer a news headline, "
    "calendar event, memory photo, or a notable tweet over the message situation. Only use messages as a hook "
    "if nothing else is interesting. When you do use messages, keep it warm and light, not snarky. "
    "Calendar order is chronological, not editorial: do not favor an event because it is first or early. "
    "Treat events labeled ROUTINE as low-interest background and avoid using them when any worthwhile "
    "news, memory photo, non-routine event, travel, or remarkable weather is available. "
    "A birthday calendar entry belongs to the person named in its title. Never call it John's birthday "
    "or say 'your birthday' unless the title explicitly says 'John's birthday' or names John Niedermeyer. "
    "Do not combine multiple hooks. Do not connect unrelated pieces of context. "
    "Parcel calendar entries are delivery context, not pickups, errands, or attendance commitments. "
    "An estimated delivery window is not an appointment at its start time. Never join calendar and package records by merchant name alone. "
    "Keep reminder actions literal: a check is not a call, order, booking, or payment. Do not invent urgency, consequences, or how long an item has waited. "
    "Mention weather only if genuinely remarkable. Do not summarize the day — find one angle and commit to it."
)

CALENDAR_NAME_NOTES = {
    "DC": "Danielle",
    "JN": "John",
}

# Maps substrings found in calendar event titles to context notes injected into the prompt.
# Add entries here whenever the AI gets something wrong about a recurring person or event.
EVENT_CONTEXT = {
    "Alaia": "Alaia is the neighbor's child. John helps get her on the school bus twice a week; this is ordinary recurring logistics, not a notable occasion.",
    "Allison": "Allison is John's therapist — 'Allison and John's session' is a weekly therapy appointment.",
    "Buffalo Sabres": "Buffalo Sabres games appear from a subscribed sports calendar — John watches from home on TV unless other calendar events show he is traveling to that game's city.",
    "Buffalo Bills": "Buffalo Bills games appear from a subscribed sports calendar — John watches from home on TV unless other calendar events show he is traveling to that game's city.",
}

ROUTINE_EVENT_KEYWORDS = (
    "Alaia",
)


def _is_routine_event(event: dict) -> bool:
    title = event.get("title") or ""
    return any(keyword.casefold() in title.casefold() for keyword in ROUTINE_EVENT_KEYWORDS)


def welcome_block(
    api_key: str,
    weather_data: dict | None,
    calendar_events: list | None,
    nyt_stories: list | None = None,
    photo: tuple | None = None,
    messages: dict | None = None,
    tweet: dict | None = None,
    as_of: date | None = None,
    reminders: dict | None = None,
    packages: dict | None = None,
) -> str | None:
    if not api_key:
        return None
    if not any((weather_data, calendar_events, nyt_stories, photo, tweet, reminders, packages)):
        return None
    try:
        today = as_of or date.today()
        day_name = today.strftime("%A")
        date_str = today.strftime("%B %-d, %Y")

        parts = [f"Today is {day_name}, {date_str}."]

        if weather_data and weather_data.get("locations"):
            w = weather_data["locations"][0]
            parts.append(f"Weather in {w['location']}: {w['temp']}°F, {w['condition']}.")
            if weather_data.get("travel_city"):
                parts.append(f"Traveling to {weather_data['travel_city']} today.")

        if calendar_events:
            timed = [e for e in calendar_events if not e.get("all_day")]
            all_day = [e for e in calendar_events if e.get("all_day")]
            ordered = (
                [e for e in timed if not _is_routine_event(e)]
                + [e for e in all_day if not _is_routine_event(e)]
                + [e for e in timed if _is_routine_event(e)]
                + [e for e in all_day if _is_routine_event(e)]
            )
            if ordered:
                event_lines = []
                for event in ordered[:6]:
                    priority = "ROUTINE" if _is_routine_event(event) else "CANDIDATE"
                    when = "all day" if event.get("all_day") else event.get("time", "time unknown")
                    kind = calendar_kind(event)
                    if kind == "delivery":
                        # Parcel's start alone is never a pickup appointment or exact ETA.
                        when = (f"estimated window {when}–{event['end_time']}"
                                if event.get("end_time") else "delivery timing not established")
                    event_lines.append(
                        f"[{priority}] {event['title']} ({when}; "
                        f"source calendar: {event.get('calendar') or 'unknown'}; type: {kind}; "
                        f"owner: {event.get('owner') or 'unknown'})")
                parts.append("CALENDAR OPTIONS, ranked by editorial interest: " + " / ".join(event_lines) + ".")

            titles = " ".join((e.get("title") or "") for e in calendar_events)
            matched_notes = [
                f"{initials} means {name}"
                for initials, name in CALENDAR_NAME_NOTES.items()
                if initials in titles
            ]
            if matched_notes:
                parts.append("Calendar shorthand: " + "; ".join(matched_notes) + ".")

            matched_context = [
                note
                for keyword, note in EVENT_CONTEXT.items()
                if keyword in titles
            ]
            if matched_context:
                parts.append("Context: " + " ".join(matched_context))

        if reminders:
            reminder_lines = []
            for bucket in ("today", "overdue", "upcoming"):
                for item in reminders.get(bucket, [])[:5]:
                    reminder_lines.append(
                        f"[{bucket.upper()}] {item.get('title') or ''} "
                        f"(list: {item.get('list') or 'unknown'}; due: {item.get('due') or 'unspecified'})"
                    )
            if reminder_lines:
                parts.append("REMINDERS: " + " / ".join(reminder_lines))

        parcel_facts = package_context(packages)
        if parcel_facts:
            parts.append("PARCEL FACTS (separate records; estimates, not appointments; "
                         "coverage may be incomplete): " + json.dumps(parcel_facts, ensure_ascii=False))

        if nyt_stories:
            titles = " / ".join(f'"{s["title"]}"' for s in nyt_stories[:3] if s.get("title"))
            if titles:
                parts.append(f"NEWS: {titles}.")

        if photo:
            _, meta = photo
            year = meta.get("year", "")
            location = meta.get("location", "")
            desc = meta.get("description", "")
            fav = " ★" if meta.get("is_favorite") else ""
            loc_part = f", {location}" if location else ""
            if desc:
                parts.append(f"MEMORY PHOTO ({year}{loc_part}{fav}): {desc}")
            elif year:
                parts.append(f"MEMORY PHOTO from {year}{loc_part}{fav}.")

        if tweet and (tweet.get("text") or "").strip():
            text = tweet["text"].strip()
            source = tweet.get("source")
            handle = tweet.get("handle") or ""
            if source == "authored":
                year = tweet.get("year", "")
                label = f"YOUR TWEET on this day{f' in {year}' if year else ''}"
            elif source == "bookmarked":
                label = f"TWEET YOU BOOKMARKED{f' (by @{handle})' if handle else ''}"
            else:
                label = f"TWEET YOU LIKED{f' (by @{handle})' if handle else ''}"
            parts.append(f'{label}: "{text}"')

        # A generated Messages quip is not evidence of an unanswered message.

        user_prompt = " ".join(parts)

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return validate_opening(response.content[0].text, calendar_events=calendar_events,
                                weather_data=weather_data, reminders=reminders, packages=packages)
    except Exception:
        return None


def validate_opening(text, *, calendar_events=None, weather_data=None, reminders=None, packages=None):
    """Omit recognized unsupported claims; this is not a general fact checker."""
    if not isinstance(text, str) or not text.strip():
        return None
    if opening_rejection(text, calendar_events or [], reminders, packages):
        return None
    return text.strip()
