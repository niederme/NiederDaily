# NiederDaily

NiederDaily is a macOS-native personal morning email digest for one person and one machine.
Each run pulls from local apps and a few network services to assemble a single editorial-style email that is useful at a glance and lightweight to maintain.

It currently combines:

- local calendar events
- local reminders
- local Photos "On This Day" memories
- local Messages context from `chat.db`
- home weather, plus travel weather when a trip calendar location points elsewhere
- a short Claude-written welcome line
- New York Times Top Stories

An optional Packages section reads active deliveries straight from the
Parcel API (`api.parcel.app/external/deliveries/?filter_mode=active`, one call
per run against Parcel's 20-per-hour limit). The API key lives only in the
macOS login Keychain as a generic password with service
`niederdaily.parcel-api`; `modules/parcel_api.py` reads it with
`/usr/bin/security`, sends it only in the `api-key` header, and never logs or
stores it. Store or replace it with (the trailing `-w` prompts for the key so
it stays out of shell history):

```bash
security add-generic-password -U -s niederdaily.parcel-api -a "$USER" -T /usr/bin/security -w
```

The API response is reduced to the v1 summary below before display: tracking
numbers become a one-way hash, and locations, extra information, and raw event
text are dropped. Each delivery's own Parcel description is used as its label,
still subject to the sensitive-term check. If the key is missing or the API
call fails, NiederDaily falls back to the legacy snapshot at
`--parcel-snapshot ~/.niederdaily/parcel/summary.json`, which
the existing 05:55 LaunchAgent still passes. A missing or expired snapshot
leaves the section out.

The handoff is a 0600 owner-owned JSON file at the absolute path above,
written atomically by `setup/write_parcel_summary_snapshot.py` from the
owner-only tool result. It must be at most 64 KiB and contain the tool's
version 1 schema. The writer rejects an older `as_of` or an older generation
for the same `as_of`, so out-of-order results cannot replace a newer snapshot.
The [synthetic contract fixture](tests/fixtures/parcel_brief_summary_v1.json)
shows the exact required fields, including freshness and coverage bounds.

The reader shows one row per `is_active: true` shipment, including its carrier
and delivery status. Company and item labels appear only when `label_source`
is `trusted_validated_ingest` and pass an additional sensitive-term check. Carrier
accents are FedEx magenta, UPS brown, Amazon orange, DHL gold, and USPS blue;
unknown carriers use black. Each carrier name matches its dot color. It
uses a documented status only when `status_code` is 0–8 and the status text is
recognized; otherwise it says “Status unavailable.” The v1 contract also
accepts optional, nullable `expected_delivery` and `latest_event` objects
from a validated cloud producer. The exact safe shapes are in
[the package detail handoff](docs/parcel-brief-detail.md). The renderer puts a
trusted company and benign item first, then status, any actual expected date
or window, any safe latest event, and the carrier with matching dot and text
color. No tracking link or raw event text enters the handoff. A `stale` cache
under 24 hours receives an explicit warning; `unavailable` produces a coverage
notice, while older or invalid data is omitted. The section shows at most 20
entries and notes incomplete, unlabeled, unknown, or truncated coverage. It
says “No active packages” only when the fresh, complete result explicitly sets
`coverage.can_state_no_active`. Unknown fields, including raw messages and
addresses, are never rendered. Before setting `parcel_snapshot_path` in the
private runtime config, verify that the recipient is the owner alone and that a
supported read-only producer writes this schema. Historical `--date` sends omit
live package data.

For a one-time owner-only test with a real sanitized owner-only result, set
`test_recipient` in the private config to the same address as `recipient_email`
(the test refuses to send if it is missing or differs), then pass
`--parcel-snapshot /absolute/private/path.json --test-packages` through the
existing NiederDaily.app `--run` launch. The test flag requires a fresh package
section and core modules, marks the subject and HTML, and disables automatic
send retries. Check Gmail Sent before any manual retry after an uncertain send.
The launcher forwards these flags to Python without modifying the recurring
configuration or rebuilding the app.

The current branch also includes a substantial visual refresh so the email feels closer to the `nieder.me/2026` editorial style on desktop and mobile.

## Highlights

- machine-local by default: most inputs come straight from macOS apps and permissions
- graceful degradation: if a module fails, the digest still sends and omits that section
- scheduled-run friendly: includes a wrapper app plus `launchd` template for more reliable TCC permissions
- context-rich output: weather summary, reminder urgency, reply-needed signal, and photo metadata surface in a skim-friendly layout
- click-through actions: calendar items and reminders can jump back into local workflows through Shortcuts deep links

## What It Does

Each run builds an email with some or all of these modules:

- `Welcome`
- `Weather`
- `Calendar`
- `Reminders`
- `Messages`
- `On This Day`
- `Tweet of the Day`
- `New York Times Top Stories`

If a module fails, the send can still continue. The app logs the failure and omits that section rather than killing the whole newsletter.

## Requirements

- macOS
- Python 3.10+ recommended
- Gmail API credentials for sending
- Anthropic API key for the welcome line
- New York Times API key
- local access to Calendar, Reminders, Photos, Contacts, Messages, and Shortcuts as needed
- optional: [`birdclaw`](https://birdclaw.sh) CLI (`brew install steipete/tap/birdclaw`) with a synced archive/likes/bookmarks for the Tweet of the Day module

Python dependencies live in [`requirements.txt`](requirements.txt):

- `anthropic`
- `google-auth-oauthlib`
- `google-api-python-client`
- `requests`
- `pyobjc-framework-AddressBook`
- `pyobjc-framework-Contacts`
- `pyobjc-framework-EventKit`
- `pyobjc-framework-Photos`

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
```

Or use the installer:

```bash
./setup/install.sh
```

### 2. Create config

Create `~/.niederdaily/config.json`:

```json
{
  "recipient_email": "you@example.com",
  "test_recipient": "you@example.com",
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "YOUR_NYT_KEY",
  "anthropic_api_key": "YOUR_ANTHROPIC_KEY",
  "reminders_lists": ["Little York", "Bills", "Niedertodo", "Subscriptions", "Ben", "Jack"],
  "calendars": [],
  "calendar_hide_from_list": [],
  "weather_calendars": ["Little York", "niederCal", "TripIt"],
  "weather_travel_min_miles": 25
}
```

Required keys are defined in [`config.py`](config.py). Calendar and weather calendar lists are optional filters.

`calendar_hide_from_list` names calendars that are still read (they inform the opening, location and travel weather) but are left out of the email's Calendar list, matched case-insensitively against the configured calendar name, e.g. `["Work", "Deliveries", "Birthdays"]`. The list also always omits commute timetable legs (`commute.transit_lines`) and bare "Travel"/"Commute" holds.

The reminder list example includes the shared `Ben` and `Jack` lists alongside the existing household lists. Reminder items retain their list names so each child's tasks can be identified. An empty `reminders_lists` array includes all available lists. The active configuration lives outside Git at `~/.niederdaily/config.json`.

Travel weather is included only for destinations more than `weather_travel_min_miles` from `default_location` (default: 25 miles, measured in a straight line). Nearby appointments, including Goshen, use the home forecast. Existing calendar, sports-event, and excluded-city filters still apply.

### Personal conventions (optional)

The opening paragraph knows nothing about you until you tell it. Every personal convention lives in `config.json`; the code ships neutral defaults (the reader is called "the reader", nobody else is in the household, there is no commute, and no calendar entry places you anywhere). All keys are optional:

```json
{
  "owner_name": "Jordan",
  "owner_full_name": "Jordan Doe",
  "employer": "Acme",
  "day_marker_prefixes": ["JD"],
  "home_keywords": ["home", "wfh", "springfield"],
  "home_label": "Springfield",
  "household_prefixes": {"AB": "Alex"},
  "own_calendars": ["Home", "Work"],
  "calendar_aliases": {"Work": {"title": "Calendar", "source_type": "exchange"}},
  "event_context": {"Dr. Lee": "Dr. Lee is Jordan's therapist; the session is a weekly appointment."},
  "routine_event_keywords": ["school bus"],
  "appointment_aliases": {"therapy": ["Dr. Lee"], "therapist": ["Dr. Lee"]},
  "prompt_notes": ["The rent reminder is Jordan paying Alex back; the rent itself is paid."],
  "reminders_suppressed_titles": ["Morning pills"],
  "reminder_title_overrides": [{"title": "Check filter!", "list": "Home", "newsletter_title": "Replace the furnace filter!"}],
  "commute": {
    "city": "Boston",
    "city_aliases": ["BOS"],
    "location_keywords": ["Boston, MA", "South Station"],
    "transit_lines": ["Metro"],
    "mode": "bus",
    "depart": "7:05am",
    "home": "7:40pm",
    "arrival_stop": "Springfield"
  },
  "opening_history_path": "~/.niederdaily/state/opening_mentions.json"
}
```

- `owner_name` / `owner_full_name`: how the opening refers to you, and whose birthday counts as yours.
- `employer`: named when work reminders give context.
- `day_marker_prefixes`: all-day events titled `<PREFIX>: <place>` (or `<PREFIX> in <place>`) say where you are that day, and they are the only calendar signal that does. A place in `home_keywords` is a home day, a `commute.city` or one of its `city_aliases` is a commute day, anything else is a trip. With no marker or other evidence, the opening is told your location is unknown and never assumes you are home.
- `home_label`: how your home is named in the location line.
- `household_prefixes`: title prefixes for other people's items (`"AB: Dentist"` belongs to Alex). They are household awareness, not your tasks, and never place you anywhere.
- `own_calendars`: the calendars that are yours rather than subscriptions. No event places you anywhere by its location: work meetings are often virtual even when the invite names the office, and event places in the commute city (`commute.location_keywords`) are kept out of the opening unless a marker puts you there.
- `calendar_aliases`: configured calendar names that are not EventKit titles. `source_type: "exchange"` requires the calendar to live on an Exchange account; `null` matches any account. Calendar names otherwise match exactly, then by a single case-insensitive match; unmatched or ambiguous names are skipped with a logged warning.
- `event_context`: title substring to a sentence of context about a recurring person or event, added to the prompt when the title appears.
- `routine_event_keywords`: events whose titles contain these are ranked as low-interest background.
- `appointment_aliases`: calendar title keywords that substantiate an appointment word in the opening (otherwise "therapy" must appear in a title).
- `prompt_notes`: extra household facts appended to the opening's instructions.
- `reminders_suppressed_titles`: reminders kept in Apple Reminders but left out of the newsletter. `reminder_title_overrides` clarifies a terse title in the newsletter only (optionally scoped to one list); the source reminder is never changed.
- `commute`: the commute city and how to read its timetable. Events titled `<transit line> <number> Inbound|Outbound` are timetable options, not bookings: they never place you in the city on their own; on a day marked as a commute day they refine the departure and return. `depart` / `home` are the usual times used when the calendar has a commute-day marker but no timetable events. Commute details only decide where you are: the opening never mentions buses or trains, lines, stops, or departure and return times, and a draft that does (including any `transit_lines` or `arrival_stop` name) is rejected.
- `opening_history_path`: where the opening records which reminders it mentioned, so the same item is not raised again for a week. Only a real daily send (not a `--date` run) reads or writes it.
- `opening_rejections_path` (default `~/.niederdaily/state/opening_rejections.jsonl`): when the opening's checks reject a draft, the draft and the reason are kept here (owner-only, last 60) so a missing opening can be diagnosed. The shared log only records reason codes. Each retry tells the model why the earlier draft was rejected.

### 3. Add Gmail OAuth credentials

Place your Google OAuth client secret at:

```bash
~/.niederdaily/client_secret.json
```

The token will be created at:

```bash
~/.niederdaily/token.json
```

### 4. Run preflight

```bash
./.venv/bin/python niederdaily.py --preflight
```

Preflight checks:

- config loading
- Calendar access
- Reminders access
- Photos access
- Messages database readability
- Contacts availability
- Gmail OAuth
- Open-Meteo
- Claude
- NYT API

### 5. Build the wrapper app for scheduled runs

Scheduled runs work best through a real app identity instead of raw `launchd` directly invoking Python:

```bash
./setup/build_niederdaily_app.sh
```

This creates:

```bash
~/Applications/NiederDaily.app
```

Grant that app access in macOS Privacy & Security for:

- Calendars
- Reminders
- Photos
- Contacts
- Full Disk Access if you want Messages access in the scheduled runtime

Opening the app manually:

```bash
open -gj ~/Applications/NiederDaily.app
```

will run preflight/prompt mode so macOS can present missing permission dialogs without sending an email.

## Running

### Manual send through the app

```bash
open -W -n -gj ~/Applications/NiederDaily.app --args --run
```

Launch the app bundle through `open`, not its executable directly. LaunchServices
then attributes the Python child process to NiederDaily's signed app identity, so
macOS applies its Calendar, Reminders, Photos, Contacts, and Full Disk Access
permissions. Running `niederdaily.py` directly is useful for code-only debugging,
but protected local modules may be omitted.

### Rebuild and run the app wrapper

```bash
bash ~/Repos/NiederDaily/setup/build_niederdaily_app.sh \
  && open -W -n -gj ~/Applications/NiederDaily.app --args --run
```

Use this when you've changed the source and want to rebuild the wrapper app and immediately trigger a real send through it — the same execution path `launchd` uses. This is the right test before trusting a scheduled run, because the wrapper app is what holds TCC permissions for Calendar, Reminders, Photos, and Messages. Running Python directly bypasses that app identity and may silently miss those modules.

### Send for a specific day (`--date`)

```bash
/Users/niederme/Applications/NiederDaily.app/Contents/MacOS/NiederDaily --run --date 2008-05-21
```

`--date YYYY-MM-DD` builds and sends the newsletter as if it were that day. It drives every date-driven module: the **Tweet of the Day** and **On This Day** photo (on-this-day for the chosen date), **Calendar** (that day's events), **Reminders** (overdue/today/upcoming relative to the date), the **welcome** greeting, and the email's date line and subject.

**Weather** and **New York Times** always reflect the live present — neither API exposes historical data for a past date. The wrapper app forwards the flag, so it works both through the executable above and via `open ... --args --run --date YYYY-MM-DD`. Omit `--date` for a normal "today" send.

### Logs

```bash
tail -n 50 ~/.niederdaily/logs/niederdaily.log
```

## Scheduling

The repo includes:

- a launch agent template at [`setup/me.nieder.daily.plist.template`](setup/me.nieder.daily.plist.template)
- an app builder at [`setup/build_niederdaily_app.sh`](setup/build_niederdaily_app.sh)

The launch agent plist runs the app wrapper executable directly under `launchd`:

```bash
~/Applications/NiederDaily.app/Contents/MacOS/NiederDaily --run
```

That path is correct inside the registered LaunchAgent, where macOS tracks the
signed bundle as the responsible process. Do not copy it as a manual shell
command; manual launches should use `open` as shown above.

On newer macOS versions, prefer `bootstrap`/`bootout` over `launchctl load`:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/me.nieder.daily.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/me.nieder.daily.plist
launchctl kickstart -k gui/$(id -u)/me.nieder.daily
```

Check job state with:

```bash
launchctl print gui/$(id -u)/me.nieder.daily
```

## Project Layout

- [`niederdaily.py`](niederdaily.py): main entry point and preflight
- [`renderer.py`](renderer.py): HTML email rendering
- [`sender.py`](sender.py): Gmail send path
- [`modules/weather.py`](modules/weather.py): weather + summary sentence
- [`modules/calendar.py`](modules/calendar.py): EventKit calendar fetch
- [`modules/reminders.py`](modules/reminders.py): EventKit reminders fetch
- [`modules/messages.py`](modules/messages.py): Messages snapshot
- [`modules/photo.py`](modules/photo.py): "On This Day" photo selection
- [`modules/tweet.py`](modules/tweet.py): "Tweet of the Day" from the local birdclaw store
- [`modules/nyt.py`](modules/nyt.py): NYT Top Stories fetch
- [`modules/welcome.py`](modules/welcome.py): Claude prompt + welcome line
- [`tests/`](tests): focused module and renderer tests

## Current State

This branch has already landed:

- EventKit migration for Calendar and Reminders
- preflight cleanup and degraded-vs-blocking behavior
- redesigned light-mode email styling
- improved mobile layout
- NYT Top Stories feed for the front-page news of the day
- bylines and larger 3:2 NYT images
- better weather card hierarchy and summary sentence
- calendar and reminder source labels with colors
- On This Day photo module styling and metadata cleanup
- Tweet of the Day module sourced from the local birdclaw store
- `--date YYYY-MM-DD` override to send/preview the newsletter as another day

## Roadmap

### Next

- harden the `Messages` module so it fails less silently and is easier to diagnose
- harden the `On This Day` photo selection path so it is faster and more predictable
- revisit deep-linking/open behavior with a cleaner Shortcuts strategy or remove it entirely
- upgrade the runtime to a newer Python everywhere to eliminate Python 3.9 / LibreSSL warning noise

### Later

- improve the welcome-line prompt guardrails to avoid age/family-role hallucinations
- add a clearer module-status trace in logs such as `ok`, `empty`, or `unavailable`
- improve install docs and scripts so they default to modern `launchctl bootstrap` behavior
- explore more useful photo metadata, if the local Photos APIs expose it reliably

## Notes

- This project is intentionally machine-local and permission-heavy.
- Calendar, Reminders, Photos, Contacts, Messages, and Shortcuts behavior can vary by host app and TCC state.
- If a section disappears, first check preflight and then the log file before assuming the renderer is broken.
