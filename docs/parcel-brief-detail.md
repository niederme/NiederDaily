# Parcel package detail handoff

The owner-only cloud producer can add two optional, nullable fields to each
shipment in the existing `schema_version: 1` summary. The v1 envelope and its
other shipment fields stay unchanged. The local writer and reader accept both
the original shape and the optional fields.

`expected_delivery` has exactly these keys: `date`, `time`, `end_date`,
`end_time`, `timezone`, `source`. `date` is a valid `YYYY-MM-DD` string;
`time` is `HH:MM` or null. `end_date` and `end_time` use those same formats or
are null, with the end not earlier than the start. `timezone` is null for
Parcel's timezone-free date/time string, or `UTC` only when an explicit source
timezone or valid epoch was converted to UTC. `source` is `parcel_api`. An
actual Parcel date or timestamp must support each populated value; do not infer
an estimate from status or from a screenshot.

`latest_event` has exactly these keys: `status`, `date`, `time`, `timezone`,
`source`. `status` is one of `delivered`, `out_for_delivery`,
`delivery_attempted`, `available_for_pickup`, `arrived_at_facility`,
`departed_facility`, `in_transit`, `label_created`, `customs_clearance`, or
`delivery_exception`. `date` is required and `time` may be null.
`timezone` is null or `UTC` under the same source rule as the estimate;
`source` is `parcel_api`. Classify an actual dated carrier event only when it
clearly matches a generic status; do not substitute aggregate shipment status.
Omit arbitrary carrier event text, locations, and additional data.

The existing `company` and `item` fields still require
`label_source: "trusted_validated_ingest"`. Only previously verified,
sharing-safe metadata can set that source. Sensitive or child-specific items
must be null while a safe company can remain. Do not infer labels from Parcel
descriptions, hashes, or screenshot row order. Unknown estimates and events
stay null.

The shipment object has no URL, tracking number, address, raw event, or email
field. The writer rejects extra fields or malformed values; the reader
independently rejects malformed entries. The handoff continues to use the
same private snapshot, existing schedule, and owner-only recipient.

For display, a populated UTC date and time is converted to
`America/New_York`, including date rollover, and labeled `ET`. A timezone-free
time is shown as provided with a “time zone not provided” note. Date-only
estimates remain dates; the renderer never invents midnight or changes their
calendar day.
