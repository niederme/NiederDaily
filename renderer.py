from __future__ import annotations

import json
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from html import escape as _esc
from urllib.parse import quote
from zoneinfo import ZoneInfo

ACCENT = "#ff453a"
INK = "#121212"
MUTED = "#474a51"
LINE = "#d6d0c6"
SHORTCUT_NAME = "Open NiederDaily Item"

PACKAGE_CARRIERS = {
    "fedex": ("FedEx", "#A02A7B"),
    "ups": ("UPS", "#694122"),
    "dhl": ("DHL", "#826100"),
    "amzlus": ("Amazon", "#995000"),
    "amazon": ("Amazon", "#995000"),
    "usps": ("USPS", "#1165A3"),
    "swiship": ("Swiship", "#121212"),
}

BADGE_REPLY = f'<span style="display:inline-block;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Needs reply</span>'

SECTION_LABEL_STYLE = f"font-size:16px;font-weight:700;letter-spacing:-0.01em;color:{INK};margin-bottom:14px;"

BASE_STYLES = """
body{margin:0;padding:0;background:#ffffff;color:#121212;font-family:Sohne,"SF Pro Text","SF Pro Display",-apple-system,BlinkMacSystemFont,"Helvetica Neue","Arial Nova",Arial,sans-serif;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
a{color:#121212;}
.wrap{max-width:680px;margin:0 auto;padding:24px 18px 48px;}
.email{background:#ffffff;overflow:hidden;}
.header{padding:44px 40px 24px;}
.date-line{font-size:16px;font-weight:300;line-height:1.35;letter-spacing:-0.01em;color:#474a51;max-width:520px;margin-bottom:12px;}
.logo{font-size:44px;font-weight:700;line-height:0.96;letter-spacing:-0.03em;color:#121212;margin-bottom:18px;}
.welcome p{margin:0 0 12px;}.welcome p:last-child{margin-bottom:0;}
.welcome{max-width:520px;font-size:18px;font-weight:300;line-height:1.38;color:#474a51;}
.section{padding:0 40px 24px;}
.section-rule{height:1px;background:#d6d0c6;margin:0 0 24px;}
.weather-loc{margin:0 0 14px;}.weather-loc:last-child{margin-bottom:0;}
.weather-place{font-size:16px;font-weight:700;line-height:1.3;letter-spacing:-0.01em;color:#121212;margin-bottom:4px;}
.weather-line{font-size:16px;line-height:1.45;color:#121212;}
.weather-temp{font-weight:600;}
.weather-range{color:#6d7178;}
.weather-summary{color:#474a51;}
.supporting{font-size:13px;line-height:1.45;color:#474a51;margin-top:8px;}
.list-row{display:flex;gap:18px;align-items:baseline;padding:0 0 11px;margin:0 0 11px;border-bottom:1px solid rgba(214,208,198,0.55);}
.list-row:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.list-time{min-width:56px;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#474a51;}
.list-main{flex:1;font-size:15px;line-height:1.35;color:#121212;}
.list-time.pkg-today,.list-time.pkg-late{color:#ff453a;}
.item-link{color:#121212;text-decoration:none;}
.item-link:hover{text-decoration:underline;}
.item-row-link{display:flex;gap:18px;align-items:baseline;width:100%;color:inherit;text-decoration:none;}
.item-row-link:hover .list-main{text-decoration:underline;}
.list-meta{display:block;font-size:12px;line-height:1.4;color:#474a51;margin-top:4px;}
.meta-sep{color:#9aa0a6;margin:0 6px;}
.calendar-source{display:inline-flex;align-items:center;gap:6px;font-weight:700;white-space:nowrap;}
.calendar-dot{display:inline-block;width:8px;height:8px;border-radius:999px;flex-shrink:0;}
.calendar-line{display:flex;font-size:12px;line-height:1.4;margin-bottom:3px;}
.calendar-title{display:block;font-weight:600;}
.calendar-location{display:block;font-weight:400;color:#6d7178;}
.reminder-group{margin:0 0 18px;}.reminder-group:last-child{margin-bottom:0;}
.reminder-list{font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#6d7178;margin:0 0 8px;}
.reminder-row{display:flex;align-items:center;gap:10px;padding:0 0 9px;margin:0 0 9px;border-bottom:1px solid rgba(214,208,198,0.55);}
.reminder-row:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.reminder-check{display:inline-block;width:14px;height:14px;border:2px solid #6d7178;border-radius:999px;box-sizing:border-box;flex-shrink:0;}
.reminder-title{flex:1;font-size:15px;line-height:1.35;color:#121212;}
.reminder-status{font-size:12px;color:#6d7178;white-space:nowrap;}
.reminder-overdue{color:#ff453a;font-weight:600;}
.msg-summary{max-width:520px;font-size:16px;line-height:1.55;color:#474a51;}
.nyt{display:flex;gap:20px;align-items:flex-start;padding:0 0 16px;margin:0 0 16px;border-bottom:1px solid rgba(214,208,198,0.55);}
.nyt:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.nyt-link{display:flex;gap:20px;align-items:flex-start;width:100%;color:inherit;text-decoration:none;}
.nytthumb{width:175px;height:117px;object-fit:cover;object-position:right center;flex-shrink:0;background:#f5efe5;}
.nythed{font-size:17px;font-weight:700;line-height:1.18;color:#121212;margin-bottom:6px;}
.nytdek{font-size:13px;color:#474a51;line-height:1.42;}
.nytmeta{font-size:10px;color:#6d7178;line-height:1.4;letter-spacing:0.025em;text-transform:uppercase;margin-top:7px;}
.photo-module{max-width:520px;margin:0 auto;}
.photo-frame{display:block;border-radius:14px;overflow:hidden;border:1px solid rgba(214,208,198,0.7);background:#ffffff;line-height:0;}
.photo-frame img{width:100%;display:block;}
.photo-description{font-size:16px;font-weight:400;letter-spacing:-0.01em;line-height:1.45;color:#474a51;margin-top:4px;}
.photo-meta{margin-top:6px;font-size:12px;line-height:1.45;color:#6d7178;}
.tweet-module{max-width:520px;margin:0 auto;}
.tweet-link{display:block;color:inherit;text-decoration:none;}
.tweet-card{padding:18px 20px 16px;border:1px solid rgba(214,208,198,0.9);border-radius:14px;background:#ffffff;}
.tweet-author{margin-bottom:10px;}
.tweet-name{font-size:15px;font-weight:700;letter-spacing:-0.01em;color:#121212;}
.tweet-handle{font-size:13px;color:#6d7178;margin-left:7px;}
.tweet-text{font-size:17px;line-height:1.46;letter-spacing:-0.01em;color:#121212;white-space:pre-wrap;}
.tweet-meta{margin-top:12px;font-size:12px;line-height:1.45;color:#6d7178;}
.footer{padding:28px 40px 36px;font-size:11px;color:#474a51;border-top:1px solid rgba(214,208,198,0.8);background:#ffffff;}
.footer a{color:#121212;text-decoration:none;border-bottom:1px solid rgba(18,18,18,0.65);}
@media only screen and (max-width: 640px){
  .wrap{max-width:100% !important;}
  .wrap{padding:12px 8px 28px !important;}
  .header{padding:22px 10px 16px !important;}
  .section{padding:0 10px 18px !important;}
  .footer{padding:22px 10px 24px !important;}
  .date-line{font-size:14px !important;margin-bottom:8px !important;}
  .logo{font-size:36px !important;margin-bottom:12px !important;}
  .welcome{font-size:16px !important;line-height:1.45 !important;}
  .section-rule{margin-bottom:18px !important;}
  .list-row{display:block !important;padding-bottom:12px !important;margin-bottom:12px !important;}
  .item-row-link{display:block !important;}
  .list-time{min-width:62px !important;flex-shrink:0;}
  .weather-place{font-size:15px !important;}
  .weather-line{font-size:15px !important;}
  .list-main{font-size:14px !important;}
  .list-meta{font-size:11px !important;line-height:1.45 !important;}
  .calendar-source{white-space:normal !important;}
  .msg-summary{font-size:15px !important;line-height:1.5 !important;}
  .nyt{display:flex !important;gap:10px !important;align-items:flex-start !important;padding-bottom:16px !important;margin-bottom:16px !important;}
  .nyt-link{display:flex !important;gap:10px !important;align-items:flex-start !important;}
  .nytthumb{display:block !important;width:112px !important;height:75px !important;max-width:none !important;flex-shrink:0 !important;margin:0 !important;}
  .nythed{font-size:16px !important;margin-bottom:5px !important;}
  .nytdek{font-size:12px !important;line-height:1.45 !important;}
  .nytmeta{font-size:11px !important;margin-top:6px !important;}
  .photo-meta{font-size:11px !important;gap:8px !important;}
  .tweet-card{padding:14px 14px 12px !important;border-radius:12px !important;}
  .tweet-text{font-size:16px !important;line-height:1.45 !important;}
  .tweet-meta{font-size:11px !important;margin-top:10px !important;}
}
"""


