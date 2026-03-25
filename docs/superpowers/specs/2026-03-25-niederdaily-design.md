# NiederDaily — Design Spec

**Date:** 2026-03-25
**Status:** Approved for implementation

---

## Overview

NiederDaily is a daily personal HTML email newsletter that lands in the owner's Gmail inbox each morning. It delivers a polished, scannable briefing: weather, calendar, reminders, messages, a photo from the past, and top news — plus a witty AI-generated welcome line that sets the tone for the day.

---

## Architecture

A single Python script (`niederdaily.py`) is scheduled via macOS `launchd` on a Mac Studio (always-on), firing at 6:00am daily. The script runs independently — no daemon, no Claude Code session required.

**Execution order matters for `welcome_block`:** weather and calendar data must be gathered first, as they are passed as inputs to the Haiku prompt. All other modules are independent and can run in any order.

```
launchd (6:00am, Mac Studio)
    └── niederdaily.py
            ├── step 1: weather_block()        ← Open-Meteo API
            ├── step 2: calendar_block()        ← AppleScript → Calendar.app
            ├── step 3: welcome_block()         ← Claude Haiku API (uses weather + calendar output)
            ├── step 4: reminders_block()       ← AppleScript → Reminders.app
            ├── step 5: messages_block()        ← chat.db SQLite (Full Disk Access required)
            ├── step 6: photo_block()           ← AppleScript → Photos.app
            ├── step 7: nyt_block()             ← NYT Top Stories API
            └── render_and_send()              ← Gmail API (MIME multipart)
```

Each module returns structured data or `None` on failure. The renderer skips any `None` section gracefully — a failed module never breaks the email.

---

## Modules

### 1. Weather (`weather_block`)

Fetches current conditions and today's forecast from **Open-Meteo** (free, no API key required). Open-Meteo accepts lat/lon only; WMO `weathercode` integers are mapped to human-readable labels using the standard WMO Weather Interpretation Code table (bundled as a dict in `weather.py`).

**Default location:** Warwick, NY (41.2512° N, 74.3607° W)

**Travel detection:** Scans today's calendar events (sorted by start time) for the **first timed event** with a non-empty `location` field. Geocodes that single location using the **Nominatim API** (`nominatim.openstreetmap.org/search`, free, no key required — must set a `User-Agent` header per their policy). If the resolved city differs from the default, fetches weather for that city and renders both sections, labelled by city name. Only one travel location is ever shown (the first offsite timed event). The resolved travel city name is also passed to `welcome_block` if present. Gracefully skips travel detection if geocoding fails.

**Displays:** Current temp (°F), condition label, high/low, sunrise/sunset.

---

### 2. Calendar (`calendar_block`)

Queries Calendar.app via AppleScript (`osascript`). Fetches all events for today across all calendars. Sorts by start time; all-day events listed last. Displays: time (or "All day"), title, and location if present.

**Fallback:** Section omitted if Calendar is inaccessible or AppleScript fails.

---

### 3. Welcome Line (`welcome_block`)

Runs after `weather_block` and `calendar_block`. Calls Claude Haiku with a short prompt containing: day of week, date, weather temp + condition, travel city if detected, and the title of the first timed calendar event (or nothing if the day is empty). Returns a single witty, warm sentence. Displayed in the dark header, italic, below the date.

**Fallback:** Omit the line silently if the API call fails or inputs are unavailable.

---

### 4. Reminders (`reminders_block`)

Queries Reminders.app via AppleScript. Returns items grouped into three buckets:

- **Overdue** — due before today, not completed
- **Today** — due today
- **Coming up** — due in the next 7 days (capped at 5 items)

**List filtering:** By default all lists are included. An optional `reminders_lists` array in `config.json` restricts to named lists if provided.

Each item shows title and due date. Badges: red (Overdue), blue (Today), grey (Coming up).

**Fallback:** Section omitted if Reminders is inaccessible.

---

### 5. Messages (`messages_block`)

