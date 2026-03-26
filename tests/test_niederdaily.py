import importlib
import types
from unittest.mock import MagicMock

def test_modules_run_in_correct_order(mocker):
    """weather and calendar must run before welcome."""
    call_order = []

    mocker.patch("modules.weather.weather_block", side_effect=lambda *a, **kw: call_order.append("weather") or {"locations": [], "travel_city": None})
    mocker.patch("modules.calendar.calendar_block", side_effect=lambda *a, **kw: call_order.append("calendar") or [])
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
    importlib.reload(niederdaily)
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
    importlib.reload(niederdaily)
    # Should not raise
    niederdaily.run()


def test_preflight_passes_with_optional_warnings(mocker, tmp_path, capsys):
    import niederdaily

    app = importlib.reload(niederdaily)
    config_dir = tmp_path / ".niederdaily"
    config_dir.mkdir()
    (config_dir / "client_secret.json").write_text("{}")

    mocker.patch.object(app.cfg, "load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "nyt",
        "anthropic_api_key": "anthropic",
        "reminders_lists": [],
        "calendars": ["Personal"],
    })
    mocker.patch.object(app, "calendar_access_granted", return_value=True)
    mocker.patch.object(app, "reminders_access_granted", return_value=True)
    mocker.patch.object(app, "photo_access_granted", return_value=False)
    mocker.patch.object(app, "calendar_block", return_value=None)
    mocker.patch.object(app, "reminders_block", return_value=None)
    mocker.patch("modules.messages.DB_PATH", str(tmp_path / "missing-chat.db"))
    mocker.patch.dict("sys.modules", {
        "AddressBook": types.SimpleNamespace(
            ABAddressBook=types.SimpleNamespace(sharedAddressBook=lambda: object())
        ),
        "anthropic": types.SimpleNamespace(
            Anthropic=lambda api_key: types.SimpleNamespace(
                messages=types.SimpleNamespace(create=lambda **kwargs: MagicMock())
            )
        ),
    })
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    mocker.patch("sender.get_gmail_service", return_value=object())
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mocker.patch("requests.get", return_value=mock_response)

    app.preflight()

    out = capsys.readouterr().out
    assert "! Calendar: unavailable" in out
    assert "! Reminders: unavailable" in out
    assert "! Photos: unavailable" in out
    assert "! Messages: chat.db not accessible" in out
    assert "✓ Gmail (OAuth token valid)" in out
    assert "Preflight degraded. Scheduling is safe" in out
    assert "Blocking checks failed" not in out


def test_preflight_blocks_when_gmail_auth_fails(mocker, tmp_path, capsys):
    import niederdaily

    app = importlib.reload(niederdaily)
    config_dir = tmp_path / ".niederdaily"
    config_dir.mkdir()
    (config_dir / "client_secret.json").write_text("{}")
    chat_db = tmp_path / "chat.db"
    chat_db.write_text("")

    mocker.patch.object(app.cfg, "load_config", return_value={
        "recipient_email": "me@example.com",
        "default_location": {"name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607},
        "nyt_api_key": "nyt",
        "anthropic_api_key": "anthropic",
        "reminders_lists": [],
        "calendars": ["Personal"],
    })
    mocker.patch.object(app, "calendar_access_granted", return_value=True)
    mocker.patch.object(app, "reminders_access_granted", return_value=True)
    mocker.patch.object(app, "photo_access_granted", return_value=True)
    mocker.patch.object(app, "calendar_block", return_value=[])
    mocker.patch.object(app, "reminders_block", return_value={"overdue": [], "today": [], "upcoming": []})
    mocker.patch("modules.messages.DB_PATH", str(chat_db))
    mocker.patch.dict("sys.modules", {
        "AddressBook": types.SimpleNamespace(
            ABAddressBook=types.SimpleNamespace(sharedAddressBook=lambda: object())
        ),
        "anthropic": types.SimpleNamespace(
            Anthropic=lambda api_key: types.SimpleNamespace(
                messages=types.SimpleNamespace(create=lambda **kwargs: MagicMock())
            )
        ),
    })
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    mocker.patch("sender.get_gmail_service", side_effect=RuntimeError("token revoked"))
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mocker.patch("requests.get", return_value=mock_response)

    app.preflight()

    out = capsys.readouterr().out
    assert "✗ Gmail OAuth: token revoked" in out
    assert "Blocking checks failed. Fix the issues above before scheduling." in out
