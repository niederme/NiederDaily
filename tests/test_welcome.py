from datetime import date

import pytest
from unittest.mock import MagicMock

from modules import profile
from modules.welcome import validate_opening, welcome_block

# A made-up reader. Real conventions live only in ~/.niederdaily/config.json.
PROFILE = {
    "owner_name": "Jordan",
    "owner_full_name": "Jordan Doe",
    "employer": "Acme",
    "day_marker_prefixes": ["JD"],
    "home_keywords": ["home", "wfh", "springfield"],
    "home_label": "Springfield",
    "household_prefixes": {"AB": "Alex"},
    "own_calendars": ["Home", "Work"],
    "event_context": {
        "Robin": "Robin is the neighbor's child. Jordan helps with the school bus twice a week; this is ordinary recurring logistics, not a notable occasion.",
        "Springfield Isotopes": "Springfield Isotopes games appear from a subscribed sports calendar; it is not an outing. Check LOCATION before saying where it is watched.",
    },
    "routine_event_keywords": ["Robin"],
    "appointment_aliases": {"therapy": ["Dr. Lee"], "therapist": ["Dr. Lee"]},
    "prompt_notes": ["The rent reminder is Jordan paying Alex back; the rent itself is paid."],
    "commute": {"city": "Boston", "city_aliases": ["BOS", "the city"],
                "location_keywords": ["Boston, MA", "South Station"], "transit_lines": ["Metro"],
                "depart": "7:05am", "home": "7:40pm", "arrival_stop": "Springfield"},
}


@pytest.fixture(autouse=True)
def jordan():
    profile.configure(PROFILE)

WEATHER = {"locations": [{"location": "Springfield", "temp": 54, "condition": "Overcast"}], "travel_city": None}
EVENTS = [{"time": "9:00am", "title": "Weekly sync", "all_day": False}]

def test_welcome_block_returns_string(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Wednesday. Cold and grey — ideal for staring at a to-do list.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS)
    assert isinstance(result, str)
    assert len(result) > 10

def test_welcome_block_returns_none_on_api_error(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS)
    assert result is None

def test_welcome_block_returns_none_with_no_inputs(mocker):
    result = welcome_block("sk-ant-test", weather_data=None, calendar_events=None)
    assert result is None

def test_welcome_block_passes_travel_city_to_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Heading to Boston, remember to pack patience.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    weather_with_travel = {**WEATHER, "travel_city": "Boston", "travel_confirmed": True}
    welcome_block("sk-ant-test", weather_data=weather_with_travel, calendar_events=EVENTS)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "Boston" in prompt_text


def test_welcome_block_includes_photo_description_in_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Seven years ago in Lisbon, apparently I was somewhere worth remembering.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    photo = (b"fake-image-bytes", {
        "year": "2019", "location": "Lisbon, Portugal", "is_favorite": True,
        "description": "A narrow cobblestone street winding into golden afternoon light.",
    })
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS, photo=photo)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "MEMORY PHOTO" in prompt_text
    assert "Lisbon" in prompt_text
    assert "cobblestone" in prompt_text


def test_welcome_block_includes_nyt_headlines_in_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Senate found something to agree on, which is statistically improbable.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    stories = [
        {"title": "Senate Passes $3T Budget Bill", "abstract": "", "byline": "", "url": "", "thumbnail": None},
        {"title": "Apple Unveils AI Chip", "abstract": "", "byline": "", "url": "", "thumbnail": None},
    ]
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS, nyt_stories=stories)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "NEWS" in prompt_text
    assert "Senate Passes" in prompt_text


def test_welcome_block_passes_calendar_name_notes_to_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Alex has the volunteer shift.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [{"time": "9:15am", "title": "AB- Volunteer at the library", "all_day": False}]
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "AB means Alex" in prompt_text
    assert "Items prefaced AB: belong to Alex" in call_args.kwargs["system"]


def test_welcome_block_does_not_privilege_first_calendar_event(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Dinner has acquired the burden of being today's plot.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [
        {"time": "7:30am", "title": "Get Robin on the bus", "all_day": False},
        {"time": "6:30pm", "title": "Dinner with Maya", "all_day": False},
    ]

    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)

    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    system_text = call_args.kwargs["system"]
    assert "First event:" not in prompt_text
    assert "[CANDIDATE] Dinner with Maya" in prompt_text
    assert prompt_text.index("Dinner with Maya") < prompt_text.index("Get Robin on the bus")
    assert "[ROUTINE] Get Robin on the bus" in prompt_text
    assert "ordinary recurring logistics" in prompt_text
    assert "do not favor an event because it is first or early" in system_text


