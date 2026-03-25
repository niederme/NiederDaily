import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from modules.reminders import reminders_block


def _make_stdout(items):
    """Build fake osascript stdout from list of (title, date_or_str) tuples."""
    lines = []
    for title, due in items:
        due_str = due.isoformat() if isinstance(due, date) else due
        lines.append(f"{title}|{due_str}|false")
    return "\n".join(lines)


def test_overdue_items(mocker):
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=8)

    stdout = _make_stdout([
        ("Overdue task", yesterday),
        ("Very overdue", last_week),
    ])

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout
    mocker.patch("modules.reminders.subprocess.run", return_value=mock_result)

    result = reminders_block([])
    assert result is not None
    assert len(result["overdue"]) == 2
    assert result["today"] == []
    assert result["upcoming"] == []


def test_today_items(mocker):
    today = date.today()

    stdout = _make_stdout([
        ("Today task", today),
    ])

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout
    mocker.patch("modules.reminders.subprocess.run", return_value=mock_result)

    result = reminders_block([])
    assert result is not None
    assert result["today"] == [{"title": "Today task", "due": today.isoformat()}]
    assert result["overdue"] == []
    assert result["upcoming"] == []


def test_upcoming_items(mocker):
    today = date.today()
    in_3_days = today + timedelta(days=3)
    in_6_days = today + timedelta(days=6)

    stdout = _make_stdout([
        ("Upcoming A", in_3_days),
        ("Upcoming B", in_6_days),
    ])

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout
    mocker.patch("modules.reminders.subprocess.run", return_value=mock_result)

    result = reminders_block([])
    assert result is not None
    assert len(result["upcoming"]) == 2
    assert result["overdue"] == []
    assert result["today"] == []


def test_nonzero_returncode_returns_none(mocker):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mocker.patch("modules.reminders.subprocess.run", return_value=mock_result)

    result = reminders_block([])
    assert result is None


def test_upcoming_capped_at_5(mocker):
    today = date.today()
    # 7 items all within the next 7 days
    items = [(f"Task {i}", today + timedelta(days=i + 1)) for i in range(7)]
    stdout = _make_stdout(items)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout
    mocker.patch("modules.reminders.subprocess.run", return_value=mock_result)

    result = reminders_block([])
    assert result is not None
    assert len(result["upcoming"]) == 5