def _label(text: str) -> str:
    return f'<div style="{SECTION_LABEL_STYLE}">{_esc(text)}</div>'


def _section(label: str | None, content: str, *, show_rule: bool = True) -> str:
    rule = '<div class="section-rule"></div>' if show_rule else ""
    heading = _label(label) if label else ""
    return f'<div class="section">{rule}{heading}{content}</div>'


def _shortcut_url(item_type: str, payload: dict) -> str:
    return ""


def _linked_text(item_type: str, text: str, payload: dict) -> str:
    href = _shortcut_url(item_type, payload)
    if not href:
        return _esc(text)
    return f'<a class="item-link" href="{_esc(href)}">{_esc(text)}</a>'


def _row_link(item_type: str, time_html: str, main_html: str, payload: dict) -> str:
    href = _shortcut_url(item_type, payload)
    if not href:
        return f'<div style="display:flex;gap:18px;align-items:baseline;width:100%;">{time_html}{main_html}</div>'
    return f'<a class="item-row-link" href="{_esc(href)}">{time_html}{main_html}</a>'


# Maps condition label (lowercased keyword) -> emoji. First match wins, so
# specific conditions come before general ones ("sun shower" before "rain").
_WEATHER_EMOJI = [
    ("thunder",       "\u26c8\ufe0f"),        # ⛈️
    ("strong storm",  "\u26c8\ufe0f"),        # ⛈️
    ("hurricane",     "\U0001f300"),           # 🌀
    ("tropical",      "\U0001f300"),           # 🌀
    ("blizzard",      "\U0001f328\ufe0f"),    # 🌨️
    ("snow",          "\U0001f328\ufe0f"),    # 🌨️
    ("flurr",         "\U0001f328\ufe0f"),    # 🌨️
    ("sleet",         "\U0001f328\ufe0f"),    # 🌨️
    ("wintry",        "\U0001f328\ufe0f"),    # 🌨️
    ("freezing",      "\U0001f9ca"),           # 🧊
    ("hail",          "\U0001f9ca"),           # 🧊
    ("sun shower",    "\U0001f326\ufe0f"),    # 🌦️
    ("rain",          "\U0001f327\ufe0f"),    # 🌧️
    ("drizzle",       "\U0001f327\ufe0f"),    # 🌧️
    ("fog",           "\U0001f32b\ufe0f"),    # 🌫️
    ("haz",           "\U0001f32b\ufe0f"),    # 🌫️
    ("smok",          "\U0001f32b\ufe0f"),    # 🌫️
    ("dust",          "\U0001f32b\ufe0f"),    # 🌫️
    ("wind",          "\U0001f4a8"),           # 💨
    ("breezy",        "\U0001f4a8"),           # 💨
    ("frigid",        "\U0001f976"),           # 🥶
    ("hot",           "\U0001f975"),           # 🥵
    ("mostly clear",  "\U0001f324\ufe0f"),    # 🌤️
    ("clear",         "\u2600\ufe0f"),        # ☀️
    ("partly",        "\u26c5"),               # ⛅
    ("mostly cloudy", "\U0001f325\ufe0f"),    # 🌥️
    ("cloudy",        "\u2601\ufe0f"),        # ☁️
]
_DEFAULT_WEATHER_EMOJI = "\U0001f321\ufe0f"   # 🌡️


