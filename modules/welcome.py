from __future__ import annotations

import anthropic
from datetime import date

SYSTEM_PROMPT = (
    "You write a single witty, warm, first-person morning greeting for a personal daily newsletter. "
    "One sentence only. Dry wit welcome. No exclamation marks. Do not start with 'Good morning.' "
    "Pick exactly ONE hook from the context and write only about that — a single news headline, "
    "a single calendar event, a memory photo, or the message situation. "
    "Do not combine multiple hooks. Do not connect unrelated pieces of context. "
    "Mention weather only if genuinely remarkable. Do not summarize the day — find one angle and commit to it."
)

CALENDAR_NAME_NOTES = {
    "DC": "Danielle",
    "JN": "John",
}


def welcome_block(
    api_key: str,
    weather_data: dict | None,
    calendar_events: list | None,
    nyt_stories: list | None = None,
    photo: tuple | None = None,
    messages: dict | None = None,
) -> str | None:
    if not api_key:
        return None
    if not weather_data and not calendar_events:
        return None
    try:
        today = date.today()
        day_name = today.strftime("%A")
        date_str = today.strftime("%B %-d, %Y")

        parts = [f"Today is {day_name}, {date_str}."]

        if weather_data and weather_data.get("locations"):
            w = weather_data["locations"][0]
            parts.append(f"Weather in {w['location']}: {w['temp']}°F, {w['condition']}.")

        if calendar_events:
            timed = [e for e in calendar_events if not e.get("all_day")]
            if timed:
                parts.append(f"First event: {timed[0]['title']} at {timed[0]['time']}.")

            titles = " ".join((e.get("title") or "") for e in calendar_events)
            matched_notes = [
                f"{initials} means {name}"
                for initials, name in CALENDAR_NAME_NOTES.items()
                if initials in titles
            ]
            if matched_notes:
                parts.append("Calendar shorthand: " + "; ".join(matched_notes) + ".")

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

        if messages and messages.get("thread_count", 0) > 0:
            parts.append(f"MESSAGES: {messages['summary']}")

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
