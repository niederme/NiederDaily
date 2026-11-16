"""Validate Parcel package summaries for display. Never query or import parcels here.

The summary comes either from a private snapshot file or from modules.parcel_api.
"""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &'’().,:/!…+-]{0,59}$")
_SENSITIVE = re.compile(
    r"\b(?:medical|clinic|hospital|medicine|medication|pharmacy|therapy|bank|credit|insurance|"
    r"identity|passport|school|child|children|kids|kid|baby|toddler|infant|"
    r"youth|juvenile|minor|rx|prescription)\b", re.I
)
_SHIPMENT_KEYS = {"shipment_id", "carrier_code", "status", "status_code",
                  "is_active", "company", "item", "label_source"}
_DETAIL_KEYS = {"expected_delivery", "latest_event"}
_EXPECTED_KEYS = {"date", "time", "end_date", "end_time", "timezone", "source"}
_EVENT_KEYS = {"status", "date", "time", "timezone", "source"}
_EVENTS = {
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
_STATUSES = {
    "delivered": "delivered",
    "frozen": "frozen",
    "in_transit": "in transit",
    "awaiting_pickup": "awaiting pickup",
    "out_for_delivery": "out for delivery",
    "not_found": "not found",
    "failed_attempt": "failed delivery attempt",
    "exception": "delivery exception",
    "information_received": "shipping information received",
}


def _label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not _LABEL.fullmatch(value) or _SENSITIVE.search(value):
        return None
    return value


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _day(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"20\d\d-\d\d-\d\d", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _clock(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is not None


def _expected(value: object) -> dict | None:
    if not isinstance(value, dict) or set(value) != _EXPECTED_KEYS:
        return None
    day, time = value["date"], value["time"]
    end_day, end_time = value["end_date"], value["end_time"]
    if (not _day(day) or time is not None and not _clock(time)
            or end_day is not None and not _day(end_day)
            or end_time is not None and (not _clock(end_time) or end_day is None)
            or value["timezone"] not in (None, "UTC")
            or value["source"] != "parcel_api"
            or end_day is not None and (end_day < day or
                                        end_day == day and time is not None and
                                        end_time is not None and end_time < time)):
        return None
    return value


def _event(value: object) -> dict | None:
    if (not isinstance(value, dict) or set(value) != _EVENT_KEYS
            or not isinstance(value["status"], str) or value["status"] not in _EVENTS
            or not _day(value["date"])
            or value["time"] is not None and not _clock(value["time"])
            or value["timezone"] not in (None, "UTC")
            or value["source"] != "parcel_api"):
        return None
    return value


def _status(entry: dict) -> str:
    code = entry.get("status_code")
    value = entry.get("status")
    if (isinstance(code, int) and not isinstance(code, bool) and 0 <= code <= 8
            and isinstance(value, str) and value in _STATUSES):
        return _STATUSES[value]
    return "status unavailable"


def _count(value: object, maximum: int | None = None) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool) and value >= 0
            and (maximum is None or value <= maximum))


def packages_block(snapshot_path: str | None, *, as_of: date | None = None,
                   now: datetime | None = None) -> dict | None:
    """Return display-only records from a fresh, owner-private snapshot.

    A separate owner-only handoff writes the sanitized connector result.
    This reader never queries Parcel or Gmail.
    """
    if not snapshot_path or (as_of is not None and as_of != date.today()):
        return None
    path = Path(snapshot_path).expanduser()
    if not path.is_absolute():
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_size > 65536):
                return None
            data = json.load(source)
    except (OSError, UnicodeError, ValueError):
        return None
    return summary_block(data, now=now)


