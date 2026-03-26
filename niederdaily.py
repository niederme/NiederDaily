#!/usr/bin/env python3
"""NiederDaily — daily personal email newsletter."""

import argparse
import logging
import sys
from pathlib import Path

log_dir = Path.home() / ".niederdaily" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_dir / "niederdaily.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

import config as cfg
from modules.weather import weather_block
from modules.calendar import calendar_block, calendar_access_granted
from modules.welcome import welcome_block
from modules.reminders import reminders_block, reminders_access_granted
from modules.messages import messages_block
from modules.photo import photo_access_granted, photo_block
from modules.nyt import nyt_block
from renderer import render_email
from sender import send_email


def run(config_path: str = None):
    try:
        conf = cfg.load_config(config_path)
    except cfg.ConfigError as e:
        logging.error(f"Config error: {e}")
        sys.exit(1)

    # Step 1 & 2: gather weather and calendar first (needed by welcome)
    weather = _safe(weather_block, conf, calendar_events=[])
    calendar = _safe(calendar_block, conf.get("calendars"))

    # Re-run weather with calendar events for travel detection
    if calendar:
        weather = _safe(weather_block, conf, calendar_events=calendar)

    # Step 3: welcome needs weather + calendar
    welcome = _safe(welcome_block, conf["anthropic_api_key"],
                    weather_data=weather, calendar_events=calendar)

    # Steps 4-7: independent modules
    reminders = _safe(reminders_block, conf.get("reminders_lists", []))
    messages  = _safe(messages_block)
    photo     = _safe(photo_block)
    nyt       = _safe(nyt_block, conf.get("nyt_api_key"))

    msg = render_email(
        recipient=conf["recipient_email"],
        welcome=welcome,
        weather=weather,
        calendar=calendar,
        reminders=reminders,
        messages=messages,
        photo=photo,
        nyt=nyt,
    )

    token_path = str(Path.home() / ".niederdaily" / "token.json")
    secret_path = str(Path.home() / ".niederdaily" / "client_secret.json")
    success = send_email(msg, secret_path, token_path)
    if success:
        logging.info("NiederDaily sent successfully.")
    else:
        logging.error("Failed to send NiederDaily.")


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        fn_name = getattr(fn, "__name__", fn.__class__.__name__)
        logging.warning(f"Module {fn_name} failed: {e}", exc_info=True)
        return None


def preflight():
    """Interactive check of all integrations. Run this before the first scheduled run."""
    print("NiederDaily Preflight Check\n" + "=" * 40)
    blocking_ok = True
    warnings = False

    def report(label: str, succeeded: bool, success_message: str, failure_message: str, *, blocking: bool):
        nonlocal blocking_ok, warnings
        if succeeded:
            print(f"✓ {label}{success_message}")
            return
        prefix = "✗" if blocking else "!"
        print(f"{prefix} {label}: {failure_message}")
        if blocking:
            blocking_ok = False
        else:
            warnings = True

    # Config
    try:
        conf = cfg.load_config()
        print("✓ Config loaded")
    except cfg.ConfigError as e:
        print(f"✗ Config: {e}")
        sys.exit(1)

    # Calendar
    calendar_ready = calendar_access_granted(prompt=True)
    result = calendar_block(conf.get("calendars")) if calendar_ready else None
    report(
        "Calendar",
        result is not None,
        f" ({len(result or [])} events today)",
        "unavailable — grant full Calendar access in System Settings → Privacy & Security → Calendars. The newsletter will skip this section until access is granted.",
        blocking=False,
    )

    # Reminders
    reminders_ready = reminders_access_granted(prompt=True)
    rem = reminders_block(conf.get("reminders_lists", [])) if reminders_ready else None
    report(
        "Reminders",
        rem is not None,
        "",
        "unavailable — grant Reminders access in System Settings → Privacy & Security → Reminders. The newsletter will skip this section until access is granted.",
        blocking=False,
    )

    # Photos
    photos_ready = photo_access_granted(prompt=True)
    report(
        "Photos",
        photos_ready,
        " (Photo Library accessible)",
        "unavailable — grant Photos access in System Settings → Privacy & Security → Photos. The newsletter will skip this section until access is granted.",
        blocking=False,
    )

    # Messages / chat.db
    from modules.messages import DB_PATH
    from pathlib import Path as P
    report(
        "Messages",
        P(DB_PATH).exists(),
        " (chat.db readable — Full Disk Access granted)",
        "chat.db not accessible — grant Full Disk Access to Terminal in System Settings → Privacy & Security. The newsletter will skip this section until access is granted.",
        blocking=False,
    )

    # Address Book / Contacts
    try:
        import AddressBook
        book = AddressBook.ABAddressBook.sharedAddressBook()
        report(
            "Contacts",
            bool(book),
            " (Address Book accessible)",
            "Address Book returned None — grant Contacts access in System Settings. Message senders will fall back to raw handles until access is granted.",
            blocking=False,
        )
    except Exception as e:
        report(
            "Contacts",
            False,
            "",
            f"{e}. Message senders will fall back to raw handles until access is granted.",
            blocking=False,
        )

    # Gmail OAuth
    from pathlib import Path as P2
    token_path = P2.home() / ".niederdaily" / "token.json"
    secret_path = P2.home() / ".niederdaily" / "client_secret.json"
    if not secret_path.exists():
        print(f"✗ Gmail: client_secret.json not found at {secret_path}")
        print("  → Download it from Google Cloud Console (APIs & Services → Credentials)")
        blocking_ok = False
    else:
        try:
            from sender import get_gmail_service
            get_gmail_service(str(secret_path), str(token_path))
            print("✓ Gmail (OAuth token valid)")
        except Exception as e:
            print(f"✗ Gmail OAuth: {e}")
            blocking_ok = False

    # Open-Meteo
    import requests
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
            params={"latitude": 41.25, "longitude": -74.36, "current": "temperature_2m",
                    "forecast_days": 1}, timeout=10)
        r.raise_for_status()
        print("✓ Open-Meteo")
    except Exception as e:
        report(
            "Open-Meteo",
            False,
            "",
            f"{e}. The newsletter will skip the weather section until this recovers.",
            blocking=False,
        )

    # Claude Haiku
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=conf["anthropic_api_key"])
        resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": "Say 'ok'"}])
        print("✓ Claude Haiku")
    except Exception as e:
        report(
            "Claude Haiku",
            False,
            "",
            f"{e}. The welcome line will be omitted until this recovers.",
            blocking=False,
        )

    # NYT
    if conf.get("nyt_api_key") and conf["nyt_api_key"] != "FILL_IN":
        try:
            r = requests.get("https://api.nytimes.com/svc/topstories/v2/home.json",
                params={"api-key": conf["nyt_api_key"]}, timeout=10)
            r.raise_for_status()
            print("✓ NYT Top Stories")
        except Exception as e:
            report(
                "NYT",
                False,
                "",
                f"{e}. The news section will be skipped until this recovers.",
                blocking=False,
            )
    else:
        print("- NYT: API key not set (section will be skipped)")

    print("\n" + ("=" * 40))
    if blocking_ok and not warnings:
        print("All checks passed. Load the LaunchAgent with:")
        print("  launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist")
    elif blocking_ok:
        print("Preflight degraded. Scheduling is safe, but unavailable sections will be skipped until access is granted.")
        print("You can still load the LaunchAgent with:")
        print("  launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist")
    else:
        print("Blocking checks failed. Fix the issues above before scheduling.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    if args.preflight:
        preflight()
    else:
        run(config_path=args.config)