Reads directly from `~/Library/Messages/chat.db` (SQLite) rather than AppleScript, which lacks the necessary APIs on modern macOS. Requires **Full Disk Access** granted to Terminal (or the Python executable) in System Settings → Privacy & Security.

Queries threads with messages in the last 24 hours. Filters to contacts only by cross-referencing `handle.id` (phone number or email) against the system Address Book via the `AddressBook` framework (accessed via `pyobjc`). Requires **Contacts access** granted in System Settings → Privacy & Security → Contacts.

**Contacts fallback:** If the Address Book lookup is denied or unavailable, display threads using the raw handle (phone number or email) rather than dropping the section entirely.

For each matching thread, displays:
- Contact name (resolved via Address Book), raw handle (if lookup unavailable), or group name
- Message count in the last 24 hours
- Time of last message
- **"Needs reply" badge** if: `message.is_from_me = 0` on the most recent message AND it's been >2 hours

**Fallback:** Section omitted if `chat.db` is unreadable or FDA is not granted.

---

### 6. On This Day Photo (`photo_block`)

Queries Photos.app via AppleScript for media items where the creation date's month and day match today, across all past years.

**Selection priority:**
1. Favorited photos
2. Photos with detected faces (AppleScript `face count` property)
3. Oldest photo
4. Random fallback from the pool

`photo_block` returns a `(bytes, metadata)` tuple. The temp file lifecycle is **fully internal** to `photo_block`: AppleScript exports the photo to a `NamedTemporaryFile`, Python reads the bytes, the file is closed and deleted — all within the function. The caller receives raw image bytes and a metadata dict; it never touches the filesystem.

The photo is embedded in the email as a **MIME inline attachment** with a `Content-ID` header (`cid:onthisday`), referenced from the HTML body as `<img src="cid:onthisday">`. This approach is fully supported by Gmail.

Caption shows: location (if available from EXIF/Photos metadata), original date, and ★ if favorited.

**Fallback:** Section omitted if Photos is inaccessible or no matching photos exist.

---

### 7. NYT Top Stories (`nyt_block`)

Fetches the top 5 stories from the NYT Top Stories API (`/home` section), free tier. Requires an NYT API key stored in config.

Each story renders as: thumbnail image linked to the article, headline linked to the article, and abstract. If a story has no thumbnail in its `multimedia` array, it renders headline and abstract only (no placeholder image).

**Fallback:** Section omitted if the API is down or key is missing.

---

## Email Design

- **Format:** HTML email, 600px max-width, light mode only
- **Visual style:** nieder.me/2026 — clean, typographic, high contrast
- **Layout:** Dark (`#1a1a1a`) masthead with logo, date, and welcome line. White body with labelled sections separated by hairline rules. Full-width photo block. Warm off-white footer.
- **Typography:** System font stack (`-apple-system, Helvetica Neue, sans-serif`)
- **Section labels:** Small-caps, tracked, muted — e.g. `WEATHER · WARWICK, NY`
- **Badges:** Colour-coded pill labels for reminder urgency and message reply status
- **Images:** Photo as MIME inline attachment (`cid:`). NYT thumbnails loaded from NYT CDN URLs (external, linked).

---

## Delivery

- **Transport:** Gmail API with OAuth2 (`gmail.send` scope)
- **MIME structure:** `multipart/related` containing `text/html` body and the inline photo attachment
- **Credential files** (both in `~/.niederdaily/`):
  - `client_secret.json` — downloaded once from Google Cloud Console; never changes
  - `token.json` — written by the OAuth flow on first run; auto-refreshed by `google-auth-oauthlib`
- **Recipient:** Owner's Gmail address (from config)
- **Subject line:** `NiederDaily · Wednesday, March 25, 2026`

---

## Runtime Environment

`install.sh` creates a **repo-owned virtualenv** at `NiederDaily/.venv/` using the system Python 3. All dependencies from `requirements.txt` are installed into this venv at install time. The launchd plist hardcodes the path to `.venv/bin/python` (absolute path resolved during install). This isolates NiederDaily from system Python upgrades, Homebrew changes, and other projects.

