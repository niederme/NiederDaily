import pytest
from datetime import date
from unittest.mock import MagicMock

from modules.welcome import _is_recipient_birthday, welcome_block

WEATHER = {"locations": [{"location": "Warwick, NY", "temp": 54, "condition": "Overcast"}], "travel_city": None}
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
        content=[MagicMock(text="Heading to NYC — remember to pack patience.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    weather_with_travel = {**WEATHER, "travel_city": "New York"}
    welcome_block("sk-ant-test", weather_data=weather_with_travel, calendar_events=EVENTS)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "New York" in prompt_text


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
        content=[MagicMock(text="Danielle is apparently what DC means, which does improve the odds of understanding my own schedule.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [{"time": "9:15am", "title": "DC- Volunteer for Traveling Trunks: James", "all_day": False}]
    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)
    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "DC means Danielle" in prompt_text


def test_welcome_block_does_not_privilege_first_calendar_event(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Dinner has acquired the burden of being today's plot.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [
        {"time": "7:30am", "title": "Get Alaia on the bus", "all_day": False},
        {"time": "6:30pm", "title": "Dinner with Maya", "all_day": False},
    ]

    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)

    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    system_text = call_args.kwargs["system"]
    assert "First event:" not in prompt_text
    assert "[CANDIDATE] Dinner with Maya" in prompt_text
    assert prompt_text.index("Dinner with Maya") < prompt_text.index("Get Alaia on the bus")
    assert "[ROUTINE] Get Alaia on the bus" in prompt_text
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
    assert "Never call it John's birthday" in system_text
    assert "names John Niedermeyer" in system_text


def test_welcome_block_includes_authored_tweet_in_prompt(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Three years ago I had opinions about shipping; today I have a calendar.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    tweet = {"text": "Shipping beats perfect.", "source": "authored", "year": "2021", "handle": "john"}
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


def test_welcome_block_includes_message_summary_in_prompt(mocker):
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
    assert "MESSAGES" in prompt_text
    assert "clearing its throat for a reply" in prompt_text


def test_welcome_block_resolves_job_shorthand_to_jobeth_leon(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Jobeth gets the candles today, which is a fine excuse for cake by proxy.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    events = [{"time": None, "title": "JoB's birthday!", "all_day": True}]

    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=events)

    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    system_text = call_args.kwargs["system"]
    assert "JoB means Jobeth Leon" in prompt_text
    assert "JN means John" not in prompt_text
    assert "shorthand in an event title never mean John" in system_text


def test_welcome_block_forbids_reasoning_out_loud(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The keynote arrives, and with it the annual urge to buy nothing.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)

    welcome_block("sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS)

    system_text = mock_client.messages.create.call_args.kwargs["system"]
    assert "Return only the greeting sentence" in system_text
    assert "Never explain your choice" in system_text


def _birthday_prompt(mocker, birthday, as_of):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Another lap completed, and the calendar has the nerve to look unimpressed.")]
    )
    mocker.patch("modules.welcome.anthropic.Anthropic", return_value=mock_client)
    welcome_block(
        "sk-ant-test", weather_data=WEATHER, calendar_events=EVENTS,
        recipient_birthday=birthday, as_of=as_of,
    )
    return mock_client.messages.create.call_args


def test_welcome_block_flags_recipients_own_birthday(mocker):
    call_args = _birthday_prompt(mocker, "03-14", date(2026, 3, 14))
    prompt_text = call_args.kwargs["messages"][0]["content"]
    system_text = call_args.kwargs["system"]
    assert "TODAY IS JOHN'S OWN BIRTHDAY" in prompt_text
    assert "the recipient's own, not a third party's" in prompt_text
    assert "or the context includes the line TODAY IS JOHN'S OWN BIRTHDAY" in system_text


def test_welcome_block_ignores_birth_year_when_matching(mocker):
    prompt_text = _birthday_prompt(mocker, "1977-03-14", date(2026, 3, 14)).kwargs["messages"][0]["content"]
    assert "TODAY IS JOHN'S OWN BIRTHDAY" in prompt_text
    assert "1977" not in prompt_text


def test_welcome_block_omits_birthday_flag_on_other_days(mocker):
    prompt_text = _birthday_prompt(mocker, "03-14", date(2026, 3, 15)).kwargs["messages"][0]["content"]
    assert "OWN BIRTHDAY" not in prompt_text


@pytest.mark.parametrize("birthday", [None, "", "not-a-date", "1977", "xx-yy"])
def test_is_recipient_birthday_rejects_unusable_values(birthday):
    assert _is_recipient_birthday(birthday, date(2026, 3, 14)) is False