def summary_block(data: object, *, now: datetime | None = None) -> dict | None:
    """Validate one v1 Parcel summary and return display-only records.

    Shared by the private snapshot reader and the direct Parcel API reader,
    so both sources pass through the same allowlists.
    """
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("source") != "parcel_cache"
            or data.get("fresh_for_seconds") != 7200
            or data.get("max_age_seconds") != 86400
            or data.get("reason") not in (None, "cache_missing", "cache_timestamp_invalid", "cache_expired")
            or not isinstance(data.get("truncated"), bool)
            or not isinstance(data.get("shipments"), list)
            or len(data["shipments"]) > 100):
        return None
    generated = _timestamp(data.get("generated_at"))
    cache_time = _timestamp(data.get("as_of"))
    clock = now or datetime.now(timezone.utc)
    freshness = data.get("freshness")
    if (generated is None or clock.tzinfo is None
            or freshness not in ("fresh", "stale", "unavailable")
            or generated > clock + timedelta(minutes=5)
            or clock - generated > timedelta(hours=24)):
        return None
    if freshness != "unavailable" and (cache_time is None
            or not _count(data.get("cache_age_seconds"))
            or cache_time > generated + timedelta(minutes=5)
            or clock - cache_time > timedelta(hours=24)
            or (freshness == "fresh" and clock - cache_time > timedelta(hours=2))):
        return None
    coverage = data.get("coverage")
    if (not isinstance(coverage, dict)
            or coverage.get("scope") != "recent_and_active_cache"
            or coverage.get("counts_scope") != "returned_shipments"
            or not isinstance(coverage.get("complete"), bool)
            or not isinstance(coverage.get("can_state_no_active"), bool)
            or not _count(coverage.get("returned_count"), 100)
            or (data.get("total_cached") is not None and not _count(data.get("total_cached")))):
        return None
    if freshness == "unavailable":
        return {"shipments": [], "freshness": "unavailable", "truncated": False,
                "no_active": False, "coverage_note": "Parcel package coverage is unavailable."}

    result = []
    unlabeled_statuses = {}
    invalid_entries = 0
    for entry in data["shipments"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("shipment_id"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["shipment_id"])
                or not isinstance(entry.get("carrier_code"), str)
                or not re.fullmatch(r"[a-z0-9]{2,40}", entry["carrier_code"])
                or not (entry.get("is_active") is True or entry.get("is_active") is False
                        or entry.get("is_active") is None)
                or entry.get("label_source") not in ("trusted_validated_ingest", None)):
            invalid_entries += 1
            continue
        if entry["is_active"] is not True:
            continue
        if (set(entry) & _DETAIL_KEYS and
                (not _SHIPMENT_KEYS <= set(entry) or
                 not set(entry) <= _SHIPMENT_KEYS | _DETAIL_KEYS)):
            invalid_entries += 1
            continue
        expected = _expected(entry.get("expected_delivery"))
        event = _event(entry.get("latest_event"))
        if ((entry.get("expected_delivery") is not None and expected is None)
                or (entry.get("latest_event") is not None and event is None)):
            invalid_entries += 1
            continue
        status = _status(entry)
        trusted = entry["label_source"] == "trusted_validated_ingest"
        company = _label(entry.get("company")) if trusted else None
        item = _label(entry.get("item")) if company else None
        if not company:
            unlabeled_statuses[status] = unlabeled_statuses.get(status, 0) + 1
        row = {
            "carrier_code": entry["carrier_code"],
            "company": company,
            "item": item,
            "status": status,
            "estimated_delivery": None,
            "tracking_url": None,
        }
        if "expected_delivery" in entry:
            row["expected_delivery"] = expected
        if "latest_event" in entry:
            row["latest_event"] = ({"status": _EVENTS[event["status"]],
                                    "date": event["date"], "time": event["time"],
                                    "timezone": event["timezone"]}
                                   if event else None)
        result.append(row)
    returned_count = coverage["returned_count"]
    incomplete = (not coverage["complete"] or data["truncated"] or invalid_entries > 0
                  or returned_count != len(data["shipments"])
                  or any(not _count(coverage.get(key)) or coverage[key] > 0 for key in (
                      "unlabeled_count", "unknown_status_count",
                      "active_membership_unknown_count"))
                  or (data["total_cached"] is not None and data["total_cached"] > returned_count))
    no_active = (freshness == "fresh" and coverage["can_state_no_active"] is True
                 and not incomplete and not result
                 and coverage.get("active_cached_count") == 0
                 and not any(isinstance(entry, dict) and entry.get("is_active") is not False
                             for entry in data["shipments"]))
    note = ("Other package details may be missing; check Parcel."
            if incomplete else "Package status is uncertain; check Parcel.")
    result.sort(key=lambda shipment: shipment["company"] is None)
    return {"shipments": result[:20], "freshness": freshness,
            "as_of": cache_time.isoformat(),
            "truncated": data["truncated"] or len(result) > 20,
            "no_active": no_active,
            "unlabeled_statuses": unlabeled_statuses,
            "coverage_note": note if incomplete or (not result and not no_active) else None}