def test_welcome_block_does_not_assign_other_birthdays_to_recipient(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Someone else gets the candles today.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [{"time": None, "title": "Sarah's Birthday", "all_day": True}]

    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)

    call_args = mock_client.messages.create.call_args
    system_text = call_args.kwargs["system"]
    assert "birthday calendar entry belongs to the person named in its title" in system_text
    assert "Never call it Jordan's birthday" in system_text
    assert "names Jordan Doe" in system_text


def test_welcome_block_includes_authored_tweet_in_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Three years ago I had opinions about shipping; today I have a calendar.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    tweet = {"text": "Shipping beats perfect.", "source": "authored", "year": "2021", "handle": "jordan"}
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS, tweet=tweet)
    prompt_text = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "YOUR TWEET on this day in 2021" in prompt_text
    assert "Shipping beats perfect." in prompt_text


def test_welcome_block_includes_bookmarked_tweet_in_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Someone smarter than me bookmarked a thought worth stealing.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    tweet = {"text": "Local-first is the future.", "source": "bookmarked", "handle": "steipete"}
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS, tweet=tweet)
    prompt_text = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "TWEET YOU BOOKMARKED (by @steipete)" in prompt_text
    assert "Local-first is the future." in prompt_text


def test_welcome_block_excludes_unreliable_message_summary(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Apparently I spent yesterday accumulating timestamps instead of responses.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    messages = {
        "summary": "Yesterday was mostly logistics, a couple of check-ins, and one conversation still politely clearing its throat for a reply.",
        "thread_count": 4,
        "needs_reply_count": 1,
    }
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS, messages=messages)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "MESSAGES" not in prompt_text
    assert "clearing its throat for a reply" not in prompt_text


def test_welcome_uses_reminders_without_weather_or_calendar(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text="One task is due today.")])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    result = welcome_block("test", None, None, reminders={"today": [
        {"title": "Prepare review notes", "list": "Work", "due": "2026-10-08"}
    ]})
    assert result == "One task is due today."
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "[TODAY] Prepare review notes (list: Work; due: 2026-10-08)" in prompt


def test_system_prompt_uses_configured_names_and_notes(mocker):
    call, _ = _prompt_for(mocker, calendar_events=EVENTS)
    system = call["system"]
    assert "for Jordan Doe." in system and "context for Acme" in system
    assert "Never assume Jordan is home" in system
    assert "The rent reminder is Jordan paying Alex back" in system


def test_neutral_defaults_name_nobody(mocker):
    profile.configure(None)
    call, _ = _prompt_for(mocker, calendar_events=EVENTS)
    system = call["system"]
    assert "for the reader." in system and "context for their work" in system
    assert "Items prefaced" not in system and " or names " not in system


def test_costume_preparation_time_is_not_parade_start(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The Halloween parade at 8 starts the day.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    events = [{"time": "8:00am", "title": "Wear costumes for Halloween parade!",
               "calendar": "Home", "all_day": False}]

    assert welcome_block("test", None, events, as_of=date(2026, 10, 25)) is None
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "PREPARATION NOTES" in prompt
    assert "Wear costumes for Halloween parade!" in prompt
    assert "8:00am" not in prompt
    assert events[0]["time"] == "8:00am"  # The calendar row is untouched.


def test_preparation_cue_allows_neutral_wording_and_verified_event_time(mocker):
    client = MagicMock()
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    prep = {"time": "8:00am", "title": "Wear costumes for Halloween parade!", "all_day": False}
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Wear costumes for the parade; its start time is not in this calendar.")]
    )
    assert welcome_block("test", None, [prep]) == "Wear costumes for the parade; its start time is not in this calendar."

    actual = {"time": "10:10am", "title": "Halloween Parade", "all_day": False}
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The Halloween parade starts at 10:10.")]
    )
    assert welcome_block("test", None, [prep, actual]) == "The Halloween parade starts at 10:10."


