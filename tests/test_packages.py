import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from modules.packages import packages_block
from modules.packages import _EVENTS
from renderer import render_email


FIXTURE = Path(__file__).parent / "fixtures" / "parcel_brief_summary_v1.json"


def test_cloud_event_codes_match_receiver_display_allowlist():
    assert _EVENTS == {
        "delivered": "Delivered",
        "out_for_delivery": "Out for delivery",
        "delivery_attempted": "Delivery attempted",
        "available_for_pickup": "Available for pickup",
        "arrived_at_facility": "Arrived at carrier facility",
        "departed_facility": "Departed carrier facility",
        "in_transit": "Moving through network",
        "label_created": "Shipping label created",
        "customs_clearance": "In customs clearance",
        "delivery_exception": "Delivery exception",
    }


def _entry(**changes):
    return {
        "shipment_id": "0" * 64,
        "carrier_code": "ups",
        "status": "out_for_delivery",
        "status_code": 4,
        "is_active": True,
        "company": "Acme",
        "item": "Raincoat",
        "label_source": "trusted_validated_ingest",
        **changes,
    }


def _snapshot(tmp_path, shipments, *, age=timedelta(0), freshness="fresh",
              truncated=False, no_active=False):
    now = datetime.now(timezone.utc)
    data = {
        "schema_version": 1, "source": "parcel_cache",
        "generated_at": now.isoformat(),
        "as_of": (now - age).isoformat() if freshness != "unavailable" else None,
        "cache_age_seconds": int(age.total_seconds()) if freshness != "unavailable" else None,
        "fresh_for_seconds": 7200, "max_age_seconds": 86400,
        "freshness": freshness,
        "reason": "cache_missing" if freshness == "unavailable" else None,
        "total_cached": len(shipments), "truncated": truncated,
        "coverage": {
            "scope": "recent_and_active_cache", "complete": freshness != "unavailable",
            "returned_count": len(shipments),
            "unlabeled_count": sum(x.get("label_source") is None for x in shipments),
            "unknown_status_count": sum(x.get("status") == "unknown" for x in shipments),
            "counts_scope": "returned_shipments",
            "active_cached_count": sum(x.get("is_active") is True for x in shipments),
            "active_membership_unknown_count": sum(x.get("is_active") is None for x in shipments),
            "can_state_no_active": no_active,
        },
        "shipments": shipments,
    }
    path = tmp_path / "parcel-snapshot.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


def _html(message):
    part = next(p for p in message.walk() if p.get_content_type() == "text/html")
    return part.get_payload(decode=True).decode()


def test_exact_authoritative_fixture_shows_only_trusted_active_label(tmp_path):
    path = tmp_path / "parcel-snapshot.json"
    path.write_bytes(FIXTURE.read_bytes())
    path.chmod(0o600)
    now = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
    summary = packages_block(str(path), now=now)
    assert summary == {
        "shipments": [{"carrier_code": "ups", "company": "Example Shop", "item": "Raincoat",
                       "status": "out for delivery", "estimated_delivery": None,
                       "tracking_url": None},
                      {"carrier_code": "fedex", "company": None, "item": None,
                       "status": "delivery exception", "estimated_delivery": None,
                       "tracking_url": None}],
        "freshness": "fresh", "as_of": "2026-10-09T17:55:00+00:00",
        "truncated": False, "no_active": False,
        "unlabeled_statuses": {"delivery exception": 1},
        "coverage_note": "Other package details may be missing; check Parcel.",
    }
    assert "bad06e" not in str(summary)


