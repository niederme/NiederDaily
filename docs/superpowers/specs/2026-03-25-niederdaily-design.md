# NiederDaily — Design Spec

**Date:** 2026-03-25
**Status:** Approved for implementation

---

## Overview

NiederDaily is a daily personal HTML email newsletter that lands in the owner's Gmail inbox each morning. It delivers a polished, scannable briefing: weather, calendar, reminders, messages, a photo from the past, and top news — plus a witty AI-generated welcome line that sets the tone for the day.

---

## Architecture

A single Python script (`niederdaily.py`) is scheduled via macOS `launchd` on a Mac Studio (always-on), firing at 6:00am daily. The script runs independently — no daemon, no Claude Code session required. It gathers data from seven isolated module functions, renders an HTML email, and sends it via the Gmail API.

```
launchd (6:00am, Mac Studio)
    └── niederdaily.py
            ├── module: welcome_block()       ← Claude Haiku API
            ├── module: weather_block()        ← Open-Meteo API
            ├── module: calendar_block()       ← AppleScript → Calendar.app
            ├── module: reminders_block()      ← AppleScript → Reminders.app
            ├── module: messages_block()       ← AppleScript → Messages.app
            ├── module: photo_block()          ← AppleScript → Photos.app
            ├── module: nyt_block()            ← NYT Top Stories API
            └── render_and_send()              ← Gmail API
```

Each module returns structured data or `None` on failure. The renderer skips any `None` section gracefully — a failed module never breaks the email.

---

## Modules

### 1. Welcome Line (`welcome_block`)

Calls Claude Haiku with a short prompt containing: day of week, date, current weather (temp + condition), and the first calendar event of the day. Returns a single witty, warm sentence in the first person. Displayed in the dark header, italic, below the date.

**Fallback:** Omit the line silently if the API call fails.

---

### 2. Weather (`weather_block`)

Fetches current conditions and today's forecast from **Open-Meteo** (free, no API key required).

**Default location:** Warwick, NY (41.2512° N, 74.3607° W)

**Travel detection:** Scans today's calendar events for a `location` field that geocodes to a city different from Warwick. If found, fetches weather for that city too and renders both, labelled by city name.

**Displays:** Current temp, condition, high/low, sunrise/sunset.

---

### 3. Calendar (`calendar_block`)

Queries Calendar.app via AppleScript. Fetches all events for today across all calendars. Sorts by start time, all-day events last. Displays: time (or "All day"), title, and location if present.

**Fallback:** Section omitted if Calendar is inaccessible.

---

### 4. Reminders (`reminders_block`)

Queries Reminders.app via AppleScript. Returns items grouped into three buckets:

- **Overdue** — due before today, not completed
- **Today** — due today
- **Coming up** — due in the next 7 days (capped at 5 items)

Each item shows its title and due date. Overdue items shown with a red badge, today items with blue, upcoming with grey.

**Fallback:** Section omitted if Reminders is inaccessible.

---

### 5. Messages (`messages_block`)

Queries Messages.app via AppleScript for threads active in the last 24 hours. Filters to contacts only (cross-references against Address Book to exclude unknown numbers and spam).

For each thread, displays:
- Contact name (or group name)
- Message count
- Time of last message
- **"Needs reply" badge** if: the last message was sent by them (not you) and it's been >2 hours

**Fallback:** Section omitted if Messages is inaccessible.

---

### 6. On This Day Photo (`photo_block`)

Queries Photos.app via AppleScript for media items where the creation date's month and day match today, across all past years.

**Selection priority:**
1. Favorited photos
2. Photos with detected faces
3. Oldest photo (most sentimental)
4. Random fallback from the pool

The selected photo is exported to a temp file and embedded as a base64 data URI in the email (no attachment, no external hosting). Caption shows: location (if available), original date, and ★ if favorited.

**Fallback:** Section omitted if Photos is inaccessible or no matching photos exist.

---

### 7. NYT Top Stories (`nyt_block`)

Fetches the top 5 stories from the NYT Top Stories API (`/home` section), free tier. Requires an NYT API key (stored in config).

Each story renders as: small thumbnail image (linked), headline (linked), and abstract.

**Fallback:** Section omitted if the API is down or key is missing.

---

## Email Design

- **Format:** HTML email, 600px max-width, light mode only
- **Visual style:** nieder.me/2026 — clean, typographic, high contrast
- **Layout:** Dark (`#1a1a1a`) masthead with logo, date, and welcome line. White body with labelled sections separated by hairline rules. Full-width photo block. Warm off-white footer.
- **Typography:** System font stack (`-apple-system, Helvetica Neue, sans-serif`)
- **Section labels:** Small-caps, tracked, muted — e.g. WEATHER · WARWICK, NY
- **Badges:** Colour-coded pill labels for reminder urgency and message reply status
- **Images:** Photo embedded as data URI. NYT thumbnails loaded from NYT CDN URLs.

---

## Delivery

- **Transport:** Gmail API with OAuth2 (`gmail.send` scope)
- **Credentials:** Stored in `~/.niederdaily/credentials.json` (OAuth token) and `~/.niederdaily/config.json` (API keys, recipient address)
- **Recipient:** Owner's Gmail address
- **Subject line:** `NiederDaily · Wednesday, March 25`

---

## Scheduling

macOS `launchd` plist installed at `~/Library/LaunchAgents/me.nieder.daily.plist`. Configured with `StartCalendarInterval` at 06:00. Stdout/stderr logged to `~/.niederdaily/logs/`.

---

## Configuration

Stored in `~/.niederdaily/config.json`:

```json
{
  "recipient_email": "me@nieder.me",
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "...",
  "anthropic_api_key": "...",
  "gmail_credentials_path": "~/.niederdaily/credentials.json"
}
```

---

## Error Handling

- Each module is wrapped in a `try/except`; failures return `None`
- `None` modules are silently skipped in the renderer
- Script-level errors (e.g. Gmail send failure) are logged to `~/.niederdaily/logs/error.log`
- No retry logic — next successful run is the next morning

---

## File Structure

```
NiederDaily/
├── niederdaily.py          # Main script
├── modules/
│   ├── welcome.py
│   ├── weather.py
│   ├── calendar.py
│   ├── reminders.py
│   ├── messages.py
│   ├── photo.py
│   └── nyt.py
├── renderer.py             # HTML email builder
├── sender.py               # Gmail API wrapper
├── config.py               # Config loader
├── setup/
│   ├── install.sh          # Sets up launchd plist, creates config dir
│   └── me.nieder.daily.plist
└── requirements.txt
```

---

## Out of Scope

- Push notifications or SMS delivery
- Web dashboard or archive
- Multiple recipients
- Retry logic or delivery confirmation
- AI summarisation of message content (heuristic approach used instead)