def test_legitimate_calendar_event_time_remains_usable(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The team meeting starts at 9.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    assert welcome_block("test", None, [{"time": "9:00am", "title": "Team meeting",
                                         "all_day": False}]) == "The team meeting starts at 9."


def test_financial_reminders_cannot_become_payment_events(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The rent reimbursement and store card payment land today.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    reminders = {
        "overdue": [{"title": "$900 Rent", "due": "2026-10-01", "list": "Personal"}],
        "today": [{"title": "Store card due the 2nd", "due": "2026-10-25", "list": "Bills"},
                  {"title": "Review orchestra calendar", "due": "2026-10-25", "list": "Home"}],
    }

    assert welcome_block("test", None, None, reminders=reminders, as_of=date(2026, 10, 25)) is None
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "[TODAY] Review orchestra calendar" in prompt
    assert "Store card" not in prompt
    assert "$900 Rent" not in prompt
    assert reminders["today"][0]["due"] == "2026-10-25"  # The reminder row is untouched.


@pytest.mark.parametrize("claim", [
    "The store card is due today.",
    "The rent is unpaid.",
    "The store card payment posts tomorrow.",
])
def test_unsupported_financial_deadline_or_status_is_rejected(mocker, claim):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text=claim)])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    assert welcome_block("test", WEATHER, EVENTS) is None


@pytest.mark.parametrize("neutral", [
    "The store card reminder is on today's list.",
    "The store card reminder is due today.",
])
def test_neutral_financial_reminder_wording_is_allowed(mocker, neutral):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text=neutral)])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    assert welcome_block("test", WEATHER, EVENTS) == neutral


def test_configured_appointment_alias_substantiates_therapy(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text="Therapy anchors the afternoon.")])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    session = [{"time": "3:00pm", "title": "Dr. Lee and Jordan's session", "all_day": False}]
    assert welcome_block("test", None, session) == "Therapy anchors the afternoon."
    profile.configure({**PROFILE, "appointment_aliases": {}})
    assert welcome_block("test", None, session) is None


# --- Location, home claims, paragraphs, reminder cooldown ---

COMMUTE_DAY = [
    {"time": "12:30pm", "end_time": "4:30pm", "title": "Example Store - UPS", "calendar": "Parcel", "all_day": False},
    {"time": "7:00pm", "title": "Shelbyville @ Springfield Isotopes", "calendar": "Springfield Isotopes", "all_day": False},
    {"time": None, "title": "JD: BOS", "calendar": "Home", "all_day": True},
]


def _prompt_for(mocker, **kwargs):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text="A city day.\n\nQuiet evening.")])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    result = welcome_block("sk-ant-test", weather_data=WEATHER, **kwargs)
    return client.messages.create.call_args.kwargs, result


def test_prompt_states_away_location_and_drops_day_marker_from_events(mocker):
    call, _ = _prompt_for(mocker, calendar_events=COMMUTE_DAY)
    prompt = call["messages"][0]["content"]
    assert "LOCATION: Jordan is away in Boston today" in prompt
    assert "7:05am" not in prompt and "7:40pm" not in prompt  # usual commute times stay out
    assert "] JD: BOS (" not in prompt
    assert "Never assume Jordan is home" in call["system"]
    assert "2 or 3 short paragraphs" in call["system"]
    assert call["max_tokens"] >= 300


def test_prompt_states_unknown_location(mocker):
    call, _ = _prompt_for(mocker, calendar_events=EVENTS)
    assert "LOCATION: unknown" in call["messages"][0]["content"]


@pytest.mark.parametrize("text", [
    "Worth tackling the gutter check while you're home expecting the package.",
    "Tonight's game offers a wind-down from home.",
    "The game at 7 is best watched at home.",
    "A good day to putter around the house.",
    "You're home all day, so the delivery is covered.",
])
def test_home_claims_rejected_on_away_day(text):
    assert validate_opening(text, calendar_events=COMMUTE_DAY) is None


@pytest.mark.parametrize("text", [
    "A city day, and back home in the evening.",
    "The order lands while you're in the city; you'll find it when you get home tonight.",
    "You'll be back at home after the first pitch.",
])
def test_return_home_language_allowed_on_away_day(text):
    assert validate_opening(text, calendar_events=COMMUTE_DAY) == text


def test_home_claims_allowed_on_home_day_and_presence_rejected_when_unknown():
    text = "Worth tackling the gutter check while you're home expecting the package."
    wfh = [{"time": None, "title": "JD: WFH", "calendar": "Work", "all_day": True}]
    assert validate_opening(text, calendar_events=wfh) == text
    assert validate_opening(text, calendar_events=EVENTS) is None
    # Ordinary uses of "home" are fine when the location is simply unknown.
    assert validate_opening("Dinner at home sounds right.", calendar_events=EVENTS) == "Dinner at home sounds right."


