import importlib.util
import json
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from modules.packages import _EVENTS

import pytest


ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "parcel_brief_summary_v1.json"
SPEC = importlib.util.spec_from_file_location(
    "parcel_snapshot_writer", ROOT / "setup" / "write_parcel_summary_snapshot.py")
writer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writer)


def test_writer_and_reader_share_exact_cloud_event_codes():
    assert writer.EVENT_STATUSES == set(_EVENTS)


def fresh_fixture():
    data = json.loads(FIXTURE.read_text())
    now = datetime.now(timezone.utc)
    data["generated_at"] = now.isoformat()
    data["as_of"] = (now - timedelta(seconds=5)).isoformat()
    data["cache_age_seconds"] = 5
    return data


def test_writer_accepts_exact_fresh_summary_into_private_file(tmp_path):
    data = fresh_fixture()
    target = tmp_path / "private" / "summary.json"
    writer.write_snapshot(writer.validate(data), target)
    assert json.loads(target.read_text()) == data
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700


def detailed_fixture():
    data = fresh_fixture()
    data["shipments"][1].update(
        expected_delivery={"date": "2026-10-13", "time": "10:00",
                           "end_date": "2026-10-13", "end_time": "14:00",
                           "timezone": None, "source": "parcel_api"},
        latest_event={"status": "arrived_at_facility", "date": "2026-10-11",
                      "time": "09:30", "timezone": None,
                      "source": "parcel_api"})
    return data


def test_writer_accepts_optional_date_window_and_safe_event(tmp_path):
    data = detailed_fixture()
    target = tmp_path / "private" / "summary.json"
    writer.write_snapshot(data, target)
    assert json.loads(target.read_text()) == data


def test_writer_accepts_explicit_utc_timing_and_dated_carrier_event():
    data = detailed_fixture()
    row = data["shipments"][1]
    row["expected_delivery"]["timezone"] = "UTC"
    row["latest_event"].update(status="arrived_at_facility", timezone="UTC")
    assert writer.validate(data) == data


@pytest.mark.parametrize("path,value", [
    (("expected_delivery", "date"), "2026-02-30"),
    (("expected_delivery", "date"), "Tuesday by 11 PM"),
    (("expected_delivery", "time"), "11:00Z"),
    (("expected_delivery", "timezone"), "America/Los_Angeles"),
    (("expected_delivery", "end_date"), "2026-10-12"),
    (("latest_event", "status"), "Arrived at home address"),
    (("latest_event", "status"), "at_facility"),
    (("latest_event", "status"), {"event": "private"}),
    (("latest_event", "date"), None),
])
def test_writer_rejects_unstructured_detail(path, value):
    data = detailed_fixture()
    data["shipments"][1][path[0]][path[1]] = value
    with pytest.raises(ValueError):
        writer.validate(data)


def test_writer_rejects_raw_detail_fields():
    data = detailed_fixture()
    data["shipments"][1]["raw_email"] = "private"
    with pytest.raises(ValueError):
        writer.validate(data)
    data = detailed_fixture()
    data["shipments"][1]["latest_event"]["location"] = "private"
    with pytest.raises(ValueError):
        writer.validate(data)


@pytest.mark.parametrize("change", [
    lambda data: data.update(freshness="stale"),
    lambda data: data.update(truncated=True),
    lambda data: data["coverage"].update(complete=False),
    lambda data: data["shipments"][0].update(raw_email="private"),
    lambda data: data.update(shipments=[]),
])
def test_writer_rejects_partial_or_extra_data(change):
    data = fresh_fixture()
    change(data)
    with pytest.raises(ValueError):
        writer.validate(data)


def test_writer_rejects_old_fixture_and_tool_envelope():
    old = json.loads(FIXTURE.read_text())
    with pytest.raises(ValueError):
        writer.validate(old, now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        writer.validate({"content": [{"type": "text", "text": json.dumps(fresh_fixture())}]})


def test_writer_rejects_out_of_order_summary_without_replacing_file(tmp_path):
    target = tmp_path / "private" / "summary.json"
    newer = fresh_fixture()
    writer.write_snapshot(newer, target)
    original = target.read_bytes()

    older = fresh_fixture()
    older["generated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    older["as_of"] = (datetime.now(timezone.utc) - timedelta(minutes=1, seconds=5)).isoformat()
    writer.validate(older)
    with pytest.raises(ValueError, match="older than the stored"):
        writer.write_snapshot(older, target)
    assert target.read_bytes() == original

    with pytest.raises(ValueError, match="older than the stored"):
        writer.write_snapshot(newer, target)
    assert target.read_bytes() == original


def test_writer_accepts_newer_cache_after_existing_snapshot(tmp_path):
    target = tmp_path / "private" / "summary.json"
    older = fresh_fixture()
    older["generated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    older["as_of"] = (datetime.now(timezone.utc) - timedelta(minutes=1, seconds=5)).isoformat()
    writer.write_snapshot(older, target)
    newer = fresh_fixture()
    writer.write_snapshot(newer, target)
    assert json.loads(target.read_text())["as_of"] == newer["as_of"]
    assert stat.S_IMODE((target.parent / ".parcel-summary.lock").stat().st_mode) == 0o600


def test_hourly_handoff_accepts_same_cache_with_newer_generation(tmp_path):
    # An hourly run that did not need a provider refresh rereads the same
    # as_of with a new generated_at; the writer must accept it.
    target = tmp_path / "private" / "summary.json"
    now = datetime.now(timezone.utc)
    first = fresh_fixture()
    first["as_of"] = (now - timedelta(minutes=65)).isoformat()
    first["generated_at"] = (now - timedelta(minutes=5)).isoformat()
    first["cache_age_seconds"] = 3600
    writer.write_snapshot(first, target)
    second = dict(first, generated_at=now.isoformat(), cache_age_seconds=3900)
    writer.write_snapshot(second, target)
    assert json.loads(target.read_text())["generated_at"] == second["generated_at"]


def test_hourly_handoff_rejects_exact_resend_without_replacing_file(tmp_path):
    target = tmp_path / "private" / "summary.json"
    data = fresh_fixture()
    writer.write_snapshot(data, target)
    original = target.read_bytes()
    with pytest.raises(ValueError, match="older than the stored"):
        writer.write_snapshot(dict(data), target)
    assert target.read_bytes() == original


def test_writer_rejects_cache_older_than_two_hours():
    data = fresh_fixture()
    data["as_of"] = (datetime.now(timezone.utc) - timedelta(hours=2, minutes=1)).isoformat()
    data["cache_age_seconds"] = 7200
    with pytest.raises(ValueError, match="not current"):
        writer.validate(data)
