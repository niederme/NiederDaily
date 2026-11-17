"""Read active deliveries straight from the Parcel API.

The API key lives only in the macOS login Keychain (generic password, service
``niederdaily.parcel-api``). It is read with /usr/bin/security at run time,
sent only in Parcel's ``api-key`` header, and never logged or stored.

The raw API response is reduced to the same v1 summary the private snapshot
uses, then validated by ``modules.packages.summary_block``. Tracking numbers,
locations, extra carrier text, and raw event strings never leave this module.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import requests

from modules.packages import _label, _expected, _event, packages_block, summary_block


KEYCHAIN_SERVICE = "niederdaily.parcel-api"
API_URL = "https://api.parcel.app/external/deliveries/"
MAX_SHIPMENTS = 100
_LOCAL_ZONE = ZoneInfo("America/New_York")

_STATUS_NAMES = {
    0: "delivered",
    1: "frozen",
    2: "in_transit",
    3: "awaiting_pickup",
    4: "out_for_delivery",
    5: "not_found",
    6: "failed_attempt",
    7: "exception",
    8: "information_received",
}

# Ordered: the first matching phrase wins, so negative or attempt wording is
# checked before the plain "delivered" match.
_EVENT_PHRASES = (
    (("not delivered", "undelivered", "undeliverable", "delivery attempt", "attempted delivery",
      "attempted", "missed delivery"), "delivery_attempted"),
    (("out for delivery", "on vehicle for delivery", "with delivery courier"), "out_for_delivery"),
    (("ready for pickup", "available for pickup", "ready for collection"), "available_for_pickup"),
    (("exception",), "delivery_exception"),
    (("customs",), "customs_clearance"),
    (("delivered",), "delivered"),
    (("arrived at", "arrival at"), "arrived_at_facility"),
    (("departed", "left the facility", "left facility"), "departed_facility"),
    (("label created", "shipping label created", "label has been created"), "label_created"),
    (("in transit",), "in_transit"),
)

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%B %d, %Y %I:%M %p", "%b %d, %Y %I:%M %p", "%B %d, %Y", "%b %d, %Y",
    "%B %d, %Y %H:%M", "%b %d, %Y %H:%M",
    "%d.%m.%Y %H:%M", "%d.%m.%Y",
)
# Carrier event strings such as "Saturday, November 7 9:19 AM" omit the year.
_YEARLESS_FORMATS = (
    "%A, %B %d %I:%M %p", "%A, %b %d %I:%M %p", "%A, %B %d %H:%M", "%A, %B %d",
    "%B %d %I:%M %p", "%b %d %I:%M %p", "%B %d",
)


class ParcelAPIError(RuntimeError):
    """Parcel answered, but not with a usable delivery list."""


def read_api_key(service: str = KEYCHAIN_SERVICE) -> str | None:
    """Return the Parcel API key from the login Keychain, or None if absent."""
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    key = result.stdout.strip() if result.returncode == 0 else ""
    return key or None


def fetch_deliveries(api_key: str, *, session=requests, timeout: float = 15) -> list:
    """Return Parcel's active deliveries. Parcel allows 20 calls per hour."""
    # Requests preserves custom API-key headers on redirects. Reject every
    # redirect instead of risking disclosure to a different destination.
    response = session.get(API_URL, params={"filter_mode": "active"},
                           headers={"api-key": api_key}, timeout=timeout,
                           allow_redirects=False)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if (response.status_code != 200 or not isinstance(payload, dict)
            or payload.get("success") is not True
            or not isinstance(payload.get("deliveries"), list)):
        # Parcel's error_message is not logged verbatim; it could echo input.
        raise ParcelAPIError(f"Parcel API request failed (HTTP {response.status_code})")
    return payload["deliveries"]


def _carrier(value: object) -> str:
    code = re.sub(r"[^a-z0-9]", "", value.lower()) if isinstance(value, str) else ""
    return code[:40] if len(code) >= 2 else "unknown"


def _yearless(text: str, fmt: str, today: date) -> datetime | None:
    """Parse a date without a year, choosing the year that keeps it recent."""
    for year in (today.year, today.year - 1):
        try:
            parsed = datetime.strptime(f"{year} {text}", f"%Y {fmt}")
        except ValueError:
            continue
        # A weekday that doesn't match this year means the wrong year.
        if "%A" in fmt and parsed.strftime("%A").lower() != text.split(",")[0].strip().lower():
            continue
        if (parsed.date() - today).days <= 31:
            return parsed
    return None


