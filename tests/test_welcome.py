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
