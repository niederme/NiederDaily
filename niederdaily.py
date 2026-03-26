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
from modules.weather import weather_block, weather_sentence
from modules.calendar import calendar_block
from modules.welcome import welcome_block
from modules.reminders import reminders_block
from modules.messages import messages_block
from modules.photo import photo_block
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
    calendar = _safe(calendar_block)

    # Re-run weather with calendar events for travel detection
    if calendar:
        weather = _safe(weather_block, conf, calendar_events=calendar)

    # Generate Haiku sentence once, for home location only
    if weather and weather.get("locations"):
        home = weather["locations"][0]
        home["sentence"] = weather_sentence(home, conf["anthropic_api_key"])

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
        logging.warning(f"Module {fn.__name__} failed: {e}", exc_info=True)
        return None


def preflight():
    """Interactive check of all integrations. Run this before the first scheduled run."""
    print("NiederDaily Preflight Check\n" + "=" * 40)
    ok = True

    # Config
    try:
        conf = cfg.load_config()
        print("✓ Config loaded")
    except cfg.ConfigError as e:
        print(f"✗ Config: {e}")
        sys.exit(1)

    # Calendar
    result = calendar_block()
    if result is not None:
        print(f"✓ Calendar ({len(result)} events today)")
    else:
        print("✗ Calendar: failed — grant Automation access to Calendar in System Settings")
        ok = False

    # Reminders
    rem = reminders_block(conf.get("reminders_lists", []))
    if rem is not None:
        print("✓ Reminders")
    else:
        print("✗ Reminders: failed — grant Automation access to Reminders in System Settings")
        ok = False

    # Photos
    import subprocess
    r = subprocess.run(["osascript", "-e", 'tell application "Photos" to return name of first media item'], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        print("✓ Photos")
    else:
        print("✗ Photos: failed — grant Automation access to Photos in System Settings")
        ok = False

    # Messages / chat.db
    from modules.messages import DB_PATH
    from pathlib import Path as P
    if P(DB_PATH).exists():
        print("✓ Messages (chat.db readable — Full Disk Access granted)")
    else:
        print("✗ Messages: chat.db not accessible — grant Full Disk Access to Terminal in System Settings → Privacy & Security")
        ok = False

    # Address Book / Contacts
    try:
        import AddressBook
        book = AddressBook.ABAddressBook.sharedAddressBook()
        if book:
            print("✓ Contacts (Address Book accessible)")
        else:
            print("✗ Contacts: Address Book returned None — grant Contacts access in System Settings")
            ok = False
    except Exception as e:
        print(f"✗ Contacts: {e}")
        ok = False

    # Gmail OAuth
    from pathlib import Path as P2
    token_path = P2.home() / ".niederdaily" / "token.json"
    secret_path = P2.home() / ".niederdaily" / "client_secret.json"
    if not secret_path.exists():
        print(f"✗ Gmail: client_secret.json not found at {secret_path}")
        print("  → Download it from Google Cloud Console (APIs & Services → Credentials)")
        ok = False
    else:
        try:
            from sender import get_gmail_service
            get_gmail_service(str(secret_path), str(token_path))
            print("✓ Gmail (OAuth token valid)")
        except Exception as e:
            print(f"✗ Gmail OAuth: {e}")
            ok = False

    # WeatherKit
    import requests
    try:
        from modules.weather import _make_jwt
        token = _make_jwt(conf)
        lat = conf["default_location"]["lat"]
        lon = conf["default_location"]["lon"]
        r = requests.get(
            f"https://weatherkit.apple.com/api/v1/availability/{lat}/{lon}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        print("✓ WeatherKit")
    except Exception as e:
        print(f"✗ WeatherKit: {e}. The newsletter will skip the weather section until this recovers.")
        ok = False

    # Claude Haiku
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=conf["anthropic_api_key"])
        resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": "Say 'ok'"}])
        print("✓ Claude Haiku")
    except Exception as e:
        print(f"✗ Claude Haiku: {e}")
        ok = False

    # NYT
    if conf.get("nyt_api_key") and conf["nyt_api_key"] != "FILL_IN":
        try:
            r = requests.get("https://api.nytimes.com/svc/topstories/v2/home.json",
                params={"api-key": conf["nyt_api_key"]}, timeout=10)
            r.raise_for_status()
            print("✓ NYT Top Stories")
        except Exception as e:
            print(f"✗ NYT: {e}")
            ok = False
    else:
        print("- NYT: API key not set (section will be skipped)")

    print("\n" + ("=" * 40))
    if ok:
        print("All checks passed. Load the LaunchAgent with:")
        print("  launchctl load ~/Library/LaunchAgents/me.nieder.daily.plist")
    else:
        print("Some checks failed. Fix the issues above before scheduling.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    if args.preflight:
        preflight()
    else:
        run(config_path=args.config)