`install.sh` never installs or modifies the system Python.

---

## Scheduling

macOS `launchd` plist installed at `~/Library/LaunchAgents/me.nieder.daily.plist`. Configured with `StartCalendarInterval` at 06:00.

The plist `ProgramArguments` key uses the absolute path to `.venv/bin/python` and the absolute path to `niederdaily.py`, both resolved by `install.sh` at install time.

Stdout/stderr logged to `~/.niederdaily/logs/niederdaily.log`.

---

## Configuration

`~/.niederdaily/config.json` — generated as a template by `install.sh`; user fills in API keys:

```json
{
  "recipient_email": "me@example.com",
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "FILL_IN",
  "anthropic_api_key": "FILL_IN",
  "reminders_lists": []
}
```

---

## Setup & First-Run Bootstrap

Before the LaunchAgent is loaded, all interactive permission flows must be completed manually. `install.sh` handles environment setup; `niederdaily.py --preflight` handles permission validation.

**`install.sh` responsibilities:**
1. Creates `~/.niederdaily/` and `~/.niederdaily/logs/`
2. Writes `config.json` template
3. Creates `.venv/` and installs `requirements.txt` into it
4. Generates the launchd plist with absolute paths to `.venv/bin/python` and `niederdaily.py`
5. Prints next steps: fill in config, run `--preflight`, then load the LaunchAgent

**`niederdaily.py --preflight` (run manually before first scheduled run):**

Runs each integration interactively and reports pass/fail:
- Triggers Calendar.app AppleScript to prompt Automation permission
- Triggers Reminders.app AppleScript to prompt Automation permission
- Triggers Photos.app AppleScript to prompt Automation permission
- Attempts to read `chat.db` and reports whether Full Disk Access is granted
- Attempts Address Book lookup and reports whether Contacts access is granted
- Runs Gmail OAuth flow (opens browser for token grant)
- Makes a test call to Open-Meteo and reports success
- Makes a test call to Claude Haiku and reports success
- Makes a test call to NYT API (if key is set) and reports success

After preflight passes, the user manually loads the agent:
```bash
launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist
```

---

## Permissions Required (Mac Studio)

- **Automation → Calendar:** for `calendar_block` and `reminders_block`
- **Automation → Photos:** for `photo_block`
- **Full Disk Access → Terminal** (or `.venv/bin/python`): for `messages_block` (`chat.db`)
- **Contacts → Terminal** (or `.venv/bin/python`): for contact name resolution in `messages_block`

---

## Error Handling

- Each module is wrapped in `try/except`; failures return `None`
- `None` modules are silently skipped in the renderer
- Script-level errors (e.g. Gmail send failure) are logged to `~/.niederdaily/logs/niederdaily.log`
- No retry logic — next successful run is the next morning

---

## File Structure

```
NiederDaily/
├── niederdaily.py          # Main entry point — orchestrates module calls in order; --preflight mode
├── modules/
│   ├── welcome.py          # Claude Haiku prompt + response parsing
│   ├── weather.py          # Open-Meteo API + WMO code table + Nominatim geocoding
│   ├── calendar.py         # AppleScript → Calendar.app
│   ├── reminders.py        # AppleScript → Reminders.app
│   ├── messages.py         # chat.db SQLite + pyobjc Address Book lookup
│   ├── photo.py            # AppleScript → Photos.app; returns (bytes, metadata)
│   └── nyt.py              # NYT Top Stories API
├── renderer.py             # Builds MIME multipart/related email from module data
├── sender.py               # Gmail API OAuth2 wrapper
├── config.py               # Loads and validates ~/.niederdaily/config.json
├── setup/
│   ├── install.sh          # Creates venv, installs deps, writes config template, generates plist
│   └── me.nieder.daily.plist.template
└── requirements.txt
```

---

## Out of Scope

- Push notifications or SMS delivery
- Web dashboard or archive
- Multiple recipients
- Retry logic or delivery confirmation
- AI summarisation of message content (heuristic approach used instead)