def _parse_local(value: object, today: date | None = None) -> tuple[str, str | None] | None:
    """Parse Parcel's timezone-free date string into (YYYY-MM-DD, HH:MM|None)."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    candidates = []
    for fmt in _DATE_FORMATS:
        try:
            candidates.append((datetime.strptime(text, fmt), fmt))
        except ValueError:
            continue
    if not candidates and today is not None:
        for fmt in _YEARLESS_FORMATS:
            parsed = _yearless(text, fmt, today)
            if parsed:
                candidates.append((parsed, fmt))
    if not candidates:
        return None
    parsed, fmt = candidates[0]
    has_time = "%H" in fmt or "%I" in fmt
    clock = parsed.strftime("%H:%M") if has_time else None
    # Parcel pads date-only estimates with midnight; never invent a time.
    if clock == "00:00":
        clock = None
    return parsed.strftime("%Y-%m-%d"), clock


def _parse_epoch(value: object) -> tuple[str, str] | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    seconds = value / 1000 if value > 1e11 else value
    try:
        moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M")


def _expected_delivery(delivery: dict) -> dict | None:
    start = _parse_epoch(delivery.get("timestamp_expected"))
    if start:
        end = _parse_epoch(delivery.get("timestamp_expected_end"))
        zone = "UTC"
    else:
        start = _parse_local(delivery.get("date_expected"))
        end = _parse_local(delivery.get("date_expected_end"))
        zone = None
    if not start:
        return None
    value = {"date": start[0], "time": start[1],
             "end_date": end[0] if end else None, "end_time": end[1] if end else None,
             "timezone": zone, "source": "parcel_api"}
    return _expected(value)


def _latest_event(delivery: dict, today: date) -> dict | None:
    events = delivery.get("events")
    if not isinstance(events, list) or not events or not isinstance(events[0], dict):
        return None
    text = events[0].get("event")
    when = _parse_local(events[0].get("date"), today)
    if not isinstance(text, str) or not when:
        return None
    lowered = text.lower()
    status = next((name for phrases, name in _EVENT_PHRASES
                   if any(phrase in lowered for phrase in phrases)), None)
    if status is None:
        return None
    return _event({"status": status, "date": when[0], "time": when[1],
                   "timezone": None, "source": "parcel_api"})


def build_summary(deliveries: list, *, now: datetime | None = None) -> dict:
    """Reduce raw Parcel deliveries to the v1 display summary."""
    clock = now or datetime.now(timezone.utc)
    stamp = clock.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    shipments = []
    unknown_status = 0
    for delivery in deliveries[:MAX_SHIPMENTS]:
        if not isinstance(delivery, dict):
            continue
        code = delivery.get("status_code")
        valid_code = isinstance(code, int) and not isinstance(code, bool) and code in _STATUS_NAMES
        if not valid_code:
            unknown_status += 1
        carrier = _carrier(delivery.get("carrier_code"))
        tracking = delivery.get("tracking_number")
        ident = hashlib.sha256(f"{carrier}:{tracking}".encode()).hexdigest()
        # The owner's own Parcel description is the label; the reader re-applies
        # the format and sensitive-term checks before anything is shown.
        label = _label(delivery.get("description"))
        shipments.append({
            "shipment_id": ident,
            "carrier_code": carrier,
            "status": _STATUS_NAMES[code] if valid_code else "unknown",
            "status_code": code if valid_code else None,
            "is_active": True,
            "company": label,
            "item": None,
            "label_source": "trusted_validated_ingest" if label else None,
            "expected_delivery": _expected_delivery(delivery),
            "latest_event": _latest_event(delivery, clock.astimezone(_LOCAL_ZONE).date()),
        })
    return {
        "schema_version": 1,
        "source": "parcel_cache",
        "generated_at": stamp,
        "freshness": "fresh",
        "as_of": stamp,
        "cache_age_seconds": 0,
        "fresh_for_seconds": 7200,
        "max_age_seconds": 86400,
        "reason": None,
        "total_cached": len(deliveries),
        "truncated": len(deliveries) > MAX_SHIPMENTS,
        "coverage": {
            "scope": "recent_and_active_cache",
            "complete": True,
            "returned_count": len(shipments),
            # A missing description is a normal Parcel row, not a coverage gap.
            "unlabeled_count": 0,
            "unknown_status_count": unknown_status,
            "counts_scope": "returned_shipments",
            "active_cached_count": len(shipments),
            "active_membership_unknown_count": 0,
            "can_state_no_active": True,
        },
        "shipments": shipments,
    }


def live_packages_block(snapshot_path: str | None, *, as_of: date | None = None,
                        now: datetime | None = None, load_key=read_api_key,
                        fetch=fetch_deliveries) -> dict | None:
    """Prefer the Parcel API; fall back to the private snapshot if it is unusable."""
    if as_of is not None and as_of != date.today():
        return None
    api_key = load_key()
    if api_key:
        try:
            block = summary_block(build_summary(fetch(api_key), now=now), now=now)
        except (requests.RequestException, ParcelAPIError, ValueError) as error:
            logging.warning("Parcel API unavailable (%s); trying snapshot.", type(error).__name__)
        else:
            if block is not None:
                logging.info("Packages read from the Parcel API.")
                return {**block, "refresh_succeeded": True}
            logging.warning("Parcel API summary failed validation; trying snapshot.")
    else:
        logging.info("No Parcel API key in Keychain; using snapshot if present.")
    snapshot = packages_block(snapshot_path, as_of=as_of, now=now)
    if snapshot is None:
        snapshot = {"shipments": [], "freshness": "unavailable", "truncated": False,
                    "no_active": False, "coverage_note": None}
    # A usable cache stays visible, but it is not a successful current refresh.
    # Preserve the validated source timestamp and every existing uncertainty note.
    note = snapshot.get("coverage_note")
    if snapshot.get("no_active") and not note:
        note = "Current package status is unavailable."
    return {**snapshot, "refresh_succeeded": False, "no_active": False,
            "coverage_note": note}