def test_optional_expected_window_event_in_two_column_row(tmp_path):
    entry = _entry(company="Example Store", item="Mixing bowl",
                   expected_delivery={"date": "2026-10-13", "time": "10:00",
                                      "end_date": "2026-10-13", "end_time": "14:00",
                                      "timezone": None, "source": "parcel_api"},
                   latest_event={"status": "arrived_at_facility", "date": "2026-10-11",
                                 "time": "09:30", "timezone": None,
                                 "source": "parcel_api"})
    summary = packages_block(str(_snapshot(tmp_path, [entry])))
    row = summary["shipments"][0]
    assert row["expected_delivery"]["date"] == "2026-10-13"
    assert row["latest_event"] == {"status": "Arrived at carrier facility",
                                   "date": "2026-10-11", "time": "09:30",
                                   "timezone": None}
    html = _html(render_email(recipient="me@example.com", welcome=None,
                              weather=None, calendar=None, reminders=None,
                              messages=None, photo=None, nyt=None, packages=summary,
                              as_of=date(2026, 10, 13)))
    row = html[html.index('class="list-row package-row"'):]
    assert '<span class="list-time">Today</span>' in row
    assert ('<span class="calendar-source calendar-line" style="color:#694122;">'
            '<span class="calendar-dot" style="background:#694122;"></span>UPS</span>'
            '<span class="calendar-title">Example Store · Mixing bowl</span>'
            '<span class="calendar-location">Out for delivery · 10am–2pm · '
            'Arrived at carrier facility · Sun 9:30am</span>') in row
    assert row.index("Today") < row.index("UPS</span>") < row.index("Example Store · Mixing bowl")
    assert "time zone not provided" not in html
    for gone in (".package-carrier", ".package-name", ".package-detail",
                 ".package-event", ".list-row.package-row"):
        assert gone not in html
    assert ".list-time.pkg-late{color:#ff453a;}" in html
    assert "pkg-today" not in html


def test_utc_timing_converts_to_new_york_with_date_rollover(tmp_path):
    entry = _entry(expected_delivery={"date": "2026-10-13", "time": "03:00",
                                      "end_date": None, "end_time": None,
                                      "timezone": "UTC", "source": "parcel_api"},
                   latest_event={"status": "arrived_at_facility",
                                 "date": "2026-10-13", "time": "01:30",
                                 "timezone": "UTC", "source": "parcel_api"})
    summary = packages_block(str(_snapshot(tmp_path, [entry])))
    html = _html(render_email(recipient="me@example.com", welcome=None,
                              weather=None, calendar=None, reminders=None,
                              messages=None, photo=None, nyt=None, packages=summary,
                              as_of=date(2026, 10, 12)))
    assert '<span class="list-time">Today</span>' in html
    assert ("Out for delivery · by 11pm · Arrived at carrier facility · 9:30pm"
            in html)
    assert " ET" not in html.split("Packages", 1)[1]
    assert "time zone not provided" not in html


def test_date_only_estimate_keeps_source_date_without_midnight_or_zone(tmp_path):
    entry = _entry(expected_delivery={"date": "2026-10-13", "time": None,
                                      "end_date": None, "end_time": None,
                                      "timezone": None, "source": "parcel_api"})
    summary = packages_block(str(_snapshot(tmp_path, [entry])))
    html = _html(render_email(recipient="me@example.com", welcome=None,
                              weather=None, calendar=None, reminders=None,
                              messages=None, photo=None, nyt=None, packages=summary,
                              as_of=date(2026, 10, 1)))
    assert '<span class="list-time">Oct 13</span>' in html
    assert '<span class="calendar-location">Out for delivery</span>' in html
    assert "12am" not in html and "time zone not provided" not in html


def test_child_label_becomes_company_only_and_missing_eta_stays_missing(tmp_path):
    entry = _entry(company="REI", item="Youth ski equipment",
                   expected_delivery=None, latest_event=None)
    summary = packages_block(str(_snapshot(tmp_path, [entry])))
    assert summary["shipments"][0]["company"] == "REI"
    assert summary["shipments"][0]["item"] is None
    html = _html(render_email(recipient="me@example.com", welcome=None,
                              weather=None, calendar=None, reminders=None,
                              messages=None, photo=None, nyt=None, packages=summary))
    assert "REI" in html and "Youth" not in html
    assert '<span class="list-time">No date</span>' in html


def test_reader_rejects_unvalidated_detail_without_leaking_it(tmp_path):
    entries = [
        _entry(expected_delivery={"date": "2026-10-13", "time": None,
                                  "end_date": None, "end_time": None,
                                  "timezone": None, "source": "parcel_api"},
               raw_email="private"),
        _entry(shipment_id="1" * 64,
               latest_event={"status": "At home address", "date": None,
                             "time": None, "timezone": None, "source": "parcel_api"}),
    ]
    summary = packages_block(str(_snapshot(tmp_path, entries)))
    assert summary["shipments"] == []
    assert "private" not in str(summary) and "address" not in str(summary)
    assert summary["coverage_note"] is not None