def _weather_emoji(condition: str) -> str:
    c = (condition or "").lower()
    for keyword, emoji in _WEATHER_EMOJI:
        if keyword in c:
            return emoji
    return _DEFAULT_WEATHER_EMOJI


def _weather_html(data: dict) -> tuple[str, list]:
    """Compact weather: place name, then one line of
    emoji, current temp, (low/high) and a short blurb.

    Returns (html, icon_attachments); emoji need no attachments, so the list
    is always empty. Kept as a tuple so render_email's contract is unchanged.
    """
    rows = []
    for loc in data["locations"]:
        sentence_html = ""
        if loc.get("sentence"):
            sentence_html = f' <span class="weather-summary">{_esc(loc["sentence"])}</span>'

        alert_html = ""
        for alert in loc.get("alerts", []):
            alert_html += (
                f'<div style="font-size:13px;line-height:1.45;font-weight:600;color:#d93025;margin-top:4px;">'
                f'\u26a0 <a href="{_esc(alert["url"])}" style="color:#d93025;text-decoration:none;">'
                f'{_esc(alert["event"])} until {_esc(alert["expires"])} \u2192</a></div>'
            )

        rows.append(
            f'<div class="weather-loc">'
            f'<div class="weather-place">{_esc(loc["location"])}</div>'
            f'<div class="weather-line">'
            f'<span class="weather-emoji" aria-hidden="true">{_weather_emoji(loc.get("condition", ""))}</span> '
            f'<span class="weather-temp">{loc["temp"]}\u00b0</span> '
            f'<span class="weather-range">({loc["low"]}\u00b0/{loc["high"]}\u00b0)</span>'
            f'{sentence_html}</div>'
            f'{alert_html}'
            f'</div>'
        )
    return _section(None, "".join(rows), show_rule=False), []


