from __future__ import annotations

import anthropic
from datetime import date

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
    "or say 'your birthday' unless the title explicitly says 'John's birthday', names John Niedermeyer, "
    "or the context includes the line TODAY IS JOHN'S OWN BIRTHDAY. When that line is present the birthday "
    "really is his, it outranks every other hook, and a calendar entry naming someone else is still theirs. "
    "Initials, nicknames, and shorthand in an event title never mean John — resolve them only with the "
    "Calendar shorthand notes provided, and if a name is unfamiliar treat it as a third party. "
    "Do not combine multiple hooks. Do not connect unrelated pieces of context. "
    "Mention weather only if genuinely remarkable. Do not summarize the day — find one angle and commit to it. "
    "Return only the greeting sentence. Never explain your choice, weigh candidate hooks aloud, quote these "
    "instructions, or refer to the context you were given."
)

CALENDAR_NAME_NOTES = {
    "DC": "Danielle",
    "JN": "John",
    "JoB": "Jobeth Leon",
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


def _is_recipient_birthday(birthday: str | None, today: date) -> bool:
    """True when today is the recipient's own birthday.

    Accepts "YYYY-MM-DD" or "MM-DD" — only month and day are compared, so the
    birth year stays optional and is never needed to match.
    """
    if not birthday:
        return False
    parts = str(birthday).strip().split("-")
    if len(parts) < 2:
        return False
    try:
        month, day = int(parts[-2]), int(parts[-1])
    except ValueError:
        return False
    return (today.month, today.day) == (month, day)


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
    recipient_birthday: str | None = None,
    as_of: date | None = None,
) -> str | None:
    if not api_key:
        return None
    if not weather_data and not calendar_events:
        return None
    try:
        today = as_of or date.today()
        day_name = today.strftime("%A")
        date_str = today.strftime("%B %-d, %Y")

        parts = [f"Today is {day_name}, {date_str}."]

        if _is_recipient_birthday(recipient_birthday, today):
            parts.append("TODAY IS JOHN'S OWN BIRTHDAY — the recipient's own, not a third party's.")

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
                    event_lines.append(f"[{priority}] {event['title']} ({when})")
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