def test_ignores_untrusted_inactive_and_sensitive_labels(tmp_path):
    path = _snapshot(tmp_path, [
        _entry(raw_email="private raw message", address="private address",
               estimated_delivery="2099-01-01", tracking_url="https://unverified.invalid/"),
        _entry(shipment_id="1" * 64, label_source=None, company=None),
        _entry(shipment_id="2" * 64, company="Medical Clinic"),
        _entry(shipment_id="3" * 64, is_active=False),
        _entry(shipment_id="4" * 64, item="Prescription", status="unknown",
               status_code=None),
    ])
    summary = packages_block(str(path))
    assert len(summary["shipments"]) == 4
    assert summary["shipments"][0] == {
        "carrier_code": "ups", "company": "Acme", "item": "Raincoat", "status": "out for delivery",
        "estimated_delivery": None, "tracking_url": None,
    }
    assert summary["shipments"][1]["item"] is None
    assert summary["shipments"][1]["status"] == "status unavailable"
    assert summary["shipments"][2]["company"] is None
    assert summary["shipments"][3]["company"] is None
    assert summary["unlabeled_statuses"] == {"out for delivery": 2}
    assert summary["no_active"] is False
    assert "raw_email" not in str(summary)


def test_missing_old_public_and_unavailable_cache(tmp_path):
    assert packages_block(None) is None
    path = _snapshot(tmp_path, [_entry()], age=timedelta(hours=25), freshness="stale")
    assert packages_block(str(path)) is None
    path = _snapshot(tmp_path, [_entry()], age=timedelta(hours=3), freshness="fresh")
    assert packages_block(str(path)) is None
    path = _snapshot(tmp_path, [], freshness="unavailable")
    assert packages_block(str(path))["coverage_note"] == "Parcel package coverage is unavailable."
    path = _snapshot(tmp_path, [_entry()])
    path.chmod(0o644)
    assert packages_block(str(path)) is None
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    assert packages_block(str(link)) is None
    assert packages_block(str(path), as_of=date(2020, 1, 1)) is None


def test_no_active_claim_requires_explicit_complete_fresh_coverage(tmp_path):
    path = _snapshot(tmp_path, [], no_active=True)
    confirmed = packages_block(str(path))
    assert confirmed["no_active"] is True
    def render(summary):
        return _html(render_email(
            recipient="me@example.com", welcome=None, weather=None,
            calendar=None, reminders=None, messages=None, photo=None,
            nyt=None, packages=summary,
        ))
    assert "No active packages." not in render(confirmed)
    assert "No active packages." in render({**confirmed, "refresh_succeeded": True})
    assert "No active packages." not in render({**confirmed, "refresh_succeeded": False})
    path = _snapshot(tmp_path, [], no_active=False)
    uncertain = packages_block(str(path))
    assert uncertain["no_active"] is False
    assert "No active packages." not in render(uncertain)
    path = _snapshot(tmp_path, [], age=timedelta(hours=3), freshness="stale",
                     no_active=True)
    assert packages_block(str(path))["no_active"] is False
    path = _snapshot(tmp_path, [_entry(label_source=None, company=None)],
                     no_active=True)
    assert packages_block(str(path))["no_active"] is False
    contradictory = json.loads(path.read_text())
    contradictory["coverage"]["unlabeled_count"] = 0
    contradictory["coverage"]["active_cached_count"] = 0
    path.write_text(json.dumps(contradictory))
    assert packages_block(str(path))["no_active"] is False


def test_stale_snapshot_is_labeled_and_bounded(tmp_path):
    path = _snapshot(tmp_path, [_entry(shipment_id=f"{i:064x}") for i in range(30)],
                     age=timedelta(hours=3), freshness="stale", truncated=True)
    summary = packages_block(str(path))
    assert summary["freshness"] == "stale"
    assert summary["truncated"] is True
    assert len(summary["shipments"]) == 20


def test_labeled_entry_after_unlabeled_rows_is_not_lost(tmp_path):
    unlabeled = [_entry(shipment_id=f"{i:064x}", label_source=None,
                        company=None) for i in range(25)]
    path = _snapshot(tmp_path, unlabeled + [_entry(shipment_id="f" * 64)])
    summary = packages_block(str(path))
    assert len(summary["shipments"]) == 20
    assert summary["shipments"][0]["company"] == "Acme"
    assert summary["truncated"] is True