def _calendar_html(events: list, *, show_rule: bool = True) -> str:
    if not events:
        return _section("Calendar", '<div class="supporting">Nothing on the calendar.</div>', show_rule=show_rule)
    rows = []
    for e in events:
        time_str = _esc(e.get("time") or "All day")
        source = ""
        if e.get("calendar"):
            dot = ""
            if e.get("calendar_color"):
                dot = f'<span class="calendar-dot" style="background:{_esc(e["calendar_color"])};"></span>'
            color = _esc(e.get("calendar_color") or "#6d7178")
            source = (f'<span class="calendar-source calendar-line" style="color:{color};">'
                      f'{dot}{_esc(e["calendar"])}</span>')
        loc = ""
        if e.get("location"):
            loc = f'<span class="calendar-location">{_esc(e["location"])}</span>'
        payload = {
            "identifier": e.get("identifier"),
            "date": date.today().isoformat(),
            "time": e.get("time"),
            "calendar": e.get("calendar"),
            "location": e.get("location"),
            "title": e["title"],
        }
        time_html = f'<span class="list-time">{time_str}</span>'
        main_html = (
            f'<span class="list-main">{source}'
            f'<span class="calendar-title">{_esc(e["title"])}</span>{loc}</span>'
        )
        rows.append(
            f'<div class="list-row">'
            f'{_row_link("calendar", time_html, main_html, payload)}</div>'
        )
    return _section("Calendar", "".join(rows), show_rule=show_rule)


# Reminders are grouped by list in this order (case-insensitive); other lists
# follow alphabetically, then reminders with no list.
REMINDER_LIST_ORDER = ["Niedertodo", "Little York"]


def _reminder_group_key(list_name: str | None) -> tuple:
    name = (list_name or "").strip()
    order = [n.casefold() for n in REMINDER_LIST_ORDER]
    if name.casefold() in order:
        return (0, order.index(name.casefold()), "")
    if name:
        return (1, 0, name.casefold())
    return (2, 0, "")


