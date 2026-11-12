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
    assert validate_opening("A city day—nothing pressing.", calendar_events=EVENTS) == "A city day, nothing pressing."
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