def test_all_unlabeled_realistic_statuses_remain_useful_without_retailers(tmp_path):
    cases = [("out_for_delivery", 4), ("in_transit", 2),
             ("in_transit", 2), ("in_transit", 2),
             ("information_received", 8)]
    entries = [_entry(shipment_id=f"{i:064x}", label_source=None,
                      company=None, item=None, status=status, status_code=code)
               for i, (status, code) in enumerate(cases)]
    path = _snapshot(tmp_path, entries)
    summary = packages_block(str(path))
    assert len(summary["shipments"]) == 5
    assert all(entry["company"] is None and entry["item"] is None
               for entry in summary["shipments"])
    assert summary["no_active"] is False
    assert summary["unlabeled_statuses"] == {
        "out for delivery": 1, "in transit": 3,
        "shipping information received": 1,
    }
    message = render_email(recipient="me@example.com", welcome=None,
                           weather=None, calendar=None, reminders=None,
                           messages=None, photo=None, nyt=None, packages=summary)
    html = _html(message)
    assert html.count('class="list-row package-row"') == 5
    assert html.count("UPS</span>") == 5
    assert "Out for delivery" in html and "Shipping information received" in html
    assert "No active packages" not in html
    assert "Acme" not in html


def test_carrier_colors_and_unknown_fallback_with_untrusted_labels(tmp_path):
    carriers = ("fedex", "ups", "amzlus", "dhl", "usps", "swiship", "othercarrier")
    entries = [_entry(shipment_id=f"{i:064x}", carrier_code=code,
                      label_source=None, company="Private Purchase", item="Secret Item")
               for i, code in enumerate(carriers)]
    summary = packages_block(str(_snapshot(tmp_path, entries)))
    html = _html(render_email(recipient="me@example.com", welcome=None,
                              weather=None, calendar=None, reminders=None,
                              messages=None, photo=None, nyt=None, packages=summary))
    assert html.count('class="list-row package-row"') == len(carriers)
    for name, color in (("FedEx", "#A02A7B"), ("UPS", "#694122"),
                        ("Amazon", "#995000"), ("DHL", "#826100"),
                        ("USPS", "#1165A3"), ("Swiship", "#121212"),
                        ("OTHERCARRIER", "#121212")):
        assert (f'class="calendar-source calendar-line" style="color:{color};">'
                f'<span class="calendar-dot" style="background:{color};"></span>'
                f'{name}</span>') in html
    assert "Private Purchase" not in html and "Secret Item" not in html


def test_renderer_discloses_uncertainty_without_raw_data(tmp_path):
    path = _snapshot(tmp_path, [
        _entry(item="<script>alert(1)</script>", raw_email="never render this",
               address="never render address", estimated_delivery="2099-01-01"),
    ], age=timedelta(hours=3), freshness="stale", truncated=True)
    message = render_email(
        recipient="me@example.com", welcome=None, weather=None, calendar=None,
        reminders=None, messages=None, photo=None, nyt=None,
        packages=packages_block(str(path)),
    )
    html = _html(message)
    assert "Packages" in html and "Acme" in html and "Out for delivery" in html
    assert "Parcel data may be out of date" in html
    assert "More shipments may be listed" in html
    assert "<script>" not in html and "never render" not in html
    assert "tracking" not in html.lower() and "2099-01-01" not in html


def test_niederdaily_passes_optional_snapshot_to_renderer(mocker, tmp_path):
    import niederdaily

    snapshot = str(tmp_path / "snapshot.json")
    mocker.patch.object(niederdaily.cfg, "load_config", return_value={
        "recipient_email": "me@example.com", "anthropic_api_key": "unused",
        "nyt_api_key": "unused",
    })
    for name in ("weather_block", "calendar_block", "reminders_block", "messages_block",
                 "photo_block", "tweet_block", "nyt_block", "welcome_block"):
        mocker.patch.object(niederdaily, name, return_value=None)
    summary = {"shipments": [{"company": "Acme", "status": "out for delivery"}],
               "freshness": "fresh", "truncated": False, "no_active": False,
               "coverage_note": None}
    reader = mocker.patch.object(niederdaily, "live_packages_block", return_value=summary)
    renderer = mocker.patch.object(niederdaily, "render_email", return_value=object())
    sender = mocker.patch.object(niederdaily, "send_email", return_value=True)

    niederdaily.run(parcel_snapshot_path=snapshot)

    reader.assert_called_once_with(snapshot, as_of=None)
    assert renderer.call_args.kwargs["packages"] == summary
    sender.assert_called_once()


