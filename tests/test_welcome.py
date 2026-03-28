import pytest
from unittest.mock import MagicMock

from modules.welcome import welcome_block

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