def _reminders_html(data: dict, *, show_rule: bool = True) -> str:
    """Reminders grouped by list: a caps list heading, then one row per
    reminder with a hollow circle in the list color, the title, and a
    right-aligned status (Overdue in red, or Today). Reminders due on a
    later day are not shown."""
    items = []  # (list_name, list_color, title, status_html, payload)
    for r in data.get("overdue", []):
        items.append((r, '<span class="reminder-status reminder-overdue">Overdue</span>'))
    for r in data.get("today", []):
        items.append((r, '<span class="reminder-status">Today</span>'))
    # Reminders due on a later day stay out of the email: only what is
    # overdue or due today is listed.
    if not items:
        return _section("Reminders", '<div class="supporting">All clear.</div>', show_rule=show_rule)

    # Stable sort keeps overdue -> today order within each list.
    items.sort(key=lambda item: _reminder_group_key(item[0].get("list")))
    groups: list[tuple[str, list[str]]] = []
    for r, status_html in items:
        list_name = (r.get("list") or "").strip()
        color = r.get("list_color") or MUTED
        payload = {"identifier": r.get("identifier"), "due": r.get("due"), "list": r.get("list"), "title": r["title"]}
        row = (
            f'<div class="reminder-row">'
            f'<span class="reminder-check" style="border-color:{_esc(color)};"></span>'
            f'<span class="reminder-title">{_linked_text("reminder", r["title"], payload)}</span>'
            f'{status_html}</div>'
        )
        if not groups or groups[-1][0] != list_name:
            groups.append((list_name, []))
        groups[-1][1].append(row)

    parts = []
    for list_name, rows in groups:
        heading = f'<div class="reminder-list">{_esc(list_name)}</div>' if list_name else ""
        parts.append(f'<div class="reminder-group">{heading}{"".join(rows)}</div>')
    return _section("Reminders", "".join(parts), show_rule=show_rule)


def _nyt_html(stories: list, *, show_rule: bool = True) -> str:
    rows = []
    for s in stories:
        img = ""
        if s.get("thumbnail"):
            img = f'<img class="nytthumb" src="{_esc(s["thumbnail"])}" alt="">'
        meta_bits = []
        published_date = s.get("published_date")
        if published_date:
            try:
                published = date.fromisoformat(published_date)
                age_days = (date.today() - published).days
                if age_days == 0:
                    meta_bits.append("Today")
                elif age_days > 0:
                    meta_bits.append(f"{age_days}d ago")
                else:
                    meta_bits.append(published.strftime("%b %-d, %Y"))
            except (TypeError, ValueError):
                meta_bits.append(str(published_date))
        if s.get("byline"):
            meta_bits.append(s["byline"])
        meta = f'<div class="nytmeta">{_esc(" · ".join(meta_bits))}</div>' if meta_bits else ""
        rows.append(
            f'<div class="nyt"><a class="nyt-link" href="{_esc(s["url"])}">'
            f'<div style="flex:1;"><div class="nythed">{_esc(s["title"])}</div>'
            f'<div class="nytdek">{_esc(s["abstract"])}</div>{meta}</div>{img}</a></div>'
        )
    return _section("Top Stories", "".join(rows), show_rule=show_rule)


def _photo_html(photo: tuple, *, show_rule: bool = True) -> str:
    _, meta = photo
    raw_date = meta.get("date")
    try:
        d = date.fromisoformat(raw_date)
        pretty_date = d.strftime("%B %-d, %Y")
        year = str(d.year)
    except Exception:
        pretty_date = raw_date or "Today"
        year = ""

    heading = f"On This Day · {year}" if year else "On This Day"

    meta_bits = [_esc(pretty_date)]
    if meta.get("location"):
        meta_bits.append(_esc(meta["location"]))
    meta_line = " · ".join(meta_bits)
    description = meta.get("description")
    description_html = f'<div class="photo-description">{_esc(description)}</div>' if description else ""
    body = (
        '<div class="photo-module">'
        '<div class="photo-frame"><img src="cid:onthisday" alt="On This Day photo"></div>'
        f'<div style="margin-top:10px;">'
        f'<div style="{SECTION_LABEL_STYLE}">{_esc(heading)}</div>'
        f'{description_html}'
        f'<div class="photo-meta">{meta_line}</div>'
        f'</div>'
        '</div>'
    )
    return _section(None, body, show_rule=show_rule)