def test_paragraph_breaks_are_kept_and_normalized():
    raw = "  First thought here.\n\n\nSecond thought.\nThird thought.  "
    assert validate_opening(raw, calendar_events=EVENTS) == "First thought here.\n\nSecond thought.\n\nThird thought."


def test_cooldown_reminders_kept_out_of_prompt(mocker):
    reminders = {"today": [], "upcoming": [],
                 "overdue": [{"title": "Clean the gutters!", "due": "2026-10-28", "list": "Home"},
                             {"title": "Return library books", "due": "2026-11-05", "list": "Personal"}]}
    call, _ = _prompt_for(mocker, calendar_events=EVENTS, reminders=reminders, as_of=date(2026, 11, 11),
                          mention_history={"return library books": "2026-11-09"})
    prompt = call["messages"][0]["content"]
    assert "gutters" in prompt and "library" not in prompt
    call, _ = _prompt_for(mocker, calendar_events=EVENTS, reminders=reminders, as_of=date(2026, 11, 11),
                          mention_history={"clean the gutters!": "2026-11-10"})
    prompt = call["messages"][0]["content"]
    assert "gutters" not in prompt and "library" in prompt


def test_prompt_carries_no_commute_logistics(mocker):
    call, _ = _prompt_for(mocker, calendar_events=COMMUTE_DAY)
    prompt = call["messages"][0]["content"]
    assert "EVENING TIMING" not in prompt
    assert "LOCATION: Jordan is away in Boston today" in prompt
    assert "Never mention the commute" in call["system"]


@pytest.mark.parametrize("text", [
    "A city day: out on the early bus and back home around 7:40.",
    "The Metro gets you in before the first meeting.",
    "Your ride home lands in Springfield before the game.",
    "Leave time for the commute after the late meeting.",
    "Catch the train after the review.",
])
def test_commute_mentions_rejected(text):
    assert validate_opening(text, calendar_events=COMMUTE_DAY) is None


def test_school_bus_is_not_a_commute_mention():
    text = "The school bus run is the only fixed point this morning."
    assert validate_opening(text, calendar_events=EVENTS) == text


@pytest.mark.parametrize("text", [
    "The gutter check has been sitting since late October.",
    "The gutter check is well overdue.",
    "It's been a while since the gutter reminder came through.",
])
def test_reminder_nagging_rejected(text):
    assert validate_opening(text, calendar_events=EVENTS) is None


def test_em_dashes_become_commas_and_overdue_dates_hidden(mocker):
    assert validate_opening("A quiet day—nothing pressing.", calendar_events=EVENTS) == "A quiet day, nothing pressing."
    reminders = {"today": [], "upcoming": [],
                 "overdue": [{"title": "Clean the gutters!", "due": "2026-10-20", "list": "Home"}]}
    call, _ = _prompt_for(mocker, calendar_events=EVENTS, reminders=reminders, as_of=date(2026, 11, 11))
    prompt = call["messages"][0]["content"]
    assert "Clean the gutters! (list: Home; overdue)" in prompt
    assert "2026-10-20" not in prompt


def test_rejected_draft_is_retried_then_omitted(mocker):
    client = MagicMock()
    client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text="Handle the gutter check while you're home.")]),
        MagicMock(content=[MagicMock(text="A city day.\n\nThe game starts before you're back.")]),
    ]
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    assert welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=COMMUTE_DAY) == \
        "A city day.\n\nThe game starts before you're back."
    assert client.messages.create.call_count == 2
    client.messages.create.side_effect = None
    client.messages.create.return_value = MagicMock(content=[MagicMock(text="Relax at home today.")])
    client.messages.create.call_count = 0
    assert welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=COMMUTE_DAY) is None
    assert client.messages.create.call_count == 3


def test_away_day_delivery_line_omits_window(mocker):
    call, _ = _prompt_for(mocker, calendar_events=COMMUTE_DAY)
    prompt = call["messages"][0]["content"]
    assert "Example Store - UPS (arrives today while Jordan is out" in prompt
    assert "12:30pm–4:30pm" not in prompt


def test_later_return_home_phrasing_allowed_on_away_day():
    text = "The gutter check is on the list for when you're home."
    assert validate_opening(text, calendar_events=COMMUTE_DAY) == text


