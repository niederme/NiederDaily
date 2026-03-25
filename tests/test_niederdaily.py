import pytest
from unittest.mock import MagicMock, patch

def test_modules_run_in_correct_order(mocker):
    """weather and calendar must run before welcome."""
    call_order = []

    mocker.patch("modules.weather.weather_block", side_effect=lambda *a, **kw: call_order.append("weather") or {"locations": [], "travel_city": None})
    mocker.patch("modules.calendar.calendar_block", side_effect=lambda: call_order.append("calendar") or [])
    mocker.patch("modules.welcome.welcome_block", side_effect=lambda *a, **kw: call_order.append("welcome") or "Hello")
    mocker.patch("modules.reminders.reminders_block", return_value=None)
    mocker.patch("modules.messages.messages_block", return_value=None)
    mocker.patch("modules.photo.photo_block", return_value=None)
    mocker.patch("modules.nyt.nyt_block", return_value=None)
    mocker.patch("renderer.render_email", return_value=MagicMock())
    mocker.patch("sender.send_email", return_value=True)
    mocker.patch("config.load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "k", "anthropic_api_key": "k2", "reminders_lists": []
    })

    import niederdaily
    niederdaily.run()

    assert call_order.index("weather") < call_order.index("welcome")
    assert call_order.index("calendar") < call_order.index("welcome")

def test_failed_module_does_not_crash_run(mocker):
    mocker.patch("modules.weather.weather_block", side_effect=Exception("boom"))
    mocker.patch("modules.calendar.calendar_block", return_value=None)
    mocker.patch("modules.welcome.welcome_block", return_value=None)
    mocker.patch("modules.reminders.reminders_block", return_value=None)
    mocker.patch("modules.messages.messages_block", return_value=None)
    mocker.patch("modules.photo.photo_block", return_value=None)
    mocker.patch("modules.nyt.nyt_block", return_value=None)
    mocker.patch("renderer.render_email", return_value=MagicMock())
    mocker.patch("sender.send_email", return_value=True)
    mocker.patch("config.load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "k", "anthropic_api_key": "k2", "reminders_lists": []
    })

    import niederdaily
    # Should not raise
    niederdaily.run()
