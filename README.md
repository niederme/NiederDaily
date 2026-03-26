# NiederDaily

NiederDaily is a personal daily email digest for one person and one machine.
It assembles a morning email from:

- local calendar events
- local reminders
- local Photos "On This Day" memories
- local Messages context
- weather
- a short Claude-written welcome line
- New York Times Most Popular stories

The current branch also includes a substantial visual refresh so the email feels closer to the `nieder.me/2026` editorial style on desktop and mobile.

## What It Does

Each run builds an email with some or all of these modules:

- `Weather`
- `Calendar`
- `Reminders`
- `Messages`
- `On This Day`
- `New York Times Most Popular`

If a module fails, the send can still continue. The app logs the failure and omits that section rather than killing the whole newsletter.

## Requirements

- macOS
- Python 3.10+ recommended
- Gmail API credentials for sending
- Anthropic API key for the welcome line
- New York Times API key
- local access to Calendar, Reminders, Photos, Contacts, and Messages as needed

Python dependencies live in [`requirements.txt`](/Users/niederme/~Repos/NiederDaily/requirements.txt):

- `anthropic`
- `google-auth-oauthlib`
- `google-api-python-client`
- `requests`
- `pyobjc-framework-AddressBook`
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
  "calendars": []
}
```

Required keys are defined in [`config.py`](/Users/niederme/~Repos/NiederDaily/config.py).

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

## Running

### Manual send

```bash
./.venv/bin/python niederdaily.py
```

### Logs

```bash
tail -n 50 ~/.niederdaily/logs/niederdaily.log
```

## Scheduling

The repo includes a launch agent template at [`setup/me.nieder.daily.plist.template`](/Users/niederme/~Repos/NiederDaily/setup/me.nieder.daily.plist.template).

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
- [`modules/nyt.py`](/Users/niederme/~Repos/NiederDaily/modules/nyt.py): NYT Most Popular fetch
- [`modules/welcome.py`](/Users/niederme/~Repos/NiederDaily/modules/welcome.py): Claude prompt + welcome line
- [`tests/`](/Users/niederme/~Repos/NiederDaily/tests): focused module and renderer tests

## Current State

This branch has already landed:

- EventKit migration for Calendar and Reminders
- preflight cleanup and degraded-vs-blocking behavior
- redesigned light-mode email styling
- improved mobile layout
- NYT Most Popular instead of Top Stories
- bylines and larger 3:2 NYT images
- better weather card hierarchy and summary sentence
- calendar and reminder source labels with colors
- On This Day photo module styling and metadata cleanup

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
