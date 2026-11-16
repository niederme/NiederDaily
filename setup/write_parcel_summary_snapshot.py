#!/usr/bin/env python3
"""Store one fresh, sanitized owner-only Parcel tool result for NiederDaily.

Accepts JSON on stdin. Never queries Parcel, Gmail, or credentials.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


MAX_BYTES = 65536
TOP_KEYS = {"schema_version", "source", "generated_at", "freshness", "as_of",
            "cache_age_seconds", "fresh_for_seconds", "max_age_seconds", "reason",
            "total_cached", "truncated", "coverage", "shipments"}
COVERAGE_KEYS = {"scope", "complete", "returned_count", "unlabeled_count",
                 "unknown_status_count", "counts_scope", "active_cached_count",
                 "active_membership_unknown_count", "can_state_no_active"}
SHIPMENT_KEYS = {"shipment_id", "carrier_code", "status", "status_code",
                 "is_active", "company", "item", "label_source"}
DETAIL_KEYS = {"expected_delivery", "latest_event"}
EXPECTED_KEYS = {"date", "time", "end_date", "end_time", "timezone", "source"}
EVENT_KEYS = {"status", "date", "time", "timezone", "source"}
EVENT_STATUSES = {"delivered", "out_for_delivery", "delivery_attempted",
                  "available_for_pickup", "arrived_at_facility",
                  "departed_facility", "in_transit", "label_created",
                  "customs_clearance", "delivery_exception"}
STATUSES = {"delivered", "frozen", "in_transit", "awaiting_pickup",
            "out_for_delivery", "not_found", "failed_attempt", "exception",
            "information_received", "unknown"}


def _count(value, maximum=None):
    return (type(value) is int and value >= 0
            and (maximum is None or value <= maximum))


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("invalid timestamp")
    return parsed.astimezone(timezone.utc)


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"20\d\d-\d\d-\d\d", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _clock(value):
    return isinstance(value, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is not None


def _expected(value):
    if value is None:
        return True
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        return False
    day, time = value["date"], value["time"]
    end_day, end_time = value["end_date"], value["end_time"]
    if (not _day(day) or (time is not None and not _clock(time))
            or (end_day is not None and not _day(end_day))
            or (end_time is not None and (not _clock(end_time) or end_day is None))
            or value["timezone"] not in (None, "UTC")
            or value["source"] != "parcel_api"):
        return False
    if end_day is not None and (end_day < day or
                                end_day == day and time is not None and
                                end_time is not None and end_time < time):
        return False
    return True


def _event(value):
    return (value is None or isinstance(value, dict) and set(value) == EVENT_KEYS
            and isinstance(value["status"], str) and value["status"] in EVENT_STATUSES
            and _day(value["date"])
            and (value["time"] is None or _clock(value["time"]))
            and value["timezone"] in (None, "UTC")
            and value["source"] == "parcel_api")


def validate(data, *, now=None):
    """Reject envelopes, extra fields, stale/incomplete snapshots, and raw data."""
    if not isinstance(data, dict) or set(data) != TOP_KEYS:
        raise ValueError("invalid summary envelope")
    if (type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["source"] != "parcel_cache" or data["freshness"] != "fresh"
            or data["fresh_for_seconds"] != 7200 or data["max_age_seconds"] != 86400
            or data["reason"] is not None or data["truncated"] is not False
            or not _count(data["cache_age_seconds"], 7200)):
        raise ValueError("summary is unavailable or incomplete")
    clock = now or datetime.now(timezone.utc)
    generated, cache_time = _timestamp(data["generated_at"]), _timestamp(data["as_of"])
    if (generated > clock + timedelta(minutes=5)
            or clock - generated > timedelta(minutes=10)
            or cache_time > generated + timedelta(minutes=5)
            or clock - cache_time > timedelta(hours=2)):
        raise ValueError("summary is not current")
    shipments, coverage = data["shipments"], data["coverage"]
    if (not isinstance(shipments, list) or len(shipments) > 100
            or not _count(data["total_cached"])
            or data["total_cached"] != len(shipments)
            or not isinstance(coverage, dict) or set(coverage) != COVERAGE_KEYS
            or coverage["scope"] != "recent_and_active_cache"
            or coverage["counts_scope"] != "returned_shipments"
            or coverage["complete"] is not True
            or not _count(coverage["returned_count"], 100)
            or coverage["returned_count"] != len(shipments)
            or type(coverage["can_state_no_active"]) is not bool):
        raise ValueError("summary coverage is incomplete")
    for key in ("unlabeled_count", "unknown_status_count", "active_cached_count",
                "active_membership_unknown_count"):
        if not _count(coverage[key]):
            raise ValueError("summary coverage is invalid")
    for entry in shipments:
        if (not isinstance(entry, dict) or not SHIPMENT_KEYS <= set(entry)
                or not set(entry) <= SHIPMENT_KEYS | DETAIL_KEYS):
            raise ValueError("invalid shipment fields")
        if (not isinstance(entry["shipment_id"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["shipment_id"])
                or not isinstance(entry["carrier_code"], str)
                or not re.fullmatch(r"[a-z0-9]{2,40}", entry["carrier_code"])
                or entry["status"] not in STATUSES
                or not (entry["status_code"] is None or _count(entry["status_code"], 8))
                or not (entry["is_active"] is None or type(entry["is_active"]) is bool)
                or not (entry["company"] is None or isinstance(entry["company"], str))
                or not (entry["item"] is None or isinstance(entry["item"], str))
                or entry["label_source"] not in (None, "trusted_validated_ingest")):
            raise ValueError("invalid shipment summary")
        if (not _expected(entry.get("expected_delivery"))
                or not _event(entry.get("latest_event"))):
            raise ValueError("invalid shipment detail")
    return data


def write_snapshot(data, target: Path):
    validate(data)
    target = target.expanduser()
    if not target.is_absolute():
        raise ValueError("snapshot path must be absolute")
    parent = target.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = parent.stat()
    if (parent.is_symlink() or info.st_uid != os.getuid()
            or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077):
        raise ValueError("snapshot directory is not private")
    payload = (json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    if len(payload) > MAX_BYTES:
        raise ValueError("snapshot is too large")
    lock_fd = os.open(parent / ".parcel-summary.lock",
                      os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        lock_info = os.fstat(lock_fd)
        if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid()
                or lock_info.st_mode & 0o077):
            raise ValueError("snapshot lock is not private")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            try:
                existing_fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                existing_fd = None
            if existing_fd is not None:
                with os.fdopen(existing_fd, "r", encoding="utf-8") as source:
                    existing_info = os.fstat(source.fileno())
                    if (not stat.S_ISREG(existing_info.st_mode)
                            or existing_info.st_uid != os.getuid()
                            or existing_info.st_mode & 0o077
                            or existing_info.st_size > MAX_BYTES):
                        raise ValueError("existing snapshot is not private")
                    previous = json.load(source)
                if (not isinstance(previous, dict)
                        or previous.get("schema_version") != 1
                        or previous.get("source") != "parcel_cache"):
                    raise ValueError("existing snapshot cannot be ordered")
                previous_order = (_timestamp(previous.get("as_of")),
                                  _timestamp(previous.get("generated_at")))
                incoming_order = (_timestamp(data["as_of"]),
                                  _timestamp(data["generated_at"]))
                if previous_order >= incoming_order:
                    raise ValueError("snapshot is older than the stored summary")
            temporary = parent / (".parcel-summary-" + uuid.uuid4().hex)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, target)
                directory_fd = os.open(parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary.exists():
                    temporary.unlink()
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path.home() / ".niederdaily" / "parcel" / "summary.json")
    args = parser.parse_args()
    raw = sys.stdin.buffer.readline(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SystemExit("Parcel summary rejected: too large")
    try:
        write_snapshot(validate(json.loads(raw)), args.output)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise SystemExit("Parcel summary rejected; no snapshot written")
    print("Fresh private Parcel summary saved.")


if __name__ == "__main__":
    main()