def test_one_run_package_gate_blocks_partial_send(mocker):
    import niederdaily

    mocker.patch.object(niederdaily.cfg, "load_config", return_value={
        "recipient_email": "me@example.com", "anthropic_api_key": "unused",
        "nyt_api_key": "unused",
    })
    mocker.patch.object(niederdaily, "weather_block", return_value={"locations": []})
    mocker.patch.object(niederdaily, "calendar_block", return_value=[])
    mocker.patch.object(niederdaily, "reminders_block", return_value={"today": []})
    for name in ("messages_block", "photo_block", "tweet_block", "nyt_block"):
        mocker.patch.object(niederdaily, name, return_value=None)
    mocker.patch.object(niederdaily, "live_packages_block", return_value=None)
    sender = mocker.patch.object(niederdaily, "send_email")
    assert niederdaily.run(parcel_snapshot_path="/private/snapshot.json",
                           require_packages=True) is False
    sender.assert_not_called()


def test_package_test_is_marked_and_has_no_automatic_send_retry(mocker):
    import niederdaily

    mocker.patch.object(niederdaily.cfg, "load_config", return_value={
        "recipient_email": "owner@example.com", "test_recipient": "owner@example.com",
        "anthropic_api_key": "unused",
        "nyt_api_key": "unused",
    })
    for name, result in (("weather_block", {"locations": []}),
                         ("calendar_block", []), ("reminders_block", {"today": []}),
                         ("messages_block", None), ("photo_block", None),
                         ("tweet_block", None), ("nyt_block", None),
                         ("welcome_block", None)):
        mocker.patch.object(niederdaily, name, return_value=result)
    summary = {"shipments": [{"carrier_code": "usps", "company": None,
                              "item": None, "status": "in transit"}],
               "freshness": "fresh", "no_active": False}
    mocker.patch.object(niederdaily, "live_packages_block", return_value=summary)
    renderer = mocker.patch.object(niederdaily, "render_email", return_value=object())
    sender = mocker.patch.object(niederdaily, "send_email", return_value=True)

    assert niederdaily.run(parcel_snapshot_path="/private/snapshot.json",
                           test_mode=True) is True
    assert renderer.call_args.kwargs["test_mode"] is True
    assert sender.call_args.kwargs == {"max_attempts": 1}


def test_package_test_rejects_any_other_recipient(mocker):
    import niederdaily

    mocker.patch.object(niederdaily.cfg, "load_config", return_value={
        "recipient_email": "someone@example.com", "test_recipient": "owner@example.com"})
    sender = mocker.patch.object(niederdaily, "send_email")
    assert niederdaily.run(test_mode=True) is False
    sender.assert_not_called()


def test_package_test_is_refused_without_a_configured_test_recipient(mocker):
    import niederdaily

    mocker.patch.object(niederdaily.cfg, "load_config", return_value={
        "recipient_email": "owner@example.com"})
    sender = mocker.patch.object(niederdaily, "send_email")
    assert niederdaily.run(test_mode=True) is False
    sender.assert_not_called()


def test_package_test_subject_and_html_are_clearly_marked():
    message = render_email(recipient="owner@example.com", welcome=None,
                           weather=None, calendar=None, reminders=None,
                           messages=None, photo=None, nyt=None,
                           packages={"shipments": [{"carrier_code": "usps",
                                                    "company": None, "item": None,
                                                    "status": "in transit"}],
                                     "freshness": "fresh", "truncated": False,
                                     "no_active": False}, test_mode=True)
    assert message["Subject"].startswith("TEST · NiederDaily Packages · ")
    assert message["To"] == message["From"] == "owner@example.com"
    assert message.get("Cc") is None and message.get("Bcc") is None
    assert "TEST EDITION · Package integration preview" in _html(message)
    assert "USPS" in _html(message) and "In transit" in _html(message)
    assert not [p for p in message.walk() if p.get_content_type() == "text/plain"]


def _expected(day, time=None, end_day=None, end_time=None, zone=None):
    return {"date": day, "time": time, "end_date": end_day, "end_time": end_time,
            "timezone": zone, "source": "parcel_api"}