def _tweet_html(tweet: dict, *, show_rule: bool = True) -> str:
    source = tweet.get("source")
    year = tweet.get("year") or ""
    if source == "authored":
        heading = "You Tweeted"
        try:
            years_ago = date.today().year - int(year)
        except (TypeError, ValueError):
            years_ago = None
        if years_ago is not None and years_ago >= 1:
            unit = "year" if years_ago == 1 else "years"
            heading = f"You Tweeted · {years_ago} {unit} ago"
        elif year:
            heading = f"You Tweeted · {year}"
    elif source == "bookmarked":
        heading = "From Your Bookmarks"
    else:
        heading = "A Tweet You Liked"

    raw_date = tweet.get("date")
    try:
        pretty_date = date.fromisoformat(raw_date).strftime("%B %-d, %Y")
    except (TypeError, ValueError):
        pretty_date = raw_date or ""

    meta_bits = []
    if pretty_date:
        meta_bits.append(_esc(pretty_date))
    likes = tweet.get("like_count") or 0
    if likes:
        meta_bits.append(f"{likes:,} likes")
    meta_line = " · ".join(meta_bits)
    meta_html = f'<div class="tweet-meta">{meta_line}</div>' if meta_line else ""

    handle = tweet.get("handle") or ""
    handle_html = f'<span class="tweet-handle">@{_esc(handle)}</span>' if handle else ""
    author_html = (
        f'<div class="tweet-author">'
        f'<span class="tweet-name">{_esc(tweet.get("display_name") or "")}</span>'
        f'{handle_html}</div>'
    )
    card_inner = (
        f'{author_html}'
        f'<div class="tweet-text">{_esc(tweet.get("text") or "")}</div>'
        f'{meta_html}'
    )
    url = tweet.get("url")
    if url:
        card = f'<a class="tweet-link" href="{_esc(url)}"><div class="tweet-card">{card_inner}</div></a>'
    else:
        card = f'<div class="tweet-card">{card_inner}</div>'

    body = (
        '<div class="tweet-module">'
        f'<div style="{SECTION_LABEL_STYLE}">{_esc(heading)}</div>'
        f'{card}'
        '</div>'
    )
    return _section(None, body, show_rule=show_rule)


PACKAGE_ZONE = ZoneInfo("America/New_York")
# Rows that need attention sort first, ahead of the date order.
PACKAGE_URGENT = {"out for delivery", "failed delivery attempt", "delivery exception"}


def _package_moment(day: str, time: str | None, source_zone: str | None) -> datetime:
    moment = datetime.strptime(day + ("T" + time if time else ""),
                               "%Y-%m-%dT%H:%M" if time else "%Y-%m-%d")
    if time and source_zone == "UTC":
        return moment.replace(tzinfo=timezone.utc).astimezone(PACKAGE_ZONE)
    return moment


def _package_date(moment: datetime, *, include_date: bool = True,
                  include_time: bool = True) -> str:
    day = moment.strftime("%b %-d") if include_date else ""
    if not include_time:
        return day
    hour = moment.strftime("%-I:%M %p" if moment.minute else "%-I %p")
    return f"{day}, {hour}" if day else hour


def _package_clock(moment: datetime) -> str:
    """Calendar-style clock: "5:19am", "8pm"."""
    clock = moment.strftime("%-I:%M" if moment.minute else "%-I")
    return clock + moment.strftime("%p").lower()


def _package_day_range(first: date, last: date) -> str:
    if first.month == last.month:
        return f"{first.strftime('%b %-d')}–{last.day}"
    return f"{first.strftime('%b %-d')}–{last.strftime('%b %-d')}"


def _package_when(expected: dict | None, status: str,
                  today: date) -> tuple[str, str, date | None]:
    """Left-column label, its CSS class, and the start date used for sorting."""
    if status == "delivered":
        return "Delivered", "", None
    if not expected:
        return "No date", "", None
    zone = expected["timezone"]
    first = _package_moment(expected["date"], expected["time"], zone).date()
    last = (_package_moment(expected["end_date"], expected["end_time"], zone).date()
            if expected["end_date"] else first)
    if last < today:
        label = (first.strftime("%b %-d") if last == first
                 else _package_day_range(first, last))
        return label, " pkg-late", first
    if last != first:
        if all(2 <= (day - today).days <= 6 for day in (first, last)):
            return f"{first.strftime('%a')}–{last.strftime('%a')}", "", first
        return _package_day_range(first, last), "", first
    days = (first - today).days
    if days == 0:
        return "Today", " pkg-today", first
    if days == 1:
        return "Tomorrow", "", first
    if days <= 6:
        return first.strftime("%a"), "", first
    return first.strftime("%b %-d"), "", first


