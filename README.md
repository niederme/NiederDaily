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

Python dependencies live in [`requirements.txt`](/Users/niederme/~Repos/NiederDaily/requirements.txt):

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
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "YOUR_NYT_KEY",
  "anthropic_api_key": "YOUR_ANTHROPIC_KEY",
  "reminders_lists": [],
  "calendars": [],
  "weather_calendars": ["Little York", "niederCal", "TripIt"]
}
```

Required keys are defined in [`config.py`](/Users/niederme/~Repos/NiederDaily/config.py). Calendar and weather calendar lists are optional filters.

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
bash ~/~Repos/NiederDaily/setup/build_niederdaily_app.sh \
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

- a launch agent template at [`setup/me.nieder.daily.plist.template`](/Users/niederme/~Repos/NiederDaily/setup/me.nieder.daily.plist.template)
- an app builder at [`setup/build_niederdaily_app.sh`](/Users/niederme/~Repos/NiederDaily/setup/build_niederdaily_app.sh)

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

- [`niederdaily.py`](/Users/niederme/~Repos/NiederDaily/niederdaily.py): main entry point and preflight
- [`renderer.py`](/Users/niederme/~Repos/NiederDaily/renderer.py): HTML email rendering
- [`sender.py`](/Users/niederme/~Repos/NiederDaily/sender.py): Gmail send path
- [`modules/weather.py`](/Users/niederme/~Repos/NiederDaily/modules/weather.py): weather + summary sentence
- [`modules/calendar.py`](/Users/niederme/~Repos/NiederDaily/modules/calendar.py): EventKit calendar fetch
- [`modules/reminders.py`](/Users/niederme/~Repos/NiederDaily/modules/reminders.py): EventKit reminders fetch
- [`modules/messages.py`](/Users/niederme/~Repos/NiederDaily/modules/messages.py): Messages snapshot
- [`modules/photo.py`](/Users/niederme/~Repos/NiederDaily/modules/photo.py): "On This Day" photo selection
- [`modules/tweet.py`](/Users/niederme/~Repos/NiederDaily/modules/tweet.py): "Tweet of the Day" from the local birdclaw store
- [`modules/nyt.py`](/Users/niederme/~Repos/NiederDaily/modules/nyt.py): NYT Top Stories fetch
- [`modules/welcome.py`](/Users/niederme/~Repos/NiederDaily/modules/welcome.py): Claude prompt + welcome line
- [`tests/`](/Users/niederme/~Repos/NiederDaily/tests): focused module and renderer tests

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