def _row(name, status="in transit", expected=None, event=None, carrier="ups"):
    return {"carrier_code": carrier, "company": name, "item": None, "status": status,
            "estimated_delivery": None, "tracking_url": None,
            "expected_delivery": expected, "latest_event": event}


def test_rows_sort_by_date_with_calendar_style_labels():
    import re
    from renderer import _packages_html
    today = date(2026, 11, 16)
    shipments = [
        _row("Undated"),
        _row("Far", expected=_expected("2026-11-24")),
        _row("Thursday", expected=_expected("2026-11-19")),
        _row("Weekday window", expected=_expected("2026-11-18", end_day="2026-11-19")),
        _row("Tomorrow", expected=_expected("2026-11-17")),
        _row("Today", expected=_expected("2026-11-16")),
        _row("Late", expected=_expected("2026-11-14")),
        _row("Date window", expected=_expected("2026-11-23", end_day="2026-11-25")),
        _row("Problem", status="delivery exception", expected=_expected("2026-11-20")),
        _row("Arriving", status="out for delivery", expected=_expected("2026-11-16")),
        _row("Done", status="delivered"),
    ]
    html = _packages_html({"shipments": shipments, "freshness": "fresh",
                           "truncated": False, "no_active": False,
                           "refresh_succeeded": True, "coverage_note": None}, today=today)
    rows = re.findall(r'<span class="list-time([^"]*)">([^<]+)</span>.*?'
                      r'<span class="calendar-title">([^<]+)</span>', html)
    assert [(title, label, cls.strip()) for cls, label, title in rows] == [
        ("Late", "Nov 14", "pkg-late"),
        ("Today", "Today", ""),
        ("Arriving", "Today", ""),
        ("Tomorrow", "Tomorrow", ""),
        ("Weekday window", "Wed–Thu", ""),
        ("Thursday", "Thu", ""),
        ("Problem", "Fri", ""),
        ("Date window", "Nov 23–25", ""),
        ("Far", "Nov 24", ""),
        ("Undated", "No date", ""),
        ("Done", "Delivered", ""),
    ]


def test_tomorrow_exception_sorts_after_today_rows():
    import re
    from renderer import _packages_html
    today = date(2026, 11, 16)
    shipments = [
        _row("Exception", status="delivery exception", expected=_expected("2026-11-17")),
        _row("Today A", expected=_expected("2026-11-16")),
        _row("Today B", status="out for delivery", expected=_expected("2026-11-16")),
    ]
    html = _packages_html({"shipments": shipments, "freshness": "fresh",
                           "truncated": False, "no_active": False,
                           "refresh_succeeded": True, "coverage_note": None}, today=today)
    titles = re.findall(r'<span class="calendar-title">([^<]+)</span>', html)
    assert titles == ["Today A", "Today B", "Exception"]


def test_event_and_window_times_use_calendar_clock_without_zone_note():
    from renderer import _packages_html
    today = date(2026, 11, 16)
    arrived = "Arrived at carrier facility"
    shipments = [
        _row("Same day", expected=_expected("2026-11-16", end_time="20:00",
                                            end_day="2026-11-16"),
             event={"status": arrived, "date": "2026-11-16", "time": "05:19",
                    "timezone": None}),
        _row("This week", expected=_expected("2026-11-18", "11:00", "2026-11-18", "14:30"),
             event={"status": arrived, "date": "2026-11-14", "time": "11:10",
                    "timezone": None}),
        _row("Older", expected=_expected("2026-11-19"),
             event={"status": arrived, "date": "2026-11-06", "time": "11:10",
                    "timezone": None}),
        _row("Utc", expected=_expected("2026-11-21", "03:00", zone="UTC"),
             event={"status": arrived, "date": "2026-11-15", "time": "02:00",
                    "timezone": "UTC"}),
    ]
    html = _packages_html({"shipments": shipments, "freshness": "fresh",
                           "truncated": False, "no_active": False,
                           "refresh_succeeded": True, "coverage_note": None}, today=today)
    assert f"In transit · by 8pm · {arrived} · 5:19am" in html
    assert f"In transit · 11am–2:30pm · {arrived} · Sat 11:10am" in html
    assert f"In transit · {arrived} · Nov 6, 11:10am" in html
    assert f"In transit · by 10pm · {arrived} · Sat 9pm" in html
    assert "time zone not provided" not in html and " ET" not in html
