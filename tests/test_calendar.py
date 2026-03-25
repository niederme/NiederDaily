import pytest
from unittest.mock import MagicMock

from modules.calendar import calendar_block

APPLESCRIPT_OUTPUT = """9:00am|Weekly sync|Zoom
12:00pm|Lunch with Sarah|The Landmark Inn
|Phil's birthday|
"""

def test_calendar_block_parses_events(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout=APPLESCRIPT_OUTPUT)
    result = calendar_block()
    assert len(result) == 3
    assert result[0]["title"] == "Weekly sync"
    assert result[0]["time"] == "9:00am"
    assert result[0]["location"] == "Zoom"
    assert result[0]["all_day"] is False
    assert result[2]["all_day"] is True
    assert result[2]["title"] == "Phil's birthday"

def test_calendar_block_returns_none_on_applescript_error(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = calendar_block()
    assert result is None

def test_calendar_block_returns_empty_list_when_no_events(mocker):
    mock_run = mocker.patch("modules.calendar.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="\n")
    result = calendar_block()
    assert result == []
