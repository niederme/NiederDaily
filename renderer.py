from __future__ import annotations

import json
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from html import escape as _esc
from urllib.parse import quote

ACCENT = "#ff453a"
INK = "#121212"
MUTED = "#474a51"
LINE = "#d6d0c6"
SHORTCUT_NAME = "Open NiederDaily Item"

BADGE_OVERDUE = f'<span style="display:inline-block;min-width:56px;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Overdue</span>'
BADGE_TODAY = f'<span style="display:inline-block;min-width:56px;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Today</span>'
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
.welcome{max-width:520px;font-size:18px;font-weight:300;line-height:1.38;color:#474a51;}
.section{padding:0 40px 24px;}
.section-rule{height:1px;background:#d6d0c6;margin:0 0 24px;}
.module-place{font-size:20px;font-weight:700;line-height:1.15;letter-spacing:-0.02em;color:#121212;margin-bottom:12px;}
.weather-card{padding:20px 22px 18px;border:1px solid rgba(214,208,198,0.9);border-radius:18px;background:#ffffff;}
.display-line{font-size:58px;font-weight:300;line-height:0.94;letter-spacing:-0.03em;color:#121212;display:flex;align-items:center;gap:18px;flex-wrap:wrap;}
.weather-icon{display:inline-block;width:56px;height:56px;vertical-align:middle;flex-shrink:0;line-height:0;}
.weather-icon svg{width:56px;height:56px;}
.weather-summary{font-size:14px;line-height:1.45;color:#474a51;margin-top:8px;}
.weather-meta{font-size:12px;line-height:1.45;color:#6d7178;margin-top:4px;}
.supporting{font-size:13px;line-height:1.45;color:#474a51;margin-top:8px;}
.list-row{display:flex;gap:18px;align-items:baseline;padding:0 0 11px;margin:0 0 11px;border-bottom:1px solid rgba(214,208,198,0.55);}
.list-row:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.list-time{min-width:56px;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#474a51;}
.list-main{flex:1;font-size:15px;line-height:1.35;color:#121212;}
.item-link{color:#121212;text-decoration:none;}
.item-link:hover{text-decoration:underline;}
.item-row-link{display:flex;gap:18px;align-items:baseline;width:100%;color:inherit;text-decoration:none;}
.item-row-link:hover .list-main{text-decoration:underline;}
.list-meta{display:block;font-size:12px;line-height:1.4;color:#474a51;margin-top:4px;}
.meta-sep{color:#9aa0a6;margin:0 6px;}
.calendar-source{display:inline-flex;align-items:center;gap:6px;color:#6d7178;white-space:nowrap;}
.calendar-dot{display:inline-block;width:8px;height:8px;border-radius:999px;flex-shrink:0;}
.msg-summary{max-width:520px;font-size:16px;line-height:1.55;color:#474a51;}
.nyt{display:flex;gap:20px;align-items:flex-start;padding:0 0 16px;margin:0 0 16px;border-bottom:1px solid rgba(214,208,198,0.55);}
.nyt:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.nyt-link{display:flex;gap:20px;align-items:flex-start;width:100%;color:inherit;text-decoration:none;}
.nytthumb{width:175px;height:117px;object-fit:cover;object-position:right center;flex-shrink:0;background:#f5efe5;}
.nythed{font-size:17px;font-weight:700;line-height:1.18;color:#121212;margin-bottom:6px;}
.nytdek{font-size:13px;color:#474a51;line-height:1.42;}
.nytbyline{font-size:11px;color:#474a51;line-height:1.4;margin-top:7px;}
.photo-module{max-width:520px;margin:0 auto;}
.photo-frame{display:block;border-radius:14px;overflow:hidden;border:1px solid rgba(214,208,198,0.7);background:#ffffff;line-height:0;}
.photo-frame img{width:100%;display:block;}
.photo-description{font-size:16px;font-weight:400;letter-spacing:-0.01em;line-height:1.45;color:#474a51;margin-top:4px;}
.photo-meta{margin-top:6px;font-size:12px;line-height:1.45;color:#6d7178;}
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
  .module-place{font-size:18px !important;margin-bottom:10px !important;}
  .weather-card{padding:14px 14px 12px !important;border-radius:16px !important;}
  .display-line{font-size:42px !important;gap:12px !important;}
  .weather-icon{width:60px !important;height:60px !important;}
  .weather-icon svg{width:40px !important;height:40px !important;}
  .weather-summary{font-size:13px !important;line-height:1.4 !important;}
  .weather-meta{font-size:11px !important;}
  .list-row{display:block !important;padding-bottom:12px !important;margin-bottom:12px !important;}
  .item-row-link{display:block !important;}
  .list-time{display:block !important;min-width:0 !important;margin-bottom:4px !important;}
  .list-main{font-size:14px !important;}
  .list-meta{font-size:11px !important;line-height:1.45 !important;}
  .calendar-source{white-space:normal !important;}
  .msg-summary{font-size:15px !important;line-height:1.5 !important;}
  .nyt{display:flex !important;gap:10px !important;align-items:flex-start !important;padding-bottom:16px !important;margin-bottom:16px !important;}
  .nyt-link{display:flex !important;gap:10px !important;align-items:flex-start !important;}
  .nytthumb{display:block !important;width:112px !important;height:75px !important;max-width:none !important;flex-shrink:0 !important;margin:0 !important;}
  .nythed{font-size:16px !important;margin-bottom:5px !important;}
  .nytdek{font-size:12px !important;line-height:1.45 !important;}
  .nytbyline{font-size:11px !important;margin-top:6px !important;}
  .photo-meta{font-size:11px !important;gap:8px !important;}
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


def _render_sf_symbol(name: str, hex_color: str, size: int = 56) -> bytes | None:
    """Render SF Symbol as PNG bytes (for CID attachment)."""
    try:
        from AppKit import (NSImage, NSImageSymbolConfiguration, NSColor,
                            NSBitmapImageRep, NSGraphicsContext)
        from Foundation import NSMakeRect, NSMakeSize
        r = int(hex_color[1:3], 16) / 255
        g = int(hex_color[3:5], 16) / 255
        b = int(hex_color[5:7], 16) / 255
        color = NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)
        cfg = NSImageSymbolConfiguration.configurationWithPaletteColors_([color, color, color])
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is None:
            return None
        img = img.imageWithSymbolConfiguration_(cfg)
        img.setSize_(NSMakeSize(size, size))
        px = size * 2
        bmp = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, px, px, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0)
        ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(bmp)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(ctx)
        img.drawInRect_(NSMakeRect(0, 0, px, px))
        NSGraphicsContext.restoreGraphicsState()
        png_data = bmp.representationUsingType_properties_(4, None)
        return bytes(png_data)
    except Exception:
        return None


# Maps condition label (lowercased keyword) → (sf_symbol_name, hex_color)
_SF_SYMBOL_MAP = [
    ("thunder",         "cloud.bolt.rain.fill",     ACCENT),
    ("blizzard",        "wind.snow",                MUTED),
    ("snow",            "cloud.snow.fill",           MUTED),
    ("flurr",           "cloud.snow.fill",           MUTED),
    ("sleet",           "cloud.sleet.fill",          MUTED),
    ("wintry",          "cloud.sleet.fill",          MUTED),
    ("freezing",        "cloud.sleet.fill",          MUTED),
    ("hail",            "cloud.hail.fill",           MUTED),
    ("heavy rain",      "cloud.heavyrain.fill",      ACCENT),
    ("rain",            "cloud.rain.fill",           ACCENT),
    ("drizzle",         "cloud.drizzle.fill",        ACCENT),
    ("shower",          "cloud.sun.rain.fill",       ACCENT),
    ("fog",             "cloud.fog.fill",            MUTED),
    ("haz",             "sun.haze.fill",             MUTED),
    ("smok",            "smoke.fill",                MUTED),
    ("dust",            "sun.dust.fill",             MUTED),
    ("wind",            "wind",                      MUTED),
    ("breezy",          "wind",                      MUTED),
    ("mostly clear",    "sun.max.fill",              ACCENT),
    ("clear",           "sun.max.fill",              ACCENT),
    ("sun shower",      "cloud.sun.rain.fill",       ACCENT),
    ("sun",             "sun.max.fill",              ACCENT),
    ("partly",          "cloud.sun.fill",            MUTED),
    ("mostly cloudy",   "cloud.fill",                MUTED),
    ("cloudy",          "cloud.fill",                MUTED),
    ("frigid",          "thermometer.snowflake",     MUTED),
    ("hot",             "thermometer.sun.fill",      ACCENT),
    ("hurricane",       "hurricane",                 ACCENT),
    ("tropical",        "tropicalstorm",             ACCENT),
]


def _weather_icon(condition: str, icon_registry: dict) -> str:
    """Returns icon HTML. Renders SF Symbol as CID attachment; registers in icon_registry."""
    c = condition.lower()
    for keyword, symbol, color in _SF_SYMBOL_MAP:
        if keyword in c:
            if symbol not in icon_registry:
                png_bytes = _render_sf_symbol(symbol, color)
                if png_bytes:
                    cid = f"wicon-{symbol.replace('.', '-').replace(' ', '-')}"
                    icon_registry[symbol] = (cid, png_bytes)
            if symbol in icon_registry:
                cid, _ = icon_registry[symbol]
                return (
                    f'<span class="weather-icon" aria-hidden="true">'
                    f'<img src="cid:{cid}" width="56" height="56" alt=""'
                    f' style="display:inline-block;vertical-align:middle;">'
                    f'</span>'
                )
            break
    # fallback: plain cloud SVG
    return (
        f'<span class="weather-icon" aria-hidden="true">'
        f'<svg width="56" height="56" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="M10 14.5C10 10.9101 12.9101 8 16.5 8C19.2451 8 21.5927 9.70662 22.5287 12.1172C22.8455 12.0398 23.1765 12 23.5167 12C25.9921 12 28 14.0079 28 16.4833C28 18.9588 25.9921 20.9667 23.5167 20.9667H12.5C9.46243 20.9667 7 18.5042 7 15.4667C7 12.4291 9.46243 9.96667 12.5 9.96667" stroke="{MUTED}" stroke-width="1.8" stroke-linecap="round"/>'
        f'</svg></span>'
    )


def _weather_html(data: dict) -> tuple[str, list]:
    """Returns (html, icon_attachments) where icon_attachments is [(cid, png_bytes), ...]."""
    parts = []
    icon_registry: dict = {}  # symbol_name -> (cid, png_bytes)
    for loc in data["locations"]:
        sentence_html = ""
        if loc.get("sentence"):
            sentence_html = f'<div class="weather-summary">{_esc(loc["sentence"])}</div>'

        alert_html = ""
        for alert in loc.get("alerts", []):
            alert_html += (
                f'<div style="margin-top:10px;padding:8px 0;border-top:1px solid rgba(214,208,198,0.6);">'
                f'<div style="font-size:12px;font-weight:600;color:#ff453a;">'
                f'⚠ <a href="{_esc(alert["url"])}" style="color:#ff453a;text-decoration:none;">'
                f'{_esc(alert["event"])} →</a></div>'
                f'<div style="font-size:11px;color:{MUTED};margin-top:2px;">'
                f'Until {_esc(alert["expires"])} · {_esc(alert["agency"])}</div>'
                f'</div>'
            )

        attribution_html = (
            f'<div style="font-size:10px;color:#9aa0a6;margin-top:8px;">'
            f'<a href="https://weatherkit.apple.com/legal-attribution.html" '
            f'style="color:#9aa0a6;text-decoration:none;">Weather</a></div>'
        )

        body = (
            f'<div class="weather-card">'
            f'<div class="module-place">{_esc(loc["location"])}</div>'
            f'<div class="display-line">'
            f'{_weather_icon(loc["condition"], icon_registry)}'
            f'<span>{loc["high"]}° / {loc["low"]}°</span></div>'
            f'{sentence_html}'
            f'<div class="weather-meta">Currently {loc["temp"]}° · Sunrise {_esc(loc["sunrise"])} · Sunset {_esc(loc["sunset"])}</div>'
            f'{alert_html}'
            f'{attribution_html}'
            f'</div>'
        )
        parts.append(_section(None, body, show_rule=False))
    return "".join(parts), list(icon_registry.values())


def _calendar_html(events: list, *, show_rule: bool = True) -> str:
    if not events:
        return _section("Calendar", '<div class="supporting">Nothing on the calendar.</div>', show_rule=show_rule)
    rows = []
    for e in events:
        time_str = _esc(e.get("time") or "All day")
        meta_parts = []
        if e.get("location"):
            meta_parts.append(_esc(e["location"]))
        if e.get("calendar"):
            dot = ""
            if e.get("calendar_color"):
                dot = f'<span class="calendar-dot" style="background:{_esc(e["calendar_color"])};"></span>'
            meta_parts.append(f'<span class="calendar-source">{dot}{_esc(e["calendar"])}</span>')
        loc = ""
        if meta_parts:
            meta_sep = '<span class="meta-sep">·</span>'
            loc = f'<span class="list-meta">{meta_sep.join(meta_parts)}</span>'
        payload = {
            "identifier": e.get("identifier"),
            "date": date.today().isoformat(),
            "time": e.get("time"),
            "calendar": e.get("calendar"),
            "location": e.get("location"),
            "title": e["title"],
        }
        time_html = f'<span class="list-time">{time_str}</span>'
        main_html = f'<span class="list-main">{_esc(e["title"])}{loc}</span>'
        rows.append(
            f'<div class="list-row">'
            f'{_row_link("calendar", time_html, main_html, payload)}</div>'
        )
    return _section("Calendar", "".join(rows), show_rule=show_rule)


def _reminders_html(data: dict, *, show_rule: bool = True) -> str:
    def reminder_meta(item: dict) -> str:
        if not item.get("list"):
            return ""
        dot = ""
        if item.get("list_color"):
            dot = f'<span class="calendar-dot" style="background:{_esc(item["list_color"])};"></span>'
        return f'<span class="list-meta"><span class="calendar-source">{dot}{_esc(item["list"])}</span></span>'

    rows = []
    for r in data.get("overdue", []):
        payload = {"identifier": r.get("identifier"), "due": r.get("due"), "list": r.get("list"), "title": r["title"]}
        time_html = f'<span class="list-time">{BADGE_OVERDUE}</span>'
        main_html = f'<span class="list-main">{_esc(r["title"])}{reminder_meta(r)}</span>'
        rows.append(f'<div class="list-row">{_row_link("reminder", time_html, main_html, payload)}</div>')
    for r in data.get("today", []):
        payload = {"identifier": r.get("identifier"), "due": r.get("due"), "list": r.get("list"), "title": r["title"]}
        time_html = f'<span class="list-time">{BADGE_TODAY}</span>'
        main_html = f'<span class="list-main">{_esc(r["title"])}{reminder_meta(r)}</span>'
        rows.append(f'<div class="list-row">{_row_link("reminder", time_html, main_html, payload)}</div>')
    next_day = None
    for r in data.get("upcoming", []):
        due_raw = r.get("due")
        if next_day is None:
            next_day = due_raw
        elif due_raw != next_day:
            break
        try:
            from datetime import datetime
            due = datetime.strptime(due_raw, "%Y-%m-%d").strftime("%a %-d")
        except Exception:
            due = due_raw
        badge = f'<span style="display:inline-block;min-width:56px;color:{MUTED};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">{due}</span>'
        payload = {"identifier": r.get("identifier"), "due": r.get("due"), "list": r.get("list"), "title": r["title"]}
        time_html = f'<span class="list-time">{badge}</span>'
        main_html = f'<span class="list-main">{_esc(r["title"])}{reminder_meta(r)}</span>'
        rows.append(f'<div class="list-row">{_row_link("reminder", time_html, main_html, payload)}</div>')
    if not rows:
        return _section("Reminders", '<div class="supporting">All clear.</div>', show_rule=show_rule)
    return _section("Reminders", "".join(rows), show_rule=show_rule)


def _nyt_html(stories: list, *, show_rule: bool = True) -> str:
    rows = []
    for s in stories:
        img = ""
        if s.get("thumbnail"):
            img = f'<img class="nytthumb" src="{_esc(s["thumbnail"])}" alt="">'
        byline = ""
        if s.get("byline"):
            byline = f'<div class="nytbyline">{_esc(s["byline"])}</div>'
        rows.append(
            f'<div class="nyt"><a class="nyt-link" href="{_esc(s["url"])}">'
            f'<div style="flex:1;"><div class="nythed">{_esc(s["title"])}</div>'
            f'<div class="nytdek">{_esc(s["abstract"])}</div>{byline}</div>{img}</a></div>'
        )
    return _section("In Case You Missed It", "".join(rows), show_rule=show_rule)


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


def render_email(
    recipient: str,
    welcome: str | None,
    weather: dict | None,
    calendar: list | None,
    reminders: dict | None,
    messages: dict | None,
    photo: tuple | None,
    nyt: list | None,
) -> MIMEMultipart:
    today = date.today()
    date_str = today.strftime("%A, %B %-d, %Y")
    subject = f"NiederDaily · {date_str}"

    welcome_html = ""
    if welcome:
        welcome_html = f'<div class="welcome">{_esc(welcome)}</div>'

    sections = []
    weather_icons: list = []
    next_section_rule = weather is None
    if weather:
        weather_html_str, weather_icons = _weather_html(weather)
        sections.append(weather_html_str)
    if calendar is not None:
        sections.append(_calendar_html(calendar, show_rule=next_section_rule))
        next_section_rule = True
    if reminders:
        sections.append(_reminders_html(reminders, show_rule=next_section_rule))
        next_section_rule = True
    if photo:
        sections.append(_photo_html(photo, show_rule=next_section_rule))
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
    {welcome_html}
  </div>
  {"".join(sections)}
  <div class="footer">NiederDaily · <a href="mailto:{recipient}">{recipient}</a> · Every morning at 6am</div>
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
