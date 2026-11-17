from datetime import date, datetime, timedelta, timezone
from html import unescape
import json
import socket
import subprocess

import pytest
import requests

from modules import parcel_api
from modules.parcel_api import (ParcelAPIError, build_summary, fetch_deliveries,
                                live_packages_block, read_api_key)
from modules.packages import summary_block
from renderer import render_email


NOW = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
SECRET_TRACKING = "TEST1234567890"


@pytest.fixture(autouse=True)
def no_live_network_or_processes(monkeypatch):
    """Parcel unit tests must not reach the network, Keychain, or source apps."""
    def blocked(*args, **kwargs):
        pytest.fail("Live network or subprocess access is forbidden in Parcel unit tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)


def _delivery(**changes):
    value = {
        "carrier_code": "ups",
        "description": "Example Shop",
        "status_code": 2,
        "tracking_number": SECRET_TRACKING,
        "extra_information": "00000",
        "events": [{"event": "Departed from facility", "date": "2026-11-06 21:14:00",
                    "location": "Example City, NJ", "additional": "raw carrier note"}],
        "date_expected": "2026-11-08 00:00:00",
    }
    value.update(changes)
    return value


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_fetch_sends_key_only_in_header_and_requests_active():
    session = _Session(_Response(200, {"success": True, "deliveries": []}))
    assert fetch_deliveries("k-123", session=session) == []
    url, kwargs = session.calls[0]
    assert url == "https://api.parcel.app/external/deliveries/"
    assert kwargs["headers"] == {"api-key": "k-123"}
    assert kwargs["params"] == {"filter_mode": "active"}
    assert kwargs["allow_redirects"] is False
    assert "k-123" not in url and kwargs["timeout"]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("destination", [
    "https://redirect.invalid/deliveries/",
    "https://api.parcel.app/another-path/",
    "http://redirect.invalid/deliveries/",
])
def test_fetch_rejects_redirects_without_forwarding_key(requests_mock, status, destination):
    requests_mock.get(parcel_api.API_URL, status_code=status,
                      headers={"Location": destination},
                      json={"success": True, "deliveries": []})
    requests_mock.get(destination, json={"success": True, "deliveries": []})

    with pytest.raises(ParcelAPIError) as error:
        fetch_deliveries("synthetic-test-key")

    assert str(error.value) == f"Parcel API request failed (HTTP {status})"
    assert requests_mock.call_count == 1
    request = requests_mock.request_history[0]
    assert request.hostname == "api.parcel.app"
    assert request.headers["api-key"] == "synthetic-test-key"
    assert request.qs == {"filter_mode": ["active"]}


def test_fetch_direct_success_still_works(requests_mock):
    requests_mock.get(parcel_api.API_URL, json={"success": True, "deliveries": []})
    assert fetch_deliveries("synthetic-test-key") == []
    assert requests_mock.call_count == 1


def test_redirect_uses_existing_snapshot_fallback_without_retry(requests_mock, mocker):
    requests_mock.get(parcel_api.API_URL, status_code=302,
                      headers={"Location": "https://redirect.invalid/deliveries/"},
                      text="Response body must not be used as a delivery list")
    snapshot = summary_block(build_summary([_delivery()], now=NOW), now=NOW)
    fallback = mocker.patch.object(parcel_api, "packages_block", return_value=snapshot)

    result = live_packages_block("/unused-private-snapshot.json", now=NOW,
                                 load_key=lambda: "synthetic-test-key",
                                 fetch=fetch_deliveries)

    assert result == {**snapshot, "refresh_succeeded": False}
    assert "refresh_succeeded" not in snapshot
    assert requests_mock.call_count == 1
    fallback.assert_called_once_with("/unused-private-snapshot.json", as_of=None, now=NOW)


@pytest.mark.parametrize("response", [
    _Response(401, {"success": False, "error_message": "bad key"}),
    _Response(200, {"success": False}),
    _Response(200, ValueError("not json")),
    _Response(200, {"success": True, "deliveries": "nope"}),
])
def test_fetch_rejects_unusable_responses(response):
    with pytest.raises(ParcelAPIError):
        fetch_deliveries("k", session=_Session(response))


def test_summary_strips_raw_fields_and_passes_reader():
    summary = build_summary([_delivery()], now=NOW)
    flat = repr(summary)
    for raw in (SECRET_TRACKING, "Example City", "raw carrier note", "00000", "Departed from"):
        assert raw not in flat
    entry = summary["shipments"][0]
    assert entry["expected_delivery"] == {"date": "2026-11-08", "time": None, "end_date": None,
                                          "end_time": None, "timezone": None,
                                          "source": "parcel_api"}
    assert entry["latest_event"]["status"] == "departed_facility"
    block = summary_block(summary, now=NOW)
    assert block["freshness"] == "fresh"
    row = block["shipments"][0]
    assert (row["company"], row["status"], row["carrier_code"]) == ("Example Shop", "in transit", "ups")
    assert row["latest_event"]["status"] == "Departed carrier facility"
    assert block["coverage_note"] is None


def test_epoch_window_is_utc_and_sensitive_description_is_dropped():
    delivery = _delivery(description="Pharmacy refill", timestamp_expected=1762610400,
                         timestamp_expected_end=1762621200, events=[])
    entry = build_summary([delivery], now=NOW)["shipments"][0]
    assert entry["expected_delivery"]["timezone"] == "UTC"
    assert entry["expected_delivery"]["time"] and entry["expected_delivery"]["end_time"]
    row = summary_block(build_summary([delivery], now=NOW), now=NOW)["shipments"][0]
    assert row["company"] is None and row["latest_event"] is None


def test_unclassified_event_and_unknown_status_are_left_out_honestly():
    delivery = _delivery(status_code=42, events=[{"event": "Weather delay", "date": "garbled"}])
    summary = build_summary([delivery], now=NOW)
    assert summary["shipments"][0]["latest_event"] is None
    block = summary_block(summary, now=NOW)
    assert block["shipments"][0]["status"] == "status unavailable"
    assert block["coverage_note"] == "Other package details may be missing; check Parcel."


def test_empty_active_list_states_no_active_packages():
    block = summary_block(build_summary([], now=NOW), now=NOW)
    assert block["no_active"] is True and block["shipments"] == []


def test_live_reader_prefers_api_and_never_touches_snapshot(mocker):
    fallback = mocker.patch.object(parcel_api, "packages_block")
    block = live_packages_block("/unused.json", now=NOW, load_key=lambda: "k",
                                fetch=lambda key: [_delivery()])
    assert block["shipments"][0]["company"] == "Example Shop"
    fallback.assert_not_called()


@pytest.mark.parametrize("fetch", [
    lambda key: (_ for _ in ()).throw(requests.ConnectionError("down")),
    lambda key: (_ for _ in ()).throw(ParcelAPIError("HTTP 429")),
])
def test_live_reader_falls_back_to_snapshot_on_api_failure(mocker, fetch):
    snapshot = summary_block(build_summary([_delivery()], now=NOW), now=NOW)
    fallback = mocker.patch.object(parcel_api, "packages_block", return_value=snapshot)
    assert live_packages_block("/snap.json", now=NOW, load_key=lambda: "k",
                               fetch=fetch) == {**snapshot, "refresh_succeeded": False}
    assert "refresh_succeeded" not in snapshot
    fallback.assert_called_once_with("/snap.json", as_of=None, now=NOW)


def test_live_reader_without_key_uses_snapshot_and_skips_network(mocker):
    fallback = mocker.patch.object(parcel_api, "packages_block", return_value=None)
    fetch = mocker.Mock()
    result = live_packages_block("/snap.json", load_key=lambda: None, fetch=fetch)
    assert result["freshness"] == "unavailable"
    assert result["refresh_succeeded"] is result["no_active"] is False
    fetch.assert_not_called()
    fallback.assert_called_once()


def test_historical_date_omits_live_packages():
    fetch = pytest.fail
    assert live_packages_block(None, as_of=date(2020, 1, 1), load_key=lambda: "k",
                               fetch=fetch) is None


def test_keychain_lookup_uses_security_and_hides_missing_item(mocker):
    run = mocker.patch.object(parcel_api.subprocess, "run")
    run.return_value.returncode = 0
    run.return_value.stdout = "secret-key\n"
    assert read_api_key() == "secret-key"
    assert run.call_args.args[0] == ["/usr/bin/security", "find-generic-password",
                                     "-s", "niederdaily.parcel-api", "-w"]
    run.return_value.returncode = 44
    run.return_value.stdout = ""
    assert read_api_key() is None


def test_api_rows_render_without_raw_fields():
    block = summary_block(build_summary([_delivery()], now=NOW), now=NOW)
    message = render_email(recipient="me@example.com", welcome=None, weather=None,
                           calendar=None, reminders=None, messages=None, photo=None,
                           nyt=None, tweet=None, packages=block)
    part = next(p for p in message.walk() if p.get_content_type() == "text/html")
    html = part.get_payload(decode=True).decode()
    assert "Example Shop" in html
    assert SECRET_TRACKING not in html and "Example City" not in html


def test_yearless_carrier_event_date_and_colon_label_are_kept():
    delivery = _delivery(description="Order 113: Raincoat",
                         events=[{"event": "Arrived at USPS Regional Facility",
                                  "date": "Saturday, November 7 9:19 AM"}])
    row = summary_block(build_summary([delivery], now=NOW), now=NOW)["shipments"][0]
    assert row["company"] == "Order 113: Raincoat"
    assert row["latest_event"] == {"status": "Arrived at carrier facility",
                                   "date": "2026-11-07", "time": "09:19", "timezone": None}


def test_placeholder_event_date_is_dropped():
    delivery = _delivery(events=[{"event": "Delivered", "date": "--//--"}])
    assert build_summary([delivery], now=NOW)["shipments"][0]["latest_event"] is None


def _render_packages(block):
    message = render_email(recipient="reader@example.com", welcome=None, weather=None,
                           calendar=None, reminders=None, messages=None, photo=None,
                           nyt=None, packages=block, as_of=NOW.date())
    part = next(p for p in message.walk() if p.get_content_type() == "text/html")
    return unescape(part.get_payload(decode=True).decode())


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("state", [
    "no_snapshot", "missing", "malformed", "expired", "unavailable",
    "fresh_empty", "fresh_rows", "stale_empty", "stale_rows",
])
def test_failed_refresh_rendering_end_to_end(requests_mock, tmp_path, status, state):
    requests_mock.get(parcel_api.API_URL, status_code=status,
                      headers={"Location": "https://api.parcel.app/changed-endpoint/"},
                      json={"success": True, "deliveries": []})
    path = tmp_path / "snapshot.json"
    usable = state.startswith(("fresh_", "stale_"))
    if state not in {"no_snapshot", "missing"}:
        age = timedelta(hours=3) if state.startswith("stale_") else timedelta(minutes=50)
        if state == "expired":
            age = timedelta(hours=25)
        data = build_summary([_delivery()] if state.endswith("_rows") else [], now=NOW - age)
        if state.startswith("stale_"):
            data["freshness"] = "stale"
        if usable:
            # File generation time is not the source's last successful check.
            data["generated_at"] = NOW.isoformat()
        if state == "unavailable":
            data.update(freshness="unavailable", as_of=None, cache_age_seconds=None,
                        reason="cache_missing")
        if state == "malformed":
            data = {"invalid": "snapshot"}
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    original = path.read_bytes() if path.exists() else None

    block = live_packages_block(None if state == "no_snapshot" else str(path), now=NOW,
                                load_key=lambda: "synthetic-test-key", fetch=fetch_deliveries)
    html = _render_packages(block)

    assert requests_mock.call_count == 1
    assert block["refresh_succeeded"] is block["no_active"] is False
    assert "Couldn't refresh" in html
    assert "No active packages" not in html
    if usable:
        checked = "Nov 7, 2 AM ET" if state.startswith("stale_") else "Nov 7, 4:10 AM ET"
        assert f"Couldn't refresh; last checked {checked}." in html
        assert "Packages unavailable" not in html
        assert ("Parcel data may be out of date" in html) == state.startswith("stale_")
        if state.endswith("_rows"):
            assert "Example Shop" in html
            assert html.index("Couldn't refresh") < html.index("Example Shop")
    else:
        assert "Packages unavailable" in html
        assert "last checked Nov" not in html
    assert (path.read_bytes() if path.exists() else None) == original


def test_only_successful_complete_refresh_can_render_no_active(requests_mock):
    requests_mock.get(parcel_api.API_URL, json={"success": True, "deliveries": []})
    block = live_packages_block(None, now=NOW, load_key=lambda: "synthetic-test-key",
                                fetch=fetch_deliveries)
    html = _render_packages(block)
    assert block["refresh_succeeded"] is block["no_active"] is True
    assert "No active packages." in html
    assert "Couldn't refresh" not in html and "Packages unavailable" not in html
    assert requests_mock.call_count == 1


def test_successful_but_incomplete_refresh_does_not_claim_empty(requests_mock):
    requests_mock.get(parcel_api.API_URL, json={"success": True, "deliveries": [{}]})
    block = live_packages_block(None, now=NOW, load_key=lambda: "synthetic-test-key",
                                fetch=fetch_deliveries)
    assert block["refresh_succeeded"] is True and block["no_active"] is False
    assert "No active packages" not in _render_packages(block)


@pytest.mark.parametrize("stamp,expected", [
    ("2026-11-01T05:10:00+00:00", "Nov 1, 1:10 AM ET"),
    ("2026-11-01T06:10:00+00:00", "Nov 1, 1:10 AM ET"),
    ("2026-11-08T04:10:00+00:00", "Nov 7, 11:10 PM ET"),
])
def test_last_checked_uses_eastern_time_and_source_date(stamp, expected):
    block = {"shipments": [], "freshness": "stale", "no_active": False,
             "refresh_succeeded": False, "as_of": stamp, "coverage_note": None}
    assert f"last checked {expected}" in _render_packages(block)