def test_bare_travel_block_is_not_an_editorial_event_and_meetings_rule_present(mocker):
    events = COMMUTE_DAY + [{"time": "4:00pm", "title": "Travel", "calendar": "Work", "all_day": False},
                            {"time": "10:30am", "title": "Platform Core Group: Weekly", "calendar": "Work", "all_day": False}]
    call, _ = _prompt_for(mocker, calendar_events=events)
    prompt = call["messages"][0]["content"]
    assert "] Travel (" not in prompt
    assert "Platform Core Group" in prompt
    assert "never enumerate meetings" in call["system"]


def test_schedule_recital_and_waiting_nag_rejected():
    recital = "Meetings at 9:15, 10:30 and 2:00 fill the day."
    assert validate_opening(recital, calendar_events=EVENTS) is None
    assert validate_opening("Standup at 9:15 sets the tone.", calendar_events=EVENTS) is not None
    assert validate_opening("The gutter check is overdue and waiting for attention.", calendar_events=EVENTS) is None


@pytest.mark.parametrize("text", [
    "The kids' evening means the usual shuttling around.",
    "A shuttle run to practice after dinner.",
])
def test_shuttling_counts_as_commute_talk(text):
    assert validate_opening(text, calendar_events=EVENTS) is None


@pytest.mark.parametrize("text", [
    "Since your location is unknown, check the Packages section.",
    "Your location isn't clear today, so plan loosely.",
    "With an unknown location, keep the evening open.",
    "It's not clear where you'll be this afternoon.",
])
def test_unknown_location_is_never_echoed(text):
    assert validate_opening(text, calendar_events=EVENTS) is None


def test_ordinary_location_words_still_allowed():
    text = "The play's location is the elementary school, so it's close by."
    assert validate_opening(text, calendar_events=EVENTS) == text


def test_prompt_tells_model_not_to_echo_unknown_location(mocker):
    call, _ = _prompt_for(mocker, calendar_events=EVENTS)
    assert "never say that the location is unknown" in call["system"]

# --- Busy days: parts of day, not clock times, and logged rejection reasons ---

BUSY_DAY = [
    {"time": "9:40am", "title": "Dentist appointment", "calendar": "Home", "all_day": False},
    {"time": "11:00am", "title": "School play", "calendar": "Home", "all_day": False},
    {"time": "12:00pm", "title": "Lunch with Alex", "calendar": "Home", "all_day": False},
    {"time": "1:00pm", "title": "Memorial service", "calendar": "Home", "all_day": False},
    {"time": "4:00pm", "title": "Potluck dinner", "calendar": "Home", "all_day": False},
]


def test_prompt_gives_parts_of_day_instead_of_clock_times(mocker):
    call, _ = _prompt_for(mocker, calendar_events=BUSY_DAY)
    prompt = call["messages"][0]["content"]
    for label in ("9:40am", "11:00am", "12:00pm", "1:00pm", "4:00pm"):
        assert label not in prompt
    assert "Dentist appointment (morning;" in prompt
    assert "Lunch with Alex (midday;" in prompt
    assert "Potluck dinner (afternoon;" in prompt


@pytest.mark.parametrize("label, part", [
    ("12:30am", "overnight"), ("6:00am", "morning"), ("11:59am", "morning"), ("12:00pm", "midday"),
    ("1:00pm", "afternoon"), ("5:00pm", "evening"), ("11 pm", "evening"), (None, "time unknown"),
])
def test_part_of_day_buckets(label, part):
    from modules.welcome import _part_of_day
    assert _part_of_day(label) == part


def test_rejected_drafts_are_logged_by_reason_without_their_text(mocker, caplog):
    recital = "Dentist at 9:40am, the play at 11:00am, lunch at 12:00pm."
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text=recital)])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    with caplog.at_level("INFO", logger="modules.welcome"):
        assert welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=BUSY_DAY) is None
    assert client.messages.create.call_count == 3
    assert caplog.text.count("rejected: schedule_recital") == 3
    assert "all 3 drafts were rejected" in caplog.text
    assert "Dentist" not in caplog.text


INVENTED_REMINDERS = {"today": [{"title": "ask Dr. Doshi for more Vyvanse", "due": "2026-11-16", "list": "Home"}],
                      "overdue": [{"title": "Check Salt", "due": "2026-11-13", "list": "Home"},
                                  {"title": "Check home heating oil!", "due": "2026-10-20", "list": "Home"}],
                      "upcoming": []}