def _package_window(expected: dict | None) -> str | None:
    """Delivery time of day, if Parcel gave one: "by 8pm" or "2–6pm"."""
    if not expected or not (expected["time"] or expected["end_time"]):
        return None
    zone = expected["timezone"]
    start = (_package_moment(expected["date"], expected["time"], zone)
             if expected["time"] else None)
    end = (_package_moment(expected["end_date"], expected["end_time"], zone)
           if expected["end_date"] and expected["end_time"] else None)
    if start and end and start.date() == end.date() and start < end:
        first, last = _package_clock(start), _package_clock(end)
        if first[-2:] == last[-2:]:
            first = first[:-2]
        return f"{first}–{last}"
    return f"by {_package_clock(end or start)}"


def _package_event_when(event: dict, today: date) -> str:
    moment = _package_moment(event["date"], event.get("time"), event.get("timezone"))
    has_time = bool(event.get("time"))
    days = (today - moment.date()).days
    if days == 0:
        return _package_clock(moment) if has_time else "today"
    if 1 <= days <= 6:
        day = moment.strftime("%a")
    else:
        day = moment.strftime("%b %-d") + ("," if has_time else "")
    return f"{day} {_package_clock(moment)}" if has_time else day


def _packages_html(packages: dict, *, show_rule: bool = True,
                   today: date | None = None) -> str:
    today = today or date.today()
    rows = []
    if packages.get("refresh_succeeded") is False:
        checked = None
        try:
            moment = datetime.fromisoformat(packages.get("as_of", "").replace("Z", "+00:00"))
            if moment.tzinfo is not None:
                checked = _package_date(moment.astimezone(PACKAGE_ZONE)) + " ET"
        except (AttributeError, TypeError, ValueError):
            pass
        notice = (f"Couldn't refresh; last checked {checked}." if checked else
                  "Couldn't refresh; no usable snapshot." if packages.get("freshness") == "unavailable"
                  else "Couldn't refresh; last checked time unavailable.")
        rows.append(f'<div class="supporting">{_esc(notice)}</div>')
    if packages.get("freshness") == "stale":
        rows.append('<div class="supporting">Parcel data may be out of date.</div>')
    if packages.get("freshness") == "unavailable":
        rows.append('<div class="supporting">Packages unavailable.</div>')
    if packages.get("truncated"):
        rows.append('<div class="supporting">More shipments may be listed in Parcel.</div>')
    entries = []
    for package in packages["shipments"]:
        expected = package.get("expected_delivery")
        label, label_class, start = _package_when(expected, package["status"], today)
        entries.append((package, label, label_class, start))
    entries.sort(key=lambda entry: (entry[0]["status"] not in PACKAGE_URGENT,
                                    entry[3] is None, entry[3] or date.max))
    for package, label, label_class, _start in entries:
        status = package["status"].capitalize()
        details = [status]
        window = _package_window(package.get("expected_delivery"))
        if window:
            details.append(window)
        event = package.get("latest_event")
        if event and event["status"].casefold() != status.casefold():
            details.append(event["status"])
            if event.get("date"):
                details.append(_package_event_when(event, today))
        carrier_code = package.get("carrier_code") or ""
        carrier, color = PACKAGE_CARRIERS.get(carrier_code, (carrier_code.upper() or "Carrier", "#121212"))
        labels = [value for value in (package.get("company"), package.get("item")) if value]
        name = " · ".join(labels) if labels else "Package"
        time_html = f'<span class="list-time{label_class}">{_esc(label)}</span>'
        main_html = (
            f'<span class="list-main">'
            f'<span class="calendar-source calendar-line" style="color:{color};">'
            f'<span class="calendar-dot" style="background:{color};"></span>{_esc(carrier)}</span>'
            f'<span class="calendar-title">{_esc(name)}</span>'
            f'<span class="calendar-location">{_esc(" · ".join(details))}</span></span>'
        )
        rows.append(f'<div class="list-row package-row">'
                    f'{_row_link("package", time_html, main_html, {})}</div>')
    if (packages.get("no_active") and packages.get("freshness") == "fresh"
            and packages.get("refresh_succeeded") is True):
        rows.append('<div class="supporting">No active packages.</div>')
    elif packages.get("coverage_note") and packages.get("freshness") != "unavailable":
        rows.append(f'<div class="supporting">{_esc(packages["coverage_note"])}</div>')
    return _section("Packages", "".join(rows), show_rule=show_rule)


