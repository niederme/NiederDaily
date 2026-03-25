import anthropic
from datetime import date

SYSTEM_PROMPT = (
    "You write a single witty, warm, first-person morning greeting for a personal daily newsletter. "
    "One sentence only. Dry wit welcome. Reference the weather or the day's plans naturally. "
    "Do not start with 'Good morning'. Do not use exclamation marks."
)


def welcome_block(api_key: str, weather_data: dict | None, calendar_events: list | None) -> str | None:
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