@pytest.mark.parametrize("text", [
    "The gutter check needs doing when you're back.",
    "The gutter check is on the list.",
    "Raking the leaves is on your list.",
])
def test_reminder_not_in_the_input_is_rejected(text):
    assert validate_opening(text, calendar_events=EVENTS, reminders=INVENTED_REMINDERS) is None


@pytest.mark.parametrize("text", [
    "Dr. Doshi's office is on the list for a Vyvanse request.",
    "The salt check is on the list.",
    "The heating oil check is on the list.",
])
def test_real_reminders_named_on_the_list_pass(text):
    assert validate_opening(text, calendar_events=EVENTS, reminders=INVENTED_REMINDERS) == text


def test_list_claims_unchecked_without_reminders_input():
    text = "The gutter check is on the list."
    assert validate_opening(text, calendar_events=EVENTS) == text


def test_prompt_has_no_concrete_reminder_example(mocker):
    call, _ = _prompt_for(mocker, calendar_events=EVENTS)
    assert "gutter" not in call["system"]


MONDAY_REMINDERS = {
    "overdue": [{"title": "Check Salt", "due": "2026-11-13", "list": "Home"},
                {"title": "Talk to Alex about Thursday's schedule", "due": "2026-11-14", "list": "Home"},
                {"title": "Recycling Night", "due": "2026-11-15", "list": "Home"},
                {"title": "Do the calendars", "due": "2026-11-15", "list": "Home"}],
    "today": [{"title": "ask Dr. Lee for more Ritalin", "due": "2026-11-16", "list": "Home"},
              {"title": "BMW Oil change", "due": "2026-11-16", "list": "Home"},
              {"title": "Check Propane", "due": "2026-11-16", "list": "Home"}],
    "upcoming": [{"title": "Ritalin refill script", "due": "2026-11-17", "list": "Home"}],
}
MONDAY_EVENTS = [{"time": "11:15am", "title": "Design review", "calendar": "Home", "all_day": False},
                 {"time": "5:00pm", "title": "Alex and Sam at practice", "calendar": "Home", "all_day": False}]


def test_more_than_one_reminder_is_rejected():
    text = ("Asking Dr. Lee for more Ritalin is on the list, and the BMW oil change is on the list. "
            "Check Propane is also on the list.")
    assert validate_opening(text, calendar_events=MONDAY_EVENTS, reminders=MONDAY_REMINDERS) is None


@pytest.mark.parametrize("text", [
    "Asking Dr. Lee for more Ritalin is on the list.",  # "Ritalin" is shared, "Lee" names one
    "The design review is the one fixed point, and the propane check is on the list.",
    "Alex and Sam have practice this evening; the salt check is on the list.",  # Alex is an event word
    "It's on your calendar: a design review late morning.",  # "calendar" is not a reminder mention
])
def test_one_reminder_passes(text):
    assert validate_opening(text, calendar_events=MONDAY_EVENTS, reminders=MONDAY_REMINDERS) == text


@pytest.mark.parametrize("text", [
    "An evening event with Jack and James is on your calendar, though return timing isn't set.",
    "The return time is not given, so keep the evening loose.",
    "With no return time listed, the game is a maybe.",
    "Your return time is unknown.",
    "Evening brings Jack and James, though your return time isn't nailed down yet.",
    "The return timing is still not pinned down.",
])
def test_return_time_echo_is_rejected(text):
    assert validate_opening(text, calendar_events=EVENTS) is None


def test_ordinary_return_language_passes():
    text = "You'll be back home in time for dinner."
    assert validate_opening(text, calendar_events=EVENTS) == text


def test_prompt_offers_a_single_reminder_candidate(mocker):
    call, _ = _prompt_for(mocker, calendar_events=MONDAY_EVENTS, reminders=MONDAY_REMINDERS,
                          as_of=date(2026, 11, 16))
    prompt = call["messages"][0]["content"]
    assert "REMINDER (the only one" in prompt
    assert prompt.count("(list: ") == 1


def _simple_prompt(mocker, events, reminders=None):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="A quiet day.")])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events, reminders=reminders,
                  as_of=date(2026, 3, 2))
    return mock_client.messages.create.call_args.kwargs["messages"][0]["content"]