def render_email(
    recipient: str,
    welcome: str | None,
    weather: dict | None,
    calendar: list | None,
    reminders: dict | None,
    messages: dict | None,
    photo: tuple | None,
    nyt: list | None,
    tweet: dict | None = None,
    as_of: date | None = None,
    packages: dict | None = None,
    test_mode: bool = False,
) -> MIMEMultipart:
    today = as_of or date.today()
    date_str = today.strftime("%A, %B %-d, %Y")
    subject = (f"TEST · NiederDaily Packages · {date_str}"
               if test_mode else f"NiederDaily · {date_str}")

    welcome_html = ""
    if welcome:
        paragraphs = [part.strip() for part in welcome.split("\n\n") if part.strip()]
        welcome_html = '<div class="welcome">' + ''.join(
            f'<p>{_esc(part)}</p>' for part in paragraphs
        ) + '</div>'
    test_html = ('<div class="supporting" style="font-weight:700;color:#995000;'
                 'margin:0 0 16px;">TEST EDITION · Package integration preview</div>'
                 if test_mode else "")

    sections = []
    weather_icons: list = []
    # The compact weather block has no card border, so a rule always separates
    # it from the next section.
    next_section_rule = True
    if weather:
        weather_html_str, weather_icons = _weather_html(weather)
        sections.append(weather_html_str)
    if calendar is not None:
        sections.append(_calendar_html(calendar, show_rule=next_section_rule))
        next_section_rule = True
    if reminders:
        sections.append(_reminders_html(reminders, show_rule=next_section_rule))
        next_section_rule = True
    if packages:
        sections.append(_packages_html(packages, show_rule=next_section_rule, today=today))
        next_section_rule = True
    if photo:
        sections.append(_photo_html(photo, show_rule=next_section_rule))
        next_section_rule = True
    if tweet:
        sections.append(_tweet_html(tweet, show_rule=next_section_rule))
        next_section_rule = True
    if nyt:
        sections.append(_nyt_html(nyt, show_rule=next_section_rule))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{BASE_STYLES}</style></head>
<body>
<div class="wrap">
<div class="email">
  <div class="header">
    <div class="date-line">{date_str}</div>
    <div class="logo">Nieder<span style="color:{ACCENT};">Daily</span></div>
    {test_html}
    {welcome_html}
  </div>
  {"".join(sections)}
  <div class="footer">NiederDaily · <a href="mailto:{recipient}">{recipient}</a> · Every morning at 5:55am{" · Weather data from <a href='https://weatherkit.apple.com/legal-attribution.html'>Apple Weather</a>" if weather else ""}</div>
</div>
</div>
</body></html>"""

    # Outer mixed wrapper keeps Gmail from mangling the related bundle
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = recipient  # self-addressed; Gmail API sets the actual sender via OAuth

    related = MIMEMultipart("related")
    related.attach(MIMEText(html, "html", "utf-8"))

    # Weather icons as CID attachments (avoids Gmail extracting base64 data URIs)
    for cid, png_bytes in weather_icons:
        icon_part = MIMEImage(png_bytes, _subtype="png")
        icon_part.add_header("Content-ID", f"<{cid}>")
        icon_part.add_header("Content-Disposition", "inline")
        related.attach(icon_part)

    if photo:
        img_bytes, img_meta = photo
        img_fmt = img_meta.get("format", "jpeg")
        img_part = MIMEImage(img_bytes, _subtype=img_fmt)
        img_part.add_header("Content-ID", "<onthisday>")
        img_part.add_header("Content-Disposition", "inline")
        related.attach(img_part)

    msg.attach(related)
    return msg
