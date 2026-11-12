from datetime import date
import importlib
import json
from unittest.mock import MagicMock

from modules import opening_history as oh

TODAY = date(2026, 11, 11)
REMINDERS = {
    "today": [{"title": "Quarterly report review", "due": "2026-11-11", "list": "Work"}],
    "overdue": [
        {"title": "Clean the gutters!", "due": "2026-10-28", "list": "Home"},
        {"title": "Replace furnace filter", "due": "2026-11-01", "list": "Home"},
        {"title": "Return library books", "due": "2026-11-05", "list": "Personal"},
    ],
    "upcoming": [{"title": "Rake leaves", "due": "2026-11-13", "list": "Home"}],
}


def test_missing_and_corrupt_files_are_empty(tmp_path):
    assert oh.load(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert oh.load(bad) == {}
    bad.write_text(json.dumps(["list"]))
    assert oh.load(bad) == {}
    bad.write_text(json.dumps({"a": "not-a-date", "b": "2026-11-01"}))
    assert oh.load(bad) == {"b": "2026-11-01"}


def test_record_is_atomic_merge_and_private(tmp_path):
    path = tmp_path / "state" / "opening_mentions.json"
    assert oh.record(path, ["Clean the gutters!"], date(2026, 11, 1))
    assert oh.record(path, ["Rake  Leaves"], TODAY)
    data = json.loads(path.read_text())
    assert data == {"clean the gutters!": "2026-11-01", "rake leaves": "2026-11-11"}
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert [p.name for p in path.parent.iterdir()] == ["opening_mentions.json"]


def test_record_failure_returns_false(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert oh.record(blocker / "sub" / "h.json", ["x"], TODAY) is False


def test_cooldown_drops_recent_overdue_and_upcoming_but_not_today():
    history = {"clean the gutters!": "2026-11-08", "rake leaves": "2026-11-10",
               "quarterly report review": "2026-11-10"}
    shown = oh.filter_for_prompt(REMINDERS, history, TODAY)
    assert [r["title"] for r in shown["today"]] == ["Quarterly report review"]
    assert "Clean the gutters!" not in [r["title"] for r in shown["overdue"]]
    assert shown["upcoming"] == []


def test_one_overdue_per_day_rotating_least_recently_mentioned():
    history = {"clean the gutters!": "2026-10-20", "replace furnace filter": "2026-11-01"}
    shown = oh.filter_for_prompt(REMINDERS, history, TODAY)
    # Never-mentioned first.
    assert [r["title"] for r in shown["overdue"]] == ["Return library books"]
    history["return library books"] = "2026-11-02"
    shown = oh.filter_for_prompt(REMINDERS, history, TODAY)
    assert [r["title"] for r in shown["overdue"]] == ["Clean the gutters!"]


def test_overdue_item_surfaces_about_weekly():
    only_gutters = {"today": [], "overdue": [REMINDERS["overdue"][0]], "upcoming": []}
    history, eligible_days = {}, []
    for offset in range(21):
        day = date.fromordinal(TODAY.toordinal() + offset)
        if oh.filter_for_prompt(only_gutters, history, day)["overdue"]:
            eligible_days.append(offset)
            history[oh.normalize("Clean the gutters!")] = day.isoformat()
    assert eligible_days == [0, 7, 14]


def test_mentioned_titles_uses_token_overlap():
    text = "The gutters can wait for the weekend.\n\nThe quarterly report review is today."
    assert oh.mentioned_titles(text, REMINDERS) == ["Quarterly report review", "Clean the gutters!"]
    assert oh.mentioned_titles("A quiet day.", REMINDERS) == []


def _run_with(mocker, tmp_path, *, as_of=None, sent=True,
              welcome="The gutters are on the list; the city day comes first."):
    reminders = {"today": [], "overdue": [REMINDERS["overdue"][0]], "upcoming": []}
    history_file = tmp_path / "hist.json"
    mocker.patch("modules.weather.weather_block", return_value=None)
    mocker.patch("modules.calendar.calendar_block", return_value=[])
    welcome_mock = mocker.patch("modules.welcome.welcome_block", return_value=welcome)
    mocker.patch("modules.reminders.reminders_block", return_value=reminders)
    mocker.patch("modules.photo.photo_block", return_value=None)
    mocker.patch("modules.nyt.nyt_block", return_value=None)
    mocker.patch("modules.tweet.tweet_block", return_value=None)
    mocker.patch("renderer.render_email", return_value=MagicMock())
    mocker.patch("sender.send_email", return_value=sent)
    mocker.patch("config.load_config", return_value={
        "recipient_email": "reader@example.com", "opening_history_path": str(history_file),
        "default_location": {"name": "Springfield", "lat": 40.0, "lon": -75.0},
        "nyt_api_key": "k", "anthropic_api_key": "k2", "reminders_lists": []})
    import niederdaily
    app = importlib.reload(niederdaily)
    app.run(as_of=as_of)
    return history_file, welcome_mock


def test_real_send_records_mentions(mocker, tmp_path):
    history_file, welcome_mock = _run_with(mocker, tmp_path)
    assert list(json.loads(history_file.read_text())) == ["clean the gutters!"]
    assert welcome_mock.call_args.kwargs["mention_history"] == {}


def test_not_recorded_for_date_override_or_failed_send(mocker, tmp_path):
    for kwargs in ({"as_of": date(2026, 11, 10)}, {"sent": False}):
        history_file, _ = _run_with(mocker, tmp_path, **kwargs)
        assert not history_file.exists(), kwargs