def test_city_claims_need_a_day_marker():
    meetings = [{"time": "10:00am", "title": "Design review", "calendar": "Work", "all_day": False,
                 "location": "South Station, Boston, MA"}]
    for text in ("You're in Boston today, with a design review.", "An office day with one review.",
                 "You're in the city today.", "A meeting-heavy BOS day ahead."):
        assert validate_opening(text, calendar_events=meetings) is None, text
    marked = meetings + [{"time": None, "title": "JD: BOS", "calendar": "Home", "all_day": True}]
    assert validate_opening("You're in Boston today, with a design review.", calendar_events=marked)
    # Naming another town for an event is fine.
    therapy = [{"time": "5:00pm", "title": "OT for Kid", "calendar": "Home", "all_day": False, "location": "Shelbyville"}]
    assert validate_opening("The evening has OT in Shelbyville.", calendar_events=therapy)


def test_hedging_is_rejected():
    for text in ("A review somewhere in the middle of the day.", "The specifics aren't clear from here.",
                 "It seems a light day."):
        assert validate_opening(text, calendar_events=EVENTS) is None, text


def test_event_place_reaches_prompt_but_not_virtual_or_city_rooms(mocker):
    events = [
        {"time": "5:00pm", "title": "OT for Kid", "calendar": "Home", "all_day": False,
         "location": "Shelbyville Therapy\n12 Elm St, Shelbyville"},
        {"time": "10:00am", "title": "Design review", "calendar": "Work", "all_day": False,
         "location": "Microsoft Teams Meeting"},
        {"time": "11:00am", "title": "Planning", "calendar": "Work", "all_day": False,
         "location": "4th floor, South Station, Boston, MA"},
    ]
    prompt = _simple_prompt(mocker, events)
    assert "place: Shelbyville Therapy" in prompt
    assert "Teams" not in prompt and "South Station" not in prompt
    assert "LOCATION: unknown" in prompt


def test_medical_reminders_are_never_offered_to_the_opening(mocker):
    reminders = {"today": [{"title": "Ask Dr. Example for a refill", "list": "Todo"},
                           {"title": "Get a veggie tray", "list": "Todo"}], "overdue": [], "upcoming": []}
    prompt = _simple_prompt(mocker, EVENTS, reminders)
    assert "veggie tray" in prompt and "Dr. Example" not in prompt


def test_prompt_forbids_assuming_away_and_hedging():
    from modules.welcome import system_prompt
    text = system_prompt()
    assert "Never assume Jordan is away either" in text
    assert "never hedge" in text
    assert "office day" not in text.split("Work meetings are context")[1]


def test_retries_name_the_rejection_and_rejected_drafts_stay_private(mocker, tmp_path, caplog):
    client = MagicMock()
    client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text="An office day in Boston with one review.")]),
        MagicMock(content=[MagicMock(text="A workday with one review.")]),
    ]
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    path = tmp_path / "state" / "rejections.jsonl"
    with caplog.at_level("INFO"):
        result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS,
                               rejections_path=path)
    assert result == "A workday with one review."
    first, second = (c.kwargs["messages"][0]["content"] for c in client.messages.create.call_args_list)
    assert "REWRITE NOTE" not in first
    assert "REWRITE NOTE" in second and "without any place" in second
    saved = path.read_text()
    assert "city_claim" in saved and "office day in Boston" in saved
    assert (path.stat().st_mode & 0o777) == 0o600
    assert "office day in Boston" not in caplog.text and "city_claim" in caplog.text


def test_unavailable_calendar_is_not_called_empty(mocker):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text="A quiet day.")])
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=None)
    assert "CALENDAR: unavailable" in client.messages.create.call_args.kwargs["messages"][0]["content"]


@pytest.mark.parametrize("photo_place", ["", "Lisbon, Portugal"])
def test_memory_photo_does_not_clobber_the_location_fact(mocker, tmp_path, photo_place):
    # A memory photo's place once overwrote the day's LOCATION, so every guard saw
    # "unknown" and rejected a correct "You're in Boston today" on a marked city day.
    client = MagicMock()
    client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text="It seems a city day.")]),
        MagicMock(content=[MagicMock(text="You're in Boston today, with one review.")]),
    ]
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=client)
    marked = EVENTS + [{"time": None, "title": "JD: BOS", "calendar": "Home", "all_day": True}]
    photo = (b"img", {"year": "2019", "location": photo_place, "description": "A street."})
    path = tmp_path / "rejections.jsonl"
    result = welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=marked, photo=photo,
                           rejections_path=path)
    assert result == "You're in Boston today, with one review."
    assert '"location": "away"' in path.read_text()
