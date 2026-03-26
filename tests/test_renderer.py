import pytest
import sys
from pathlib import Path

from renderer import render_email

WEATHER = {"locations": [{"location": "Warwick, NY", "temp": 54, "condition": "Overcast", "high": 61, "low": 44, "sunrise": "6:52am", "sunset": "7:31pm"}], "travel_city": None}
CALENDAR = [{"time": "9:00am", "title": "Weekly sync", "location": "", "all_day": False}]
REMINDERS = {"overdue": [{"title": "Call accountant", "due": "2026-03-20"}], "today": [], "upcoming": []}
MESSAGES = [{"name": "Mom", "handle": "+15555550101", "is_contact": True, "count": 4, "last_time": "8:14pm", "needs_reply": True}]
PHOTO = (b'\xff\xd8\xff' + b'\x00' * 100, {"year": "2019", "date": "2019-03-25", "location": "Warwick, NY", "is_favorite": True})
NYT = [{"title": "Story One", "abstract": "Things happened.", "byline": "By Reporter One", "url": "https://nytimes.com/1", "thumbnail": None}]

def test_render_returns_mime_message():
    msg = render_email(
        recipient="me@example.com",
        welcome="Wednesday. Cold and grey.",
        weather=WEATHER, calendar=CALENDAR, reminders=REMINDERS,
        messages=MESSAGES, photo=PHOTO, nyt=NYT
    )
    assert msg["To"] == "me@example.com"
    assert "NiederDaily" in msg["Subject"]

def test_render_subject_includes_date():
    from datetime import date
    msg = render_email(recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=None)
    assert date.today().strftime("%Y") in msg["Subject"]

def test_render_includes_weather_icon():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=WEATHER, calendar=None, reminders=None, messages=None, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert 'class="weather-icon"' in html
    assert 'class="weather-card"' in html
    assert 'class="weather-condition"' in html
    assert 'class="weather-meta"' in html
    assert "<svg" in html
    assert "61° / 44°" in html
    assert "Overcast" in html
    assert "Sunrise 6:52am" in html


def test_render_omits_rule_between_weather_card_and_next_section():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=WEATHER, calendar=CALENDAR, reminders=None, messages=None, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert html.count('class="section-rule"') == 0
    assert "Calendar" in html

def test_render_includes_photo_attachment():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=PHOTO, nyt=None
    )
    payloads = msg.get_payload()
    content_ids = [p.get("Content-ID", "") for p in payloads if hasattr(p, 'get')]
    assert any("onthisday" in cid for cid in content_ids)

def test_render_needs_reply_badge_present():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=MESSAGES, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert "Needs reply" in html
    assert "Mom" in html

def test_render_skips_none_sections_without_error():
    # Should not raise, and should produce a valid email
    msg = render_email(recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=None)
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert "NiederDaily" in html

def test_render_welcome_appears_in_header():
    msg = render_email(
        recipient="me@example.com", welcome="Today is fine.",
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert "Today is fine." in html
    assert "font-style:italic" not in html

def test_render_reminders_only_show_first_upcoming_day():
    reminders = {
        "overdue": [],
        "today": [],
        "upcoming": [
            {"title": "Call mom", "due": "2026-03-26"},
            {"title": "Pick up Rx", "due": "2026-03-26"},
            {"title": "UMAC uniforms", "due": "2026-03-30"},
        ],
    }
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=reminders, messages=None, photo=None, nyt=None
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert "Call mom" in html
    assert "Pick up Rx" in html
    assert "UMAC uniforms" not in html


def test_render_nyt_without_thumbnail_has_no_placeholder_block():
    msg = render_email(
        recipient="me@example.com", welcome=None,
        weather=None, calendar=None, reminders=None, messages=None, photo=None, nyt=NYT
    )
    html_part = next(p for p in msg.get_payload() if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode()
    assert 'class="nytthumb"' not in html
    assert "By Reporter One" in html
